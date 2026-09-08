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

# Packages in halalas (SAR * 100)
PACKAGES = {
    "social": {"name": "سوشيال ميديا", "amount": 150000},
    "ecommerce": {"name": "متاجر إلكترونية", "amount": 100000},
    "content": {"name": "تسويق محتوى", "amount": 120000},
    "growth": {"name": "نمو الأعمال", "amount": 80000},
}

MOYASAR_API_URL = "https://api.moyasar.com/v1/payments"


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
) -> Payment:
    if package not in PACKAGES:
        raise PaymentError(f"Unknown package: {package}")

    settings = get_settings()
    amount = PACKAGES[package]["amount"]
    name = PACKAGES[package]["name"]

    payment = Payment(
        amount=amount,
        currency="SAR",
        package=package,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email,
        status="pending",
        gateway="moyasar" if settings.moyasar_api_secret else "invoice",
        description=f"باقة {name} - النرجس للذكاء الاصطناعي",
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def initiate_moyasar(session: AsyncSession, payment: Payment, source: dict) -> dict:
    settings = get_settings()
    if not settings.moyasar_api_secret:
        raise PaymentError("Moyasar API secret not configured")

    payload = {
        "amount": payment.amount,
        "currency": "SAR",
        "description": payment.description or "النرجس للذكاء الاصطناعي",
        "callback_url": settings.payment_success_url,
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
