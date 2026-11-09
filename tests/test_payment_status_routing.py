"""GET /api/payments/{id} and verify_payment route by provider."""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import Payment
from src.services import payments as pm


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def no_moyasar(monkeypatch):
    """Any Moyasar HTTP call fails the test."""
    real_send = httpx.AsyncClient.send

    async def guard(self, request, *a, **k):
        assert "moyasar" not in str(request.url), "Moyasar must not be called"
        return await real_send(self, request, *a, **k)

    monkeypatch.setattr(httpx.AsyncClient, "send", guard)


async def _pay(maker, gateway, gid, status="pending", **kw):
    async with maker() as s:
        p = Payment(package="radd", amount=47920, currency="SAR", description="x", status=status,
                    gateway=gateway, gateway_payment_id=gid, customer_name="t", **kw)
        s.add(p)
        await s.commit()
        return p


def _order(payment, status="COMPLETED"):
    usd = pm.sar_halalas_to_usd_cents(pm.expected_charge(payment))
    return {"id": payment.gateway_payment_id, "status": "COMPLETED",
            "purchase_units": [{"custom_id": str(payment.id), "payments": {"captures": [
                {"status": status, "amount": {"currency_code": "USD", "value": f"{usd / 100:.2f}"}}]}}]}


async def test_paypal_record_checked_against_paypal_not_moyasar(maker, monkeypatch, no_moyasar):
    p = await _pay(maker, "paypal", "ORDER1", charge_currency="USD")
    async with maker() as s:
        p.charge_amount = pm.sar_halalas_to_usd_cents(pm.expected_charge(p))
        s.add(p)
        await s.commit()
    calls = []

    async def fake_get(order_id):
        calls.append(order_id)
        return _order(p)

    async def no_capture(order_id):
        raise AssertionError("status check must not capture")

    monkeypatch.setattr(pm, "get_paypal_order", fake_get)
    monkeypatch.setattr(pm, "capture_paypal_order", no_capture)
    async with maker() as s:
        got = await pm.verify_payment(s, p.id)
    assert calls == ["ORDER1"] and got.status == "paid"


async def test_unpaid_paypal_order_stays_pending(maker, monkeypatch, no_moyasar):
    p = await _pay(maker, "paypal", "ORDER2")

    async def fake_get(order_id):
        return {"id": order_id, "status": "CREATED", "purchase_units": []}

    monkeypatch.setattr(pm, "get_paypal_order", fake_get)
    async with maker() as s:
        got = await pm.verify_payment(s, p.id)
    assert got.status == "pending"


async def test_invoice_record_calls_no_gateway(maker, monkeypatch, no_moyasar):
    p = await _pay(maker, "invoice", "INV-LOCAL", status="invoice")

    async def boom(order_id):
        raise AssertionError("PayPal must not be called")

    monkeypatch.setattr(pm, "get_paypal_order", boom)
    async with maker() as s:
        got = await pm.verify_payment(s, p.id)
    assert got.status == "invoice"


def test_provider_routing():
    assert pm.payment_provider(Payment(gateway="paypal", gateway_payment_id="x")) == "paypal"
    assert pm.payment_provider(Payment(gateway="moyasar", gateway_payment_id="x")) == "moyasar"
    assert pm.payment_provider(Payment(gateway=None, gateway_payment_id="x")) == "moyasar"
    assert pm.payment_provider(Payment(gateway="invoice", gateway_payment_id="x")) == "none"


async def test_api_paypal_status_and_gateway_error_is_502(maker, monkeypatch, no_moyasar):
    from src.main import app

    p = await _pay(maker, "paypal", "ORDER3")
    state = {"fail": False}

    async def fake_get(order_id):
        if state["fail"]:
            raise pm.PaymentError("PayPal order fetch error 500")
        return {"id": order_id, "status": "CREATED", "purchase_units": []}

    monkeypatch.setattr(pm, "get_paypal_order", fake_get)
    app.state.session_factory = maker
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        from src.core.portal_auth import make_payment_token

        auth = {"X-Payment-Token": make_payment_token(p.id)}
        ok = await c.get(f"/api/payments/{p.id}", headers=auth)
        state["fail"] = True
        bad = await c.get(f"/api/payments/{p.id}", headers=auth)
        missing = await c.get("/api/payments/00000000-0000-0000-0000-000000000000")
        junk = await c.get("/api/payments/not-a-uuid")
    assert ok.status_code == 200 and ok.json()["status"] == "pending" and ok.json()["gateway"] == "paypal"
    assert bad.status_code == 502 and "Moyasar" not in bad.text
    assert missing.status_code == 404 and junk.status_code == 404
