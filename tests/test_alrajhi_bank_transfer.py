"""Customer bank transfer uses the published Al Rajhi account and an IBAN QR.

Card checkout stays closed. The QR is the compact IBAN, not a ZATCA tax code.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
import segno
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import Payment
from src.services import payments as pm
from src.services import transfer

IBAN = "SA5880000126608016363961"
ACCOUNT = "أحمد عبدالله غرم الله الزهراني"


def _iban_ok(iban: str) -> bool:
    rearr = iban[4:] + iban[:4]
    digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearr)
    return int(digits) % 97 == 1


def test_published_file_is_al_rajhi_and_opens_customer_transfer(monkeypatch):
    for key in ("PAYMENT_IBAN", "PAYMENT_ACCOUNT_NAME", "PAYMENT_BANK_NAME", "PAYMENT_BANK_NAME_EN"):
        monkeypatch.delenv(key, raising=False)
    raw = json.loads(transfer.CONTENT_FILE.read_text(encoding="utf-8"))
    assert raw["bank_name"] == "مصرف الراجحي"
    assert raw["account_name"] == ACCOUNT
    assert raw["iban"] == IBAN
    assert raw["swift"] == "RJHISARI"
    assert _iban_ok(IBAN)
    assert IBAN[4:6] == "80"
    details = transfer.bank_details()
    assert details["iban"] == IBAN
    assert details["swift"] == "RJHISARI"
    assert details["bank_name_en"] == "Al Rajhi Bank"
    assert transfer.has_bank_details() is True
    assert pm.customer_bank_transfer_enabled() is False
    caps = pm.capabilities()
    assert caps["card"] is False
    assert caps["methods"]["invoice"] is False
    assert caps["bank"] == {}


def test_invoice_qr_encodes_only_the_iban(monkeypatch):
    for key in ("PAYMENT_IBAN", "PAYMENT_ACCOUNT_NAME", "PAYMENT_BANK_NAME"):
        monkeypatch.delenv(key, raising=False)
    payment = Payment(
        id=uuid4(), amount=79000, currency="SAR", package="bidaya", status="invoice", total_halalas=79000
    )
    out = pm.transfer_instructions(payment)
    assert out["bank"] == {}
    assert out["qr_svg"] == ""
    assert out["iban_spaced"] == ""
    assert IBAN not in str(out)
    assert out["reference"]


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
    import httpx

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_unpaid_invoice_shows_account_reference_and_iban_qr(anon, maker, monkeypatch):
    for key in ("PAYMENT_IBAN", "PAYMENT_ACCOUNT_NAME", "PAYMENT_BANK_NAME"):
        monkeypatch.delenv(key, raising=False)
    async with maker() as session:
        payment = Payment(
            amount=79000, currency="SAR", package="bidaya", status="invoice", gateway="invoice", total_halalas=79000
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        pid = payment.id
        ref = str(pid)[:8].upper()
    page = await anon.get(f"/invoice/{pid}")
    assert page.status_code == 200
    assert IBAN not in page.text
    assert ACCOUNT not in page.text
    assert "مصرف الراجحي" not in page.text
    assert "RJHISARI" not in page.text
    assert ref in page.text
    assert "xfer-qr" not in page.text
    assert "QR (ZATCA TLV)" not in page.text
    english = await anon.get(f"/invoice/{pid}", cookies={"narjis_lang": "en"})
    assert "Al Rajhi Bank" not in english.text
    assert "IBAN" not in english.text
    assert ref in english.text
    assert 'dir="ltr"' in english.text
