"""Owner-raised invoice links: the buyer must tick the refund consent before paying."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import Payment
from src.services import payments as pm
from src.services import policies

TPL = Path(__file__).resolve().parents[1] / "src" / "web" / "templates"


@contextmanager
def _gateway(secret):
    from src.config import settings as s

    old = s.moyasar_api_secret
    object.__setattr__(s, "moyasar_api_secret", secret)
    pm._credential_cache.clear()
    try:
        yield
    finally:
        object.__setattr__(s, "moyasar_api_secret", old)
        pm._credential_cache.clear()


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def anon(maker):
    from src import main
    from src.utils.rate_limit import transfer_limiter

    main.app.state.session_factory = maker
    transfer_limiter.reset()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as c:
        yield c


async def _owner_invoice(maker) -> Payment:
    """What the owner dashboard raises: no buyer present, so no consent yet."""
    async with maker() as s:
        p = await pm.create_payment(s, "starter", customer_name="عميل")
        p.status = "invoice"
        await s.commit()
        return p


async def _reload(maker, pid) -> Payment:
    async with maker() as s:
        return await s.get(Payment, UUID(str(pid)))


async def test_owner_invoice_starts_without_consent(maker):
    p = await _owner_invoice(maker)
    assert p.refund_consent_at is None


async def test_invoice_page_shows_required_consent_from_policies(anon, maker):
    p = await _owner_invoice(maker)
    with _gateway(None):
        r = await anon.get(f"/invoice/{p.id}", headers={"accept-language": "ar"})
    assert r.status_code == 200
    assert 'id="refundConsent"' in r.text and "required" in r.text.split('id="refundConsent"')[1][:60]
    assert policies.REFUND_CONSENT_AR in r.text


def test_consent_text_is_not_duplicated_in_templates():
    src = (TPL / "partials" / "_invoice_consent.html").read_text(encoding="utf-8")
    assert "{{ refund_consent_ar }}" in src and "{{ refund_consent_en }}" in src
    assert "invoice_consent.html" in (TPL / "invoice.html").read_text(encoding="utf-8")
    assert "invoice_consent.html" in (TPL / "invoice_en.html").read_text(encoding="utf-8")
    xfer = (TPL / "partials" / "_transfer.html").read_text(encoding="utf-8")
    assert "refund_consent: true" in xfer and "narjisInvoiceConsent" in xfer


async def test_transfer_report_without_consent_is_422(anon, maker):
    p = await _owner_invoice(maker)
    r = await anon.post(f"/api/payments/{p.id}/transfer-reported")
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "refund_consent_required"
    r = await anon.post(f"/api/payments/{p.id}/transfer-reported", json={"refund_consent": False})
    assert r.status_code == 422
    row = await _reload(maker, p.id)
    assert row.refund_consent_at is None and row.gateway_source != "transfer_reported"


async def test_transfer_report_with_consent_stores_it(anon, maker, monkeypatch):
    async def _alert(text):
        return {"ok": True}

    monkeypatch.setattr("src.services.telegram_sender.send_owner_alert", _alert)
    p = await _owner_invoice(maker)
    r = await anon.post(f"/api/payments/{p.id}/transfer-reported", json={"refund_consent": True})
    assert r.status_code == 200, r.text
    row = await _reload(maker, p.id)
    assert row.refund_consent_at is not None
    assert row.refund_consent_version == policies.POLICY_VERSION
    assert row.status != "paid"


async def test_card_pay_without_consent_is_422_and_no_charge(anon, maker, monkeypatch):
    called = []

    async def _init(*a, **k):
        called.append(1)
        return {"id": "inv_x", "checkout_url": "https://checkout.moyasar.com/invoices/inv_x"}

    monkeypatch.setattr(pm, "initiate_moyasar", _init)
    p = await _owner_invoice(maker)
    with _gateway("sk_test"):
        r = await anon.post(f"/api/payments/{p.id}/pay-card", json={})
        r2 = await anon.post(f"/api/payments/{p.id}/pay-card", json={"refund_consent": False})
    assert r.status_code == 422 and r2.status_code == 422 and called == []
    assert (await _reload(maker, p.id)).refund_consent_at is None


async def test_card_pay_with_consent_stores_it_and_redirects(anon, maker, monkeypatch):
    async def _init(session, payment, source, **k):
        payment.gateway = "moyasar"
        payment.gateway_payment_id = "inv_x"
        await session.commit()
        return {"id": "inv_x", "checkout_url": "https://checkout.moyasar.com/invoices/inv_x?lang=ar"}

    monkeypatch.setattr(pm, "initiate_moyasar", _init)
    p = await _owner_invoice(maker)
    with _gateway("sk_test"):
        r = await anon.post(f"/api/payments/{p.id}/pay-card", json={"refund_consent": True})
        # A second tap reuses the Moyasar invoice instead of creating another.
        again = await anon.post(f"/api/payments/{p.id}/pay-card", json={"refund_consent": True})
    assert r.status_code == 200, r.text
    assert r.json()["redirect_url"].startswith("https://checkout.moyasar.com/invoices/inv_x")
    assert again.status_code == 200 and "inv_x" in again.json()["redirect_url"]
    row = await _reload(maker, p.id)
    assert row.refund_consent_at is not None and row.refund_consent_version == policies.POLICY_VERSION


async def test_card_pay_without_gateway_is_503(anon, maker):
    p = await _owner_invoice(maker)
    with _gateway(None):
        r = await anon.post(f"/api/payments/{p.id}/pay-card", json={"refund_consent": True})
    assert r.status_code == 503


async def test_card_pay_rejects_paid_and_unknown(anon, maker):
    from uuid import uuid4

    p = await _owner_invoice(maker)
    async with maker() as s:
        row = await s.get(Payment, p.id)
        row.status = "paid"
        await s.commit()
    r = await anon.post(f"/api/payments/{p.id}/pay-card", json={"refund_consent": True})
    assert r.status_code == 409
    assert (await anon.post(f"/api/payments/{uuid4()}/pay-card", json={"refund_consent": True})).status_code == 404
    assert (await anon.post("/api/payments/nope/pay-card", json={"refund_consent": True})).status_code == 422
