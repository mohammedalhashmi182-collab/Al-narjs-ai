"""VAT rate comes from settings/env VAT_RATE (default 0: operator not VAT-registered)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.config import settings as st
from src.db.session import Base
from src.services import payments as pm
from src.services import zatca


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def vat0(monkeypatch):
    monkeypatch.setenv("VAT_RATE", "0")


def test_default_setting_is_zero():
    assert type(st).model_fields["vat_rate"].default == 0


def test_zero_rate_total_equals_price(vat0):
    assert pm.vat_rate() == 0 and not pm.vat_enabled()
    assert pm.vat_amount(100_000) == 0
    assert pm.total_with_vat(100_000) == 100_000  # 1000 SAR -> 1000 SAR


def test_legacy_rate_still_computes_1150(vat15):
    assert pm.vat_enabled() and pm.vat_percent() == 15
    assert pm.total_with_vat(100_000) == 115_000  # 1000 SAR -> 1150 SAR


def test_zero_rate_invoice_lines_have_no_vat_and_no_tax_qr(vat0):
    lines, subtotal, vat_total, total = zatca.with_vat([{"name": "x", "qty": 1, "net": 100_000}])
    assert vat_total == 0 and total == subtotal == 100_000
    assert zatca.title_ar() == "فاتورة" and zatca.title_en() == "Invoice"
    assert zatca.qr_tlv_base64("s", "300000000000003", datetime.now(timezone.utc), 100_000, 0) == ""
    assert not any("SELLER_VAT_NUMBER" in m for m in zatca.readiness()["missing"])


async def test_zero_rate_invoice_page_is_plain_invoice(vat0, maker, monkeypatch):
    import httpx

    from src.main import app

    monkeypatch.setattr(st, "seller_vat_number", None)
    app.state.session_factory = maker
    async with maker() as s:
        p = await pm.create_payment(s, "bidaya", "a", "0555000001", None, founding=False)
        p.status = "paid"
        await s.commit()
        await zatca.ensure_invoice(s, p)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        ar = await c.get(f"/invoice/{p.id}")
        en = await c.get(f"/invoice/{p.id}?lang=en")
    assert ar.status_code == 200
    for r in (ar, en):
        assert "فاتورة ضريبية" not in r.text and "Tax Invoice" not in r.text
        assert "15%" not in r.text and "ZATCA" not in r.text
        assert "الرقم الضريبي" not in r.text and "VAT No." not in r.text
    assert "ضريبة القيمة المضافة" not in ar.text


async def test_zero_rate_portal_js_uses_setting(vat0):
    import httpx

    from src.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/portal")
    if r.status_code == 200 and "coSummary" in r.text:
        assert "after * 0.15" not in r.text
        assert "const VAT_RATE = 0.0;" in r.text


async def test_plan_icons_have_fas_prefix():
    import httpx

    from src.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/portal/packages")
    body = r.text
    for ic in ("fa-comments", "fa-seedling", "fa-building"):
        if ic in body:
            assert f"fas {ic}" in body
