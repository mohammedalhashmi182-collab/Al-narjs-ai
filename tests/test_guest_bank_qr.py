"""Guest bank-transfer QR on the invoice, driven by PAYMENT_* env vars."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import Payment
from src.services import payments as pm
from src.services import transfer

DUMMY_IBAN = "SA0000000000000000000000"


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def anon(maker):
    from src.main import app

    app.state.session_factory = maker
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


def _arm(monkeypatch, *, bank_en=None):
    monkeypatch.setenv("PAYMENT_IBAN", "SA00 0000 0000 0000 0000 0000")
    monkeypatch.setenv("PAYMENT_ACCOUNT_NAME", "Dummy Holder")
    monkeypatch.setenv("PAYMENT_BANK_NAME", "مصرف تجريبي")
    if bank_en:
        monkeypatch.setenv("PAYMENT_BANK_NAME_EN", bank_en)
    else:
        monkeypatch.delenv("PAYMENT_BANK_NAME_EN", raising=False)


def test_incomplete_or_invalid_account_hides_the_qr(monkeypatch):
    monkeypatch.setenv("PAYMENT_IBAN", DUMMY_IBAN)
    monkeypatch.setenv("PAYMENT_ACCOUNT_NAME", "Dummy Holder")
    monkeypatch.delenv("PAYMENT_BANK_NAME", raising=False)
    assert transfer.bank_details() == {}
    monkeypatch.setenv("PAYMENT_BANK_NAME", "Al Rajhi Bank")
    monkeypatch.setenv("PAYMENT_IBAN", "NOT-AN-IBAN")
    assert transfer.bank_details() == {}


def test_qr_payload_is_the_iban_and_the_page_keeps_amount_and_reference(monkeypatch):
    _arm(monkeypatch)
    payment = Payment(id=uuid4(), amount=79000, currency="SAR", package="bidaya", status="invoice", total_halalas=79000)
    out = pm.transfer_instructions(payment)
    assert out["bank"]["bank_name"] == "مصرف تجريبي"
    assert "bank_name_en" not in out["bank"]
    assert "xfer-qr-svg" in out["qr_svg"]
    payload = transfer.transfer_qr_payload(
        bank=out["bank"], amount_sar=out["amount_text"], reference=out["reference"], plan=out["plan_en"]
    )
    assert payload == DUMMY_IBAN
    assert out["amount_text"] not in payload and out["reference"] not in payload
    assert out["amount_text"] and out["reference"]
    assert "ZATCA" not in out["qr_svg"]


async def test_english_invoice_is_ltr_and_arabic_invoice_keeps_rtl(anon, maker, monkeypatch):
    _arm(monkeypatch, bank_en="Example Bank")
    async with maker() as session:
        payment = Payment(amount=79000, currency="SAR", package="bidaya", status="invoice", gateway="invoice", total_halalas=79000)
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        pid = payment.id
    ar = await anon.get(f"/invoice/{pid}")
    en = await anon.get(f"/invoice/{pid}", cookies={"narjis_lang": "en"})
    assert ar.status_code == 200 and 'dir="rtl"' in ar.text
    assert "تواصل معنا للدفع" not in ar.text
    assert "نسخ الآيبان" in ar.text and "مصرف تجريبي" in ar.text
    assert "Example Bank" not in ar.text
    assert en.status_code == 200 and "Contact us to pay" not in en.text
    assert "Copy IBAN" in en.text and "Example Bank" in en.text and 'dir="ltr"' in en.text
    assert "xfer-qr" in ar.text and "xfer-qr" in en.text


async def test_receipt_is_stored_for_the_owner_and_does_not_mark_paid(anon, maker, monkeypatch):
    from src.core.owner_auth import make_session_token

    _arm(monkeypatch)
    async with maker() as session:
        payment = Payment(
            amount=79000, currency="SAR", package="bidaya", status="invoice", gateway="invoice",
            total_halalas=79000, refund_consent_at=None,
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        pid = payment.id
    jpeg = b"\xff\xd8\xff" + b"not-a-real-photo"
    missing = await anon.post(f"/api/payments/{pid}/transfer-receipt", files={"file": ("r.jpg", jpeg, "image/jpeg")})
    assert missing.status_code == 422
    uploaded = await anon.post(
        f"/api/payments/{pid}/transfer-receipt",
        data={"refund_consent": "true"},
        files={"file": ("r.jpg", jpeg, "image/jpeg")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["recorded"] is True
    assert uploaded.json()["status"] != "paid"
    blocked = await anon.get(f"/api/owner/payments/{pid}/transfer-receipt")
    assert blocked.status_code in (401, 403)
    owner = await anon.get(
        f"/api/owner/payments/{pid}/transfer-receipt",
        cookies={"narjis_owner": make_session_token()},
    )
    assert owner.status_code == 200
    assert owner.content.startswith(b"\xff\xd8\xff")
    assert owner.headers["content-type"].startswith("image/jpeg")
    rejected = await anon.post(
        f"/api/payments/{pid}/transfer-receipt",
        data={"refund_consent": "true"},
        files={"file": ("r.exe", b"MZ-not-an-image", "application/octet-stream")},
    )
    assert rejected.status_code == 400
