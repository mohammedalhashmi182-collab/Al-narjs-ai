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
        c.cookies.set("narjis_lang", "en")
        en = await c.get(f"/invoice/{p.id}")
    assert "Item" in en.text and ar.status_code == 200
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


# ---------------------------------------------------------------- QA round 2

@pytest.mark.parametrize("raw", ["15", "1.5", "-0.1", "abc", "nan"])
def test_out_of_range_rate_is_rejected(monkeypatch, raw, caplog):
    monkeypatch.setenv("VAT_RATE", raw)
    with caplog.at_level("WARNING"):
        assert pm.vat_rate() == 0.0
    assert "VAT_RATE" in caplog.text


def test_rate_one_is_allowed(monkeypatch):
    monkeypatch.setenv("VAT_RATE", "1")
    assert pm.vat_rate() == 1.0


async def test_rate_15_charges_plan_price(monkeypatch, maker):
    monkeypatch.setenv("VAT_RATE", "15")
    async with maker() as s:
        p = await pm.create_payment(s, "bidaya", "a", "0555000001", None, founding=False)
    base = int(p.amount)
    assert pm.payment_total(p) == base and pm.expected_charge(p) == base
    from src.services import catalog

    assert catalog.PACKAGES["bidaya"]["amount"] == 79_000
    assert pm.total_with_vat(79_000) == 79_000  # 790 plan -> 790 charged


async def test_payment_created_at_15_confirms_after_switch(monkeypatch, maker):
    monkeypatch.setenv("VAT_RATE", "0.15")
    async with maker() as s:
        p = await pm.create_payment(s, "bidaya", "a", "0555000001", None, founding=False)
    owed = pm.payment_total(p)
    assert owed == int(p.amount) + round(int(p.amount) * 0.15)
    monkeypatch.setenv("VAT_RATE", "0")
    assert pm.expected_charge(p) == owed
    assert pm.gateway_amount_matches(p, {"amount": owed, "currency": "SAR"})
    assert not pm.gateway_amount_matches(p, {"amount": int(p.amount), "currency": "SAR"})


async def test_stored_tax_invoice_renders_from_stored_amounts(monkeypatch, maker):
    import httpx

    from src.main import app

    monkeypatch.setattr(st, "seller_vat_number", "310122393500003")
    monkeypatch.setenv("VAT_RATE", "0.15")
    app.state.session_factory = maker
    async with maker() as s:
        p = await pm.create_payment(s, "bidaya", "a", "0555000001", None, founding=False)
        p.status = "paid"
        await s.commit()
        inv = await zatca.ensure_invoice(s, p)
    assert inv.vat_total > 0 and inv.qr_tlv
    monkeypatch.setenv("VAT_RATE", "0")  # owner switches VAT off afterwards
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        ar = await c.get(f"/invoice/{p.id}")
        en = await c.get(f"/invoice/{p.id}?lang=en")
    assert "فاتورة ضريبية مبسطة" in ar.text and "ZATCA" in ar.text and "310122393500003" in ar.text
    assert f"{inv.vat_total / 100:.2f}" in ar.text and f"{inv.total / 100:.2f}" in ar.text
    assert "Simplified Tax Invoice" in en.text and f"{inv.total / 100:.2f}" in en.text


def test_messages_mention_vat_only_when_charged(monkeypatch):
    from types import SimpleNamespace

    from src.services import collections, renewals

    proj = SimpleNamespace(client_name="c", package="bidaya")
    end = datetime(2026, 11, 1, tzinfo=timezone.utc)
    p0 = SimpleNamespace(id="x" * 36, amount=79_000, total_halalas=79_000, billing_period="monthly")
    p15 = SimpleNamespace(id="x" * 36, amount=79_000, total_halalas=90_850, billing_period="monthly")
    for p, has in ((p0, False), (p15, True)):
        texts = [collections.reminder_text("d-5", proj, p, end, "http://t"),
                 collections.overage_text(proj, p, "http://t"),
                 renewals.reminder_text(proj, p, end, "http://t")]
        for t in texts:
            assert ("ضريبة" in t) is has, t


def test_catalog_has_no_tax_invoice_feature():
    from src.services import catalog

    blob = repr(catalog.PACKAGES)
    assert "فواتير ضريبية" not in blob and "Tax invoices" not in blob


@pytest.mark.parametrize("lang", ["ar", "en"])
@pytest.mark.parametrize("path", ["/pricing", "/", "/home", "/portal"])
async def test_public_pages_have_no_vat_wording_at_zero(vat0, path, lang):
    import httpx

    from src.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t",
                                 follow_redirects=True, cookies={"narjis_lang": lang}) as c:
        r = await c.get(path)
    assert r.status_code == 200
    for bad in ("قبل الضريبة", "الفواتير الضريبية", "فواتير ضريبية", "Tax invoices", "pre-VAT",
                "15%", "15٪", "١٥٪", "excl. VAT", "Prices exclude"):
        assert bad not in r.text, (path, bad)


async def test_pricing_page_shows_configured_percent(monkeypatch):
    import httpx

    from src.main import app

    monkeypatch.setenv("VAT_RATE", "0.05")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t",
                                 follow_redirects=True, cookies={"narjis_lang": "en"}) as c:
        r = await c.get("/pricing")
    assert "ضريبة القيمة المضافة 5٪" in r.text and "15٪" not in r.text and "15% VAT" not in r.text
