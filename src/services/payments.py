from __future__ import annotations

import base64
import json
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
VAT_RATE = 0.15


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
        status="pending",
        gateway="invoice",
        description=description,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def initiate_moyasar(session: AsyncSession, payment: Payment, source: dict, callback_url: Optional[str] = None) -> dict:
    settings = get_settings()
    if not settings.moyasar_api_secret:
        raise PaymentError("Moyasar API secret not configured")

    payload = {
        "amount": payment.amount,
        "currency": "SAR",
        "description": payment.description or "النرجس للذكاء الاصطناعي",
        "callback_url": callback_url or settings.payment_success_url,
        "source": source,
        "metadata": {
            "payment_id": str(payment.id),
            "package": payment.package or "",
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            MOYASAR_API_URL,
            json=payload,
            headers={"Authorization": _auth_header(settings)},
        )

    if resp.status_code not in (200, 201):
        raise PaymentError(f"Moyasar error {resp.status_code}: {resp.text}")

    data = resp.json()
    payment.gateway = "moyasar"
    payment.gateway_payment_id = data.get("id")
    payment.gateway_source = data.get("source", {}).get("type") if isinstance(data.get("source"), dict) else None
    await session.commit()
    return data


async def verify_payment(session: AsyncSession, payment_id: UUID) -> Payment:
    result = await session.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise PaymentError("Payment not found")

    settings = get_settings()
    if not settings.moyasar_api_secret or not payment.gateway_payment_id:
        return payment

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{MOYASAR_API_URL}/{payment.gateway_payment_id}",
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
