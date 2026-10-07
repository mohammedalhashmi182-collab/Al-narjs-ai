from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.models import Payment

# Single source of truth for package pricing is src/services/catalog.py
from src.services import catalog

PACKAGES = catalog.PACKAGES  # compatible alias — amounts live in catalog only

MOYASAR_API_URL = "https://api.moyasar.com/v1/payments"
MOYASAR_INVOICES_URL = "https://api.moyasar.com/v1/invoices"
VAT_RATE = 0.15

# Methods that are settled by the Moyasar hosted checkout. Every one of them
# needs MOYASAR_API_SECRET; without it the route silently degrades to a manual
# invoice, which is why the UI asks capabilities() before offering a button.
CARD_METHODS = ("mada", "stcpay", "creditcard", "applepay")

# A configured secret is not a working secret. Production answered 401
# "Invalid authorization credentials" on a set MOYASAR_API_SECRET, so the
# checkout was advertising mada, Visa, Mastercard and Apple Pay and failing
# every payment. The presence of the env var is not evidence, so this probes
# the credential and trusts the answer.
CREDENTIAL_PROBE_TTL_SECONDS = 300.0
CREDENTIAL_PROBE_TIMEOUT_SECONDS = 4.0
_credential_cache: dict[str, tuple[float, str]] = {}
_credential_lock = asyncio.Lock()


def vat_amount(halalas: int) -> int:
    return round(halalas * VAT_RATE)


def total_with_vat(halalas: int) -> int:
    return halalas + vat_amount(halalas)


def package_amount(package: str) -> int:
    pkg = catalog.PACKAGES.get(package)
    if not pkg:
        raise PaymentError(f"Unknown package: {package}")
    return pkg["amount"]


def promo_active() -> bool:
    settings = get_settings()
    return bool(settings.promo_code and settings.promo_percent > 0)


def promo_info() -> dict:
    settings = get_settings()
    return {
        "active": promo_active(),
        "code": settings.promo_code or "",
        "percent": settings.promo_percent if promo_active() else 0,
        "expires": settings.promo_expires or "",
    }


def apply_promo(halalas: int, promo: Optional[str] = None) -> tuple[int, int]:
    """Return (final_halalas, discount_percent). Promo applies to the base amount."""
    if not promo or not promo_active():
        return halalas, 0
    settings = get_settings()
    if promo.strip().upper() != settings.promo_code.strip().upper():
        return halalas, 0
    pct = settings.promo_percent
    return round(halalas * (100 - pct) / 100), pct


class PaymentError(Exception):
    pass


def paypal_ready() -> bool:
    settings = get_settings()
    return bool(settings.paypal_client_id and settings.paypal_client_secret)


def paypal_collects_money() -> bool:
    """A sandbox PayPal completes a checkout that never charges the buyer.

    Offering it next to the real methods is worse than not offering it: the
    buyer pays, no money moves, no subscription activates.
    """
    settings = get_settings()
    return paypal_ready() and settings.paypal_mode == "live"


def moyasar_secret_is_live() -> bool:
    """Whether the configured Moyasar secret can actually take a payment.

    A ``sk_test_`` secret is accepted by the API and creates real invoices, so a
    probe cannot detect it -- it returns 200 exactly like a live key. The prefix
    is the only signal, and it is decisive: Moyasar keys are self-describing and
    the prefix is not a secret, so reading it leaks nothing.

    Production was found configured with a test secret beside a *live*
    publishable key. The card buttons would have reappeared as soon as the
    credential passed its probe, and every buyer would have completed a sandbox
    checkout that charged nothing and activated nothing. A working probe is not
    the same as a working payment method.
    """
    secret = (get_settings().moyasar_api_secret or "").strip()
    if not secret:
        return False
    return secret.startswith("sk_live_")


def cached_credential_state(name: str) -> str:
    """The last probe answer, or "ok" while nothing has disproved it.

    Optimistic on purpose: an unprobed or unreachable gateway must not remove a
    method that works. Only a positive rejection hides it.
    """
    entry = _credential_cache.get(name)
    if entry and entry[0] > time.monotonic():
        return entry[1]
    return "ok"


async def probe_moyasar_credentials() -> str:
    """Ask Moyasar whether the configured secret is accepted.

    A GET on the invoice list is the cheapest authenticated call that changes
    nothing. Only 401/403 counts as proof: a timeout, a DNS failure or any
    unexpected status returns "unknown", which keeps the method visible, because
    hiding a working checkout over a network blip costs a real sale.
    """
    settings = get_settings()
    if not settings.moyasar_api_secret:
        return "unset"

    entry = _credential_cache.get("moyasar")
    if entry and entry[0] > time.monotonic():
        return entry[1]

    async with _credential_lock:
        entry = _credential_cache.get("moyasar")
        if entry and entry[0] > time.monotonic():
            return entry[1]
        state = "unknown"
        try:
            async with httpx.AsyncClient(timeout=CREDENTIAL_PROBE_TIMEOUT_SECONDS) as client:
                resp = await client.get(
                    MOYASAR_INVOICES_URL,
                    params={"page": 1},
                    headers={"Authorization": _auth_header(settings)},
                )
            state = "rejected" if resp.status_code in (401, 403) else "ok"
        except Exception:  # noqa: BLE001 - a probe must never raise into a request
            state = "unknown"
        _credential_cache["moyasar"] = (time.monotonic() + CREDENTIAL_PROBE_TTL_SECONDS, state)
        return state


def capabilities(card_state: Optional[str] = None) -> dict:
    """Which methods can actually take money right now.

    Booleans and public bank/contact details only — never a key, a secret or a
    token. The checkout renders exactly these methods, so a button can never
    promise a card payment that the server would quietly turn into a manual
    transfer.

    ``card_state`` carries the Moyasar credential verdict. Pass the probed value
    on the request path; omit it and the last known verdict is used.
    """
    from src.services import transfer

    settings = get_settings()
    if card_state is None:
        card_state = cached_credential_state("moyasar")
    card = bool(settings.moyasar_api_secret) and card_state != "rejected"
    test_mode = card and not moyasar_secret_is_live()
    if test_mode:
        # The credential works, so it passes the probe -- but a test secret cannot
        # move money. Offering it would be the PayPal-sandbox trap again.
        card = False
    paypal = paypal_collects_money()
    methods = {method: card for method in CARD_METHODS}
    methods["paypal"] = paypal
    methods["invoice"] = True
    return {
        "methods": methods,
        "card": card,
        "card_configured": bool(settings.moyasar_api_secret),
        "card_credentials": card_state,
        "card_test_mode": test_mode,
        "paypal": paypal,
        "paypal_configured": paypal_ready(),
        "paypal_test_mode": paypal_ready() and settings.paypal_mode != "live",
        "invoice": True,
        "bank": transfer.bank_details(),
        "contact": transfer.contact_channels(),
    }


async def capabilities_async() -> dict:
    """capabilities() with a live credential verdict for the card gateway."""
    return capabilities(card_state=await probe_moyasar_credentials())


async def readiness_async() -> dict:
    """readiness() with a live credential verdict for the card gateway."""
    return readiness(card_state=await probe_moyasar_credentials())


def readiness(card_state: Optional[str] = None) -> dict:
    """Owner-facing detail: what is configured and what is missing.

    Reports env-var *names* and booleans only. Values are never included, so
    this is safe to render on an owner screen.
    """
    settings = get_settings()
    caps = capabilities(card_state=card_state)
    missing: list[str] = []
    if not settings.moyasar_api_secret:
        missing.append("MOYASAR_API_SECRET")
    if not paypal_ready():
        missing.append("PAYPAL_CLIENT_ID+PAYPAL_CLIENT_SECRET")

    # A configured-but-rejected secret is worse than a missing one: it looks
    # ready and fails on every buyer. Name it first.
    blocking: list[str] = []
    if caps["card_credentials"] == "rejected":
        blocking.append(
            "MOYASAR_API_SECRET is set but Moyasar rejected it (401). "
            "Card checkout is hidden and every card payment would fail."
        )
    if caps.get("card_test_mode"):
        blocking.append(
            "MOYASAR_API_SECRET is a TEST key (sk_test_). Moyasar accepts it and "
            "creates invoices, but no money moves, so card checkout is hidden. "
            "Set an sk_live_ secret to take real card payments."
        )
    if paypal_ready() and caps["paypal_test_mode"]:
        blocking.append(
            "PAYPAL_MODE is not 'live', so PayPal completes sandbox checkouts "
            "that take no money. It is hidden until PAYPAL_MODE=live."
        )
    if not caps["bank"].get("iban"):
        blocking.append(
            "content/transfer.json has no bank details, so a bank-transfer "
            "buyer cannot pay unaided and must be messaged."
        )

    return {
        **caps,
        "collect_money_now": bool(caps["card"] or caps["paypal"]),
        "paypal_mode": settings.paypal_mode,
        "promo_active": promo_active(),
        "missing_env": missing,
        "blocking_issues": blocking,
        "env_required": {
            "card": ["MOYASAR_API_SECRET", "MOYASAR_PUBLISHABLE_KEY"],
            "paypal": ["PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_MODE=live"],
        },
    }


def reference(payment: Payment) -> str:
    """The short human-quotable invoice reference shown to the buyer."""
    return str(payment.id)[:8].upper()


def transfer_instructions(payment: Payment) -> dict:
    """Everything the buyer needs to settle a manual invoice unaided."""
    from src.services import transfer

    ref = reference(payment)
    total = total_with_vat(payment.amount)
    customer = payment.customer_name or payment.customer_phone or payment.customer_email
    return {
        "payment_id": str(payment.id),
        "reference": ref,
        "status": payment.status,
        "base_halalas": payment.amount,
        "vat_halalas": vat_amount(payment.amount),
        "total_halalas": total,
        "total_sar": round(total / 100, 2),
        "currency": payment.currency or "SAR",
        "bank": transfer.bank_details(),
        "contact": transfer.contact_buttons(ref, round(total / 100, 2), customer),
        "invoice_url": f"/invoice/{payment.id}",
    }


def _auth_header(settings) -> str:
    if not settings.moyasar_api_secret:
        raise PaymentError("Moyasar API secret not configured")
    token = base64.b64encode(f"{settings.moyasar_api_secret}:".encode()).decode()
    return f"Basic {token}"


async def create_payment(
    session: AsyncSession,
    package: str,
    customer_name: Optional[str] = None,
    customer_phone: Optional[str] = None,
    customer_email: Optional[str] = None,
    promo: Optional[str] = None,
    lead_id: Optional[UUID] = None,
    project_id: Optional[UUID] = None,
) -> Payment:
    pkg = catalog.PACKAGES.get(package)
    if not pkg:
        raise PaymentError(f"Unknown package: {package}")

    settings = get_settings()
    amount, discount_pct = apply_promo(pkg["amount"], promo)
    name = pkg["name"]

    description = f"باقة {name} - النرجس للذكاء الاصطناعي"
    if discount_pct:
        description += f" (خصم الإطلاق {discount_pct}%)"

    payment = Payment(
        amount=amount,
        currency="SAR",
        package=package,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email,
        lead_id=lead_id,
        project_id=project_id,
        status="pending",
        gateway="invoice",
        description=description,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def initiate_moyasar(
    session: AsyncSession,
    payment: Payment,
    source: dict,
    callback_url: Optional[str] = None,
    amount_halalas: Optional[int] = None,
) -> dict:
    settings = get_settings()
    if not settings.moyasar_api_secret:
        raise PaymentError("Moyasar API secret not configured")

    # Owner decision (option A): package prices are VAT-inclusive, so the amount
    # charged must equal what the invoice bills. This previously charged
    # payment.amount (the pre-VAT base) while the invoice document showed
    # base + 15%, under-collecting 15% on every card sale.
    charge = total_with_vat(payment.amount) if amount_halalas is None else amount_halalas
    if charge < payment.amount:
        raise PaymentError("Charge amount is below the recorded base amount")

    # Use the hosted-invoice flow so the customer pays on Moyasar's checkout
    # page without requiring client-side card tokenization.
    payload = {
        "amount": charge,
        "currency": "SAR",
        "description": payment.description or "النرجس للذكاء الاصطناعي",
        "callback_url": callback_url or settings.payment_success_url,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            MOYASAR_INVOICES_URL,
            json=payload,
            headers={"Authorization": _auth_header(settings)},
        )

    if resp.status_code not in (200, 201):
        raise PaymentError(f"Moyasar error {resp.status_code}: {resp.text}")

    data = resp.json()
    invoice_id = data.get("id")
    if not invoice_id:
        raise PaymentError(f"Moyasar invoice missing id: {resp.text[:200]}")

    payment.gateway = "moyasar"
    payment.gateway_payment_id = invoice_id
    payment.gateway_source = "invoice"
    await session.commit()
    checkout = data.get("url") or f"https://checkout.moyasar.com/invoices/{invoice_id}"
    if "lang=" not in checkout:
        checkout += ("&" if "?" in checkout else "?") + "lang=ar"
    else:
        checkout = checkout.replace("lang=en", "lang=ar")
    return {
        "id": invoice_id,
        "checkout_url": checkout,
    }


async def verify_payment(session: AsyncSession, payment_id: UUID) -> Payment:
    result = await session.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise PaymentError("Payment not found")

    settings = get_settings()
    if not settings.moyasar_api_secret or not payment.gateway_payment_id:
        return payment

    invoice_mode = payment.gateway_source == "invoice" or str(payment.gateway_payment_id).startswith("inv_")
    endpoint = MOYASAR_INVOICES_URL if invoice_mode else MOYASAR_API_URL

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{endpoint}/{payment.gateway_payment_id}",
            headers={"Authorization": _auth_header(settings)},
        )

    if resp.status_code != 200:
        raise PaymentError(f"Moyasar verify error {resp.status_code}: {resp.text}")

    data = resp.json()
    status = data.get("status")
    if status == "paid":
        payment.status = "paid"
    elif status in ("failed", "canceled"):
        payment.status = "failed"
    elif status == "authorized":
        payment.status = "authorized"
    elif status == "expired":
        payment.status = "failed"
    else:
        payment.status = status or payment.status

    src = data.get("source", {})
    if isinstance(src, dict):
        payment.gateway_source = src.get("type", payment.gateway_source)

    await session.commit()
    return payment


def source_credit_card() -> dict:
    return {"type": "creditcard"}


def source_mada() -> dict:
    return {"type": "creditcard", "company": "mada"}


def source_stcpay() -> dict:
    return {"type": "stcpay"}


def source_applepay() -> dict:
    return {"type": "applepay"}


def get_publishable_key() -> Optional[str]:
    return get_settings().moyasar_publishable_key


# ---------------- PayPal ----------------

def _paypal_base_url(settings) -> str:
    return "https://api-m.paypal.com" if settings.paypal_mode == "live" else "https://api-m.sandbox.paypal.com"


async def _paypal_token(settings) -> str:
    if not (settings.paypal_client_id and settings.paypal_client_secret):
        raise PaymentError("PayPal not configured")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_paypal_base_url(settings)}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(settings.paypal_client_id, settings.paypal_client_secret),
        )
    if resp.status_code != 200:
        raise PaymentError(f"PayPal auth error {resp.status_code}: {resp.text}")
    try:
        return resp.json()["access_token"]
    except (KeyError, ValueError):
        raise PaymentError("PayPal token response malformed")


async def create_paypal_order(
    session: AsyncSession,
    payment: Payment,
    amount_halalas: int,
    return_url: str,
    cancel_url: str,
) -> dict:
    settings = get_settings()
    token = await _paypal_token(settings)
    sar_total = amount_halalas  # halalas of SAR
    usd_value = sar_total / 100 * settings.paypal_sar_usd_rate
    if settings.paypal_currency.upper() == "USD":
        value = f"{usd_value:.2f}"
    else:
        value = f"{sar_total / 100:.2f}"
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": str(payment.id),
            "custom_id": str(payment.id),
            "description": (payment.description or "Al-Narjis AI")[:127],
            "amount": {
                "currency_code": settings.paypal_currency,
                "value": value,
            },
        }],
        "application_context": {
            "return_url": return_url,
            "cancel_url": cancel_url,
            "brand_name": "Al-Narjis AI",
            "user_action": "PAY_NOW",
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_paypal_base_url(settings)}/v2/checkout/orders",
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
    if resp.status_code not in (200, 201):
        raise PaymentError(f"PayPal create error {resp.status_code}: {resp.text}")

    data = resp.json()
    payment.gateway = "paypal"
    payment.status = "pending"
    payment.gateway_payment_id = data.get("id")
    await session.commit()

    approval = next((l for l in data.get("links", []) if l.get("rel") == "approve"), None)
    return {
        "order_id": data.get("id"),
        "approval_url": approval.get("href") if approval else None,
    }


async def capture_paypal_order(order_id: str) -> dict:
    settings = get_settings()
    token = await _paypal_token(settings)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_paypal_base_url(settings)}/v2/checkout/orders/{order_id}/capture",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
    if resp.status_code not in (200, 201):
        raise PaymentError(f"PayPal capture error {resp.status_code}: {resp.text}")
    return resp.json()


async def activate_subscription(session: AsyncSession, payment: Payment) -> dict:
    """Activate the client's portal project once a payment is confirmed paid.

    Links the paid payment to the matching ``ClientProject`` (by explicit
    ``project_id``, else by phone+package against the latest pending project)
    and flips it to ``active`` so portal agents can be woken and run.

    Returns a dict describing the outcome; never raises.
    """
    from datetime import datetime, timezone
    from uuid import UUID as _UUID

    from sqlalchemy import select as _sel

    from src.models import ClientProject

    if not payment or payment.status != "paid":
        return {"activated": False, "reason": "payment not paid"}

    project = None

    if getattr(payment, "project_id", None):
        try:
            pid = _UUID(str(payment.project_id))
        except (ValueError, TypeError):
            pid = None
        if pid is not None:
            project = (
                await session.execute(_sel(ClientProject).where(ClientProject.id == pid))
            ).scalar_one_or_none()

    if project is None:
        # Legacy fallback: match the latest pending project on phone+package.
        query = _sel(ClientProject)
        if payment.customer_phone:
            query = query.where(ClientProject.phone == payment.customer_phone)
        else:
            query = query.where(ClientProject.email == payment.customer_email) if payment.customer_email else query
        query = query.where(ClientProject.package == payment.package)
        query = query.order_by(ClientProject.created_at.desc())
        project = (await session.execute(query.limit(1))).scalar_one_or_none()

    if project is None:
        return {"activated": False, "reason": "no matching project"}

    if project.status == "active":
        return {"activated": True, "already_active": True}

    project.status = "active"
    project.subscription_note = (
        f"activated by payment {payment.id} on {datetime.now(timezone.utc).isoformat()}"
    )
    await session.commit()
    return {"activated": True, "project_id": str(project.id)}
