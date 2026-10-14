from __future__ import annotations

import asyncio
import base64
import json
import logging
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

logger = logging.getLogger(__name__)

PACKAGES = catalog.PACKAGES  # compatible alias — amounts live in catalog only

MOYASAR_API_URL = "https://api.moyasar.com/v1/payments"
MOYASAR_INVOICES_URL = "https://api.moyasar.com/v1/invoices"
VAT_RATE = 0.15

from datetime import timedelta as _timedelta

# Access survives this long past ``current_period_end`` before the renewal
# job expires it (see src/services/renewals.py).
RENEWAL_GRACE = _timedelta(days=3)

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


def _validate_addons(addons) -> int:
    try:
        addons = int(addons or 0)
    except (TypeError, ValueError):
        raise PaymentError("addons must be an integer")
    if addons < 0 or addons > catalog.MAX_ADDON_AGENTS:
        raise PaymentError(f"addons must be between 0 and {catalog.MAX_ADDON_AGENTS}")
    return addons


def _validate_packs(packs, name: str) -> int:
    try:
        packs = int(packs or 0)
    except (TypeError, ValueError):
        raise PaymentError(f"{name} must be an integer")
    if packs < 0 or packs > catalog.MAX_USAGE_PACKS:
        raise PaymentError(f"{name} must be between 0 and {catalog.MAX_USAGE_PACKS}")
    return packs


def _validate_period(billing_period: Optional[str]) -> str:
    period = (billing_period or catalog.DEFAULT_BILLING_PERIOD).strip().lower()
    if period not in catalog.BILLING_PERIODS:
        raise PaymentError(f"Unknown billing period: {billing_period}")
    return period


def package_amount(package: str, billing_period: Optional[str] = None, addons: int = 0) -> int:
    """Pre-VAT halalas for one billing period (monthly, or annual = 10 months)."""
    # A lead's suggested domain (social/ecommerce/content/growth) is billed at
    # the tier that staffs a full domain team; tier keys pass through.
    if package in catalog.DOMAINS:
        package = catalog.resolve_tier(package)
    if package not in catalog.PACKAGES:
        raise PaymentError(f"Unknown package: {package}")
    return catalog.plan_amount(package, _validate_period(billing_period), _validate_addons(addons))


def setup_fee_amount(package: str, billing_period: Optional[str] = None, renewal: bool = False, founding: bool = False) -> int:
    """One-time setup fee (halalas, pre-VAT) a new order adds; 0 when waived."""
    if package in catalog.DOMAINS:
        package = catalog.resolve_tier(package)
    return catalog.setup_fee(package, _validate_period(billing_period), renewal=renewal, founding=founding)


def usage_packs_amount(conversation_packs: int = 0, voice_packs: int = 0, billing_period: Optional[str] = None) -> int:
    """Pre-VAT halalas for usage add-on packs over one billing period (validated)."""
    return catalog.usage_packs_amount(
        _validate_packs(conversation_packs, "conversation_packs"),
        _validate_packs(voice_packs, "voice_packs"),
        _validate_period(billing_period),
    )


def period_months(billing_period: Optional[str]) -> int:
    """Months of access one paid invoice buys (1 or 12)."""
    return catalog.BILLING_PERIODS[catalog.resolve_billing_period(billing_period)]["months_granted"]


def add_months(dt, months: int):
    """Calendar-month addition, clamped to the last day (Jan 31 + 1 = Feb 28/29)."""
    import calendar

    month0 = dt.month - 1 + months
    year = dt.year + month0 // 12
    month = month0 % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def order_description(package: str, billing_period: str, addons: int, discount_pct: int = 0, renewal: bool = False, setup_fee: int = 0,
                      conversation_packs: int = 0, voice_packs: int = 0, founding: bool = False) -> str:
    pkg = catalog.PACKAGES.get(package) or catalog.LEGACY_TIERS[package]
    description = f"باقة {pkg['name']} - النرجس للذكاء الاصطناعي"
    if addons:
        description += f" + {addons} وكيل إضافي"
    if conversation_packs:
        description += f" + {conversation_packs} × باقة ١٬٠٠٠ محادثة إضافية"
    if voice_packs:
        description += f" + {voice_packs} × باقة ١٠٠ دقيقة صوت إضافية"
    description += " (اشتراك سنوي: 12 شهراً بسعر 10)" if billing_period == "annual" else " (اشتراك شهري)"
    if renewal:
        description += " - تجديد"
    if founding:
        description += f" (سعر العملاء المؤسسين: خصم {discount_pct}%، بدون رسوم إعداد)"
    elif discount_pct:
        description += f" (خصم الإطلاق {discount_pct}%)"
    if setup_fee:
        description += f" + رسوم إعداد لمرة واحدة {setup_fee // 100} ر.س"
    return description


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
            "paypal": ["PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_MODE=live", "PAYPAL_WEBHOOK_ID"],
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
    billing_period: Optional[str] = None,
    addons: int = 0,
    is_renewal: bool = False,
    conversation_packs: int = 0,
    voice_packs: int = 0,
    founding: Optional[bool] = False,
) -> Payment:
    if package in catalog.DOMAINS:
        package = catalog.resolve_tier(package)
    # Grandfathering: a legacy tier can only be renewed (at its old price),
    # never bought new.
    legacy_renewal = is_renewal and catalog.GRANDFATHER_RENEWALS and catalog.is_legacy_tier(package)
    if package not in catalog.PACKAGES and not legacy_renewal:
        raise PaymentError(f"Unknown package: {package}")
    period = _validate_period(billing_period)
    addons = _validate_addons(addons)
    conversation_packs = _validate_packs(conversation_packs, "conversation_packs")
    voice_packs = _validate_packs(voice_packs, "voice_packs")

    # Founding offer (first 15 customers): founding=None auto-applies it while
    # a seat is free (checkout, owner payment links, renewals of a founding
    # project); True/False force it. It replaces any promo
    # code (no stacking) and waives the setup fee.
    if founding is None:
        from src.services import founding as _founding

        project = None
        if project_id is not None:
            from src.models import ClientProject

            project = (await session.execute(
                select(ClientProject).where(ClientProject.id == project_id)
            )).scalar_one_or_none()
        founding = await _founding.eligible_for_order(session, package, is_renewal=is_renewal, project=project)
    founding = bool(founding) and package in catalog.PACKAGES

    # ``amount`` is the whole period's pre-VAT base (annual = 10 x monthly)
    # plus usage add-on packs (never discounted) plus the one-time setup fee
    # on a first monthly order (never discounted by a promo, never on
    # renewals, annual or founding); VAT, the Moyasar charge and the gateway
    # amount check all derive from it.
    if founding:
        amount = catalog.founding_amount(package, period, addons)
        discount_pct = catalog.FOUNDING_OFFER["annual_pct" if period == "annual" else "monthly_pct"]
    else:
        amount, discount_pct = apply_promo(catalog.plan_amount(package, period, addons), promo)
    amount += catalog.usage_packs_amount(conversation_packs, voice_packs, period)
    fee = catalog.setup_fee(package, period, renewal=is_renewal, founding=founding)
    amount += fee
    description = order_description(package, period, addons, discount_pct, renewal=is_renewal, setup_fee=fee,
                                    conversation_packs=conversation_packs, voice_packs=voice_packs, founding=founding)

    payment = Payment(
        amount=amount,
        currency="SAR",
        package=package,
        billing_period=period,
        addon_agents=addons,
        addon_conversation_packs=conversation_packs,
        addon_voice_packs=voice_packs,
        founding=founding,
        is_renewal=is_renewal,
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
    success_url: Optional[str] = None,
    back_url: Optional[str] = None,
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
    #
    # For invoices, callback_url is NOT where the buyer returns: it is a
    # server-to-server POST from Moyasar. It used to point at the GET-only
    # /payment/success page, so the buyer was never sent back (nothing was
    # captured or activated) and Moyasar's notification answered 405.
    # success_url / back_url are the buyer's return; callback_url is the webhook.
    payload = {
        "amount": charge,
        "currency": "SAR",
        "description": payment.description or "النرجس للذكاء الاصطناعي",
        "success_url": success_url or settings.payment_success_url,
        "back_url": back_url or settings.payment_failure_url,
        "metadata": {"order_id": str(payment.id)},
    }
    if callback_url:
        payload["callback_url"] = callback_url

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
    if payment.status in ("paid", REVIEW_STATUS):
        # Idempotent: a settled or flagged order is never re-decided by a poll.
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
    apply_gateway_status(payment, data)
    src = data.get("source", {})
    if isinstance(src, dict):
        payment.gateway_source = src.get("type", payment.gateway_source)

    await session.commit()
    return payment


REVIEW_STATUS = "review"


def expected_charge(payment: Payment) -> int:
    """Halalas Moyasar must report for this order: the VAT-inclusive total."""
    return total_with_vat(payment.amount)


def gateway_amount_matches(payment: Payment, data: dict) -> bool:
    """The gateway's amount (halalas) and currency must equal the order's total in SAR."""
    try:
        amount = int(data.get("amount"))
    except (TypeError, ValueError):
        return False
    currency = str(data.get("currency") or "").upper()
    return amount == expected_charge(payment) and currency == "SAR"


def apply_gateway_status(payment: Payment, data: dict) -> None:
    """Map a Moyasar invoice/payment object onto the order.

    A ``paid`` verdict is only trusted when the amount and currency match the
    order; anything else is parked as ``review`` for the owner and never paid.
    """
    if payment.status == "paid":
        return
    status = data.get("status")
    if status == "paid":
        if gateway_amount_matches(payment, data):
            payment.status = "paid"
        else:
            logger.warning(
                "moyasar amount mismatch for %s: got %s %s, expected %s SAR",
                payment.id, data.get("amount"), data.get("currency"), expected_charge(payment),
            )
            payment.status = REVIEW_STATUS
    elif status in ("failed", "canceled", "expired"):
        payment.status = "failed"
    elif status == "authorized":
        payment.status = "authorized"
    else:
        payment.status = status or payment.status


async def handle_moyasar_webhook(session: AsyncSession, event: dict) -> dict:
    """Apply a verified Moyasar webhook event. Safe to receive more than once."""
    event_type = str(event.get("type") or "")
    if event_type not in ("payment_paid", "payment_failed"):
        return {"ok": True, "ignored": event_type or "unknown"}

    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

    payment = None
    order_id = metadata.get("order_id")
    if order_id:
        try:
            payment = (
                await session.execute(select(Payment).where(Payment.id == UUID(str(order_id))))
            ).scalar_one_or_none()
        except ValueError:
            payment = None
    if payment is None:
        refs = [r for r in (data.get("invoice_id"), data.get("id")) if r]
        if refs:
            payment = (
                await session.execute(select(Payment).where(Payment.gateway_payment_id.in_(refs)))
            ).scalars().first()
    if payment is None:
        return {"ok": True, "ignored": "unknown order"}

    if payment.status == "paid":
        return {"ok": True, "payment_id": str(payment.id), "status": "paid", "already": True}

    # The body is only a hint: re-fetch the record with the secret key and
    # decide from Moyasar's own answer (amount + currency checked there).
    payment = await verify_payment(session, payment.id)
    return {"ok": True, "payment_id": str(payment.id), "status": payment.status, "already": False}


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
#
# PayPal cannot settle SAR. Prices are SAR incl. 15% VAT, so the PayPal order is
# raised in USD at the fixed riyal peg (PAYPAL_SAR_PER_USD, default 3.75). The
# SAR total stays on ``Payment.amount`` (pre-VAT base, as for Moyasar); the USD
# cents PayPal must report are stored on ``charge_currency``/``charge_amount``
# and every capture is checked against them before the order is marked paid.

PAYPAL_CURRENCY = "USD"
PAYPAL_WEBHOOK_EVENTS = (
    "CHECKOUT.ORDER.APPROVED",
    "PAYMENT.CAPTURE.COMPLETED",
    "PAYMENT.CAPTURE.DENIED",
    "PAYMENT.CAPTURE.REVERSED",
    "PAYMENT.CAPTURE.REFUNDED",
)


def _paypal_base_url(settings) -> str:
    return "https://api-m.paypal.com" if settings.paypal_mode == "live" else "https://api-m.sandbox.paypal.com"


def sar_halalas_to_usd_cents(halalas: int, sar_per_usd: Optional[float] = None) -> int:
    """Convert SAR halalas to USD cents at the peg, rounded half-up to the cent."""
    from decimal import ROUND_HALF_UP, Decimal

    rate = Decimal(str(sar_per_usd if sar_per_usd is not None else get_settings().paypal_sar_per_usd))
    if rate <= 0:
        raise PaymentError("PAYPAL_SAR_PER_USD must be positive")
    return int((Decimal(int(halalas)) / rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def paypal_quote(payment: Payment) -> dict:
    """SAR total (incl. VAT) and the USD amount the buyer will be charged."""
    sar = expected_charge(payment)
    usd = sar_halalas_to_usd_cents(sar)
    return {
        "total_sar": sar,
        "amount_usd": usd,
        "amount_usd_display": f"{usd / 100:.2f}",
        "currency": PAYPAL_CURRENCY,
        "sar_per_usd": get_settings().paypal_sar_per_usd,
    }


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
        raise PaymentError(f"PayPal auth error {resp.status_code}")
    try:
        return resp.json()["access_token"]
    except (KeyError, ValueError):
        raise PaymentError("PayPal token response malformed")


async def create_paypal_order(
    session: AsyncSession,
    payment: Payment,
    return_url: str,
    cancel_url: str,
    amount_halalas: Optional[int] = None,
) -> dict:
    """Create a PayPal Orders v2 order (intent CAPTURE) in USD for this payment.

    ``amount_halalas`` is accepted for compatibility but must equal the
    VAT-inclusive total; the charge is always derived from the order itself.
    """
    if payment.status == "paid":
        raise PaymentError("Payment already paid")
    sar_total = expected_charge(payment)
    if amount_halalas is not None and int(amount_halalas) != sar_total:
        raise PaymentError("PayPal amount does not match the order total")
    settings = get_settings()
    usd_cents = sar_halalas_to_usd_cents(sar_total)
    token = await _paypal_token(settings)
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": str(payment.id),
            "custom_id": str(payment.id),
            "invoice_id": reference(payment),
            "description": (payment.description or "Al-Narjis AI")[:127],
            "amount": {"currency_code": PAYPAL_CURRENCY, "value": f"{usd_cents / 100:.2f}"},
        }],
        "payment_source": {"paypal": {"experience_context": {
            "return_url": return_url,
            "cancel_url": cancel_url,
            "brand_name": "Al-Narjis AI",
            "user_action": "PAY_NOW",
            "shipping_preference": "NO_SHIPPING",
        }}},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_paypal_base_url(settings)}/v2/checkout/orders",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                # Same payment + amount -> PayPal returns the same order on retry.
                "PayPal-Request-Id": f"create-{payment.id}-{usd_cents}",
            },
        )
    if resp.status_code not in (200, 201):
        raise PaymentError(f"PayPal create error {resp.status_code}")

    data = resp.json()
    payment.gateway = "paypal"
    payment.status = "pending"
    payment.gateway_payment_id = data.get("id")
    payment.charge_currency = PAYPAL_CURRENCY
    payment.charge_amount = usd_cents
    await session.commit()

    links = data.get("links") or []
    approval = next((l for l in links if l.get("rel") in ("payer-action", "approve")), None)
    return {
        "order_id": data.get("id"),
        "approval_url": approval.get("href") if approval else None,
        "amount_usd": usd_cents,
        "currency": PAYPAL_CURRENCY,
    }


async def _paypal_request(method: str, path: str, *, json_body: Optional[dict] = None, request_id: Optional[str] = None) -> httpx.Response:
    settings = get_settings()
    token = await _paypal_token(settings)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if request_id:
        headers["PayPal-Request-Id"] = request_id
    async with httpx.AsyncClient(timeout=30) as client:
        return await client.request(method, f"{_paypal_base_url(settings)}{path}", json=json_body, headers=headers)


async def get_paypal_order(order_id: str) -> dict:
    resp = await _paypal_request("GET", f"/v2/checkout/orders/{order_id}")
    if resp.status_code != 200:
        raise PaymentError(f"PayPal order fetch error {resp.status_code}")
    return resp.json()


async def capture_paypal_order(order_id: str) -> dict:
    """Capture an approved order. Already captured -> the current order state."""
    resp = await _paypal_request(
        "POST", f"/v2/checkout/orders/{order_id}/capture", request_id=f"capture-{order_id}",
    )
    if resp.status_code in (200, 201):
        return resp.json()
    if resp.status_code == 422 and "ORDER_ALREADY_CAPTURED" in resp.text:
        return await get_paypal_order(order_id)
    raise PaymentError(f"PayPal capture error {resp.status_code}")


def _paypal_captures(order: dict) -> list[dict]:
    out: list[dict] = []
    for unit in order.get("purchase_units") or []:
        caps = ((unit.get("payments") or {}).get("captures")) or []
        out.extend(c for c in caps if isinstance(c, dict))
    return out


def paypal_capture_matches(payment: Payment, order: dict, capture: dict) -> bool:
    """Captured currency/amount and order ownership must equal what we created."""
    if order.get("id") and payment.gateway_payment_id and order.get("id") != payment.gateway_payment_id:
        return False
    units = order.get("purchase_units") or []
    custom = next((u.get("custom_id") or u.get("reference_id") for u in units if u.get("custom_id") or u.get("reference_id")), None)
    if custom is None:
        custom = capture.get("custom_id")
    if custom is not None and str(custom) != str(payment.id):
        return False
    amount = capture.get("amount") or {}
    if str(amount.get("currency_code") or "").upper() != PAYPAL_CURRENCY:
        return False
    if (payment.charge_currency or "").upper() != PAYPAL_CURRENCY or payment.charge_amount is None:
        return False
    try:
        from decimal import Decimal

        cents = int((Decimal(str(amount.get("value"))) * 100).to_integral_value())
    except Exception:  # noqa: BLE001
        return False
    return cents == int(payment.charge_amount) == sar_halalas_to_usd_cents(expected_charge(payment))


def apply_paypal_order(payment: Payment, order: dict) -> None:
    """Map a PayPal order (after capture or fetch) onto the payment.

    Paid only when a COMPLETED capture matches the stored USD amount; a
    completed capture that does not match is parked as ``review``.
    """
    if payment.status == "paid":
        return
    caps = _paypal_captures(order)
    completed = [c for c in caps if c.get("status") == "COMPLETED"]
    if completed:
        if all(paypal_capture_matches(payment, order, c) for c in completed) and len(completed) == 1:
            payment.status = "paid"
            payment.gateway_source = "paypal"
        else:
            logger.warning("paypal capture mismatch for %s (order %s)", payment.id, order.get("id"))
            payment.status = REVIEW_STATUS
        return
    if any(c.get("status") in ("DECLINED", "FAILED") for c in caps) or order.get("status") == "VOIDED":
        payment.status = "failed"
    elif any(c.get("status") == "PENDING" for c in caps):
        payment.status = "authorized"  # e.g. eCheck / held for review by PayPal


async def finalize_paypal_payment(session: AsyncSession, payment: Payment) -> Payment:
    """Capture (or re-read) the PayPal order and settle the payment. Idempotent."""
    if payment.status in ("paid", REVIEW_STATUS) or not payment.gateway_payment_id:
        return payment
    order = await get_paypal_order(payment.gateway_payment_id)
    if order.get("status") == "APPROVED":
        order = await capture_paypal_order(payment.gateway_payment_id)
    apply_paypal_order(payment, order)
    await session.commit()
    return payment


async def verify_paypal_webhook(headers, event: dict) -> bool:
    """Ask PayPal to verify the transmission signature for this webhook id."""
    settings = get_settings()
    if not settings.paypal_webhook_id:
        return False
    needed = {
        "auth_algo": "paypal-auth-algo",
        "cert_url": "paypal-cert-url",
        "transmission_id": "paypal-transmission-id",
        "transmission_sig": "paypal-transmission-sig",
        "transmission_time": "paypal-transmission-time",
    }
    body = {k: headers.get(h) for k, h in needed.items()}
    if not all(body.values()):
        return False
    body["webhook_id"] = settings.paypal_webhook_id
    body["webhook_event"] = event
    resp = await _paypal_request("POST", "/v1/notifications/verify-webhook-signature", json_body=body)
    if resp.status_code != 200:
        raise PaymentError(f"PayPal webhook verify error {resp.status_code}")
    return (resp.json() or {}).get("verification_status") == "SUCCESS"


async def handle_paypal_webhook(session: AsyncSession, event: dict) -> dict:
    """Apply a verified PayPal event. The body is a hint; the order is re-fetched."""
    event_type = str(event.get("event_type") or "")
    if event_type not in PAYPAL_WEBHOOK_EVENTS:
        return {"ok": True, "ignored": event_type or "unknown"}
    resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}

    order_id = None
    payment_ref = None
    if event_type == "CHECKOUT.ORDER.APPROVED":
        order_id = resource.get("id")
        units = resource.get("purchase_units") or []
        payment_ref = next((u.get("custom_id") for u in units if u.get("custom_id")), None)
    else:
        payment_ref = resource.get("custom_id")
        related = (resource.get("supplementary_data") or {}).get("related_ids") or {}
        order_id = related.get("order_id")

    payment = None
    if payment_ref:
        try:
            payment = (await session.execute(select(Payment).where(Payment.id == UUID(str(payment_ref))))).scalar_one_or_none()
        except ValueError:
            payment = None
    if payment is None and order_id:
        payment = (await session.execute(select(Payment).where(Payment.gateway_payment_id == order_id))).scalars().first()
    if payment is None or payment.gateway != "paypal":
        return {"ok": True, "ignored": "unknown order"}
    if order_id and payment.gateway_payment_id and order_id != payment.gateway_payment_id:
        return {"ok": True, "ignored": "order mismatch"}

    if event_type in ("PAYMENT.CAPTURE.REVERSED", "PAYMENT.CAPTURE.REFUNDED"):
        # Money left after activation: never auto-deactivate, flag for the owner.
        logger.warning("paypal %s for payment %s", event_type, payment.id)
        return {"ok": True, "payment_id": str(payment.id), "status": payment.status, "already": True, "alert": event_type}

    if payment.status == "paid":
        return {"ok": True, "payment_id": str(payment.id), "status": "paid", "already": True}

    payment = await finalize_paypal_payment(session, payment)
    return {"ok": True, "payment_id": str(payment.id), "status": payment.status, "already": False}


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

    # Idempotent: the same paid order never extends the period twice.
    if project.last_payment_id is not None and str(project.last_payment_id) == str(payment.id):
        return {"activated": True, "already_active": True, "project_id": str(project.id)}

    now = datetime.now(timezone.utc)
    period = catalog.resolve_billing_period(getattr(payment, "billing_period", None))
    current_end = project.current_period_end
    if current_end is not None and current_end.tzinfo is None:
        current_end = current_end.replace(tzinfo=timezone.utc)
    # A renewal paid early (or inside the grace window) extends from the old end
    # so the client never loses or gains days; a lapsed one restarts from now.
    start = current_end if (current_end is not None and current_end > now - RENEWAL_GRACE) else now
    project.current_period_end = add_months(start, period_months(period))
    project.billing_period = period
    project.addon_agents = int(getattr(payment, "addon_agents", 0) or 0)
    project.addon_conversation_packs = int(getattr(payment, "addon_conversation_packs", 0) or 0)
    project.addon_voice_packs = int(getattr(payment, "addon_voice_packs", 0) or 0)
    if getattr(payment, "founding", False):
        from src.services import founding as _founding

        _founding.mark_project(project, payment, now)
    staffed = await staff_project(session, project)
    project.last_payment_id = payment.id
    if project.renewal_payment_id is not None and str(project.renewal_payment_id) == str(payment.id):
        project.renewal_payment_id = None
    was_active = project.status == "active"
    project.status = "active"
    verb = "renewed" if was_active or getattr(payment, "is_renewal", False) else "activated"
    project.subscription_note = (
        f"{verb} by payment {payment.id} on {now.isoformat()} "
        f"({period}) until {project.current_period_end.isoformat()}"
    )
    await session.commit()
    return {
        "activated": True,
        "already_active": was_active,
        "project_id": str(project.id),
        "current_period_end": project.current_period_end.isoformat(),
        "staffed": staffed,
    }


async def staff_project(session: AsyncSession, project) -> list[str]:
    """Make sure the project has CEO + tier allowance + add-on agents.

    Paid add-ons used to be billed but never staffed. This tops the team up
    (never removes agents, so a downgrade keeps existing work) and returns the
    slugs that were newly added. Does not commit.
    """
    from sqlalchemy import select as _sel

    from src.models import ClientAgent

    rows = (
        await session.execute(_sel(ClientAgent).where(ClientAgent.project_id == project.id))
    ).scalars().all()
    have = [r.slug for r in rows]
    target = catalog.staff_team(project.package, int(project.addon_agents or 0), preferred=have)
    added = [slug for slug in target if slug not in have]
    for slug in added:
        session.add(ClientAgent(project_id=project.id, slug=slug, status="dormant"))
    if added:
        await session.flush()
    return added
