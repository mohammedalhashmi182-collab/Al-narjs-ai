"""PayPal (Orders v2) checkout: USD at the riyal peg, verified capture, webhooks.

PayPal is fully mocked here; no request leaves the process.
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import ClientProject, Decision, Payment
from src.services import payments as pm

_RealClient = httpx.AsyncClient


@contextmanager
def _paypal_live(webhook_id="WH-TEST", rate=3.75):
    from src.config import settings as s

    names = {
        "moyasar_api_secret": None,
        "paypal_client_id": "client-id",
        "paypal_client_secret": "client-secret",
        "paypal_mode": "live",
        "paypal_webhook_id": webhook_id,
        "paypal_sar_per_usd": rate,
    }
    old = {n: getattr(s, n) for n in names}
    for n, v in names.items():
        object.__setattr__(s, n, v)
    old_flag = os.environ.get("CUSTOMER_PAYPAL_ENABLED")
    os.environ["CUSTOMER_PAYPAL_ENABLED"] = "1"
    try:
        yield s
    finally:
        for n, v in old.items():
            object.__setattr__(s, n, v)
        if old_flag is None:
            os.environ.pop("CUSTOMER_PAYPAL_ENABLED", None)
        else:
            os.environ["CUSTOMER_PAYPAL_ENABLED"] = old_flag


class FakePayPal:
    def __init__(self):
        self.orders: dict[str, dict] = {}
        self.calls: list[tuple[str, str]] = []
        self.capture_value_override = None
        self.capture_currency_override = None
        self.verify_status = "SUCCESS"
        self.n = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append((request.method, path))
        assert request.url.host == "api-m.paypal.com"
        if path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "tok"})
        if path == "/v1/notifications/verify-webhook-signature":
            body = json.loads(request.content)
            assert body["webhook_id"] == "WH-TEST"
            return httpx.Response(200, json={"verification_status": self.verify_status})
        if path == "/v2/checkout/orders" and request.method == "POST":
            body = json.loads(request.content)
            self.n += 1
            oid = f"ORDER{self.n}"
            unit = body["purchase_units"][0]
            self.orders[oid] = {"id": oid, "status": "APPROVED", "purchase_units": [dict(unit)]}
            self.last_create = body
            return httpx.Response(201, json={
                "id": oid, "status": "PAYER_ACTION_REQUIRED",
                "links": [{"rel": "payer-action", "href": f"https://www.paypal.com/checkoutnow?token={oid}"}],
            })
        if path.startswith("/v2/checkout/orders/"):
            parts = path.split("/")
            oid = parts[4]
            order = self.orders.get(oid)
            if order is None:
                return httpx.Response(404, json={})
            if request.method == "GET":
                return httpx.Response(200, json=order)
            if parts[-1] == "capture":
                if order["status"] == "COMPLETED":
                    return httpx.Response(422, json={"details": [{"issue": "ORDER_ALREADY_CAPTURED"}]})
                unit = order["purchase_units"][0]
                amount = dict(unit["amount"])
                if self.capture_value_override:
                    amount["value"] = self.capture_value_override
                if self.capture_currency_override:
                    amount["currency_code"] = self.capture_currency_override
                unit["payments"] = {"captures": [{"id": "CAP" + oid, "status": "COMPLETED", "amount": amount, "custom_id": unit["custom_id"]}]}
                order["status"] = "COMPLETED"
                return httpx.Response(201, json=order)
        return httpx.Response(404, json={})


@pytest.fixture
def paypal(monkeypatch):
    fake = FakePayPal()
    transport = httpx.MockTransport(fake.handler)

    def _client(*a, **kw):
        kw.pop("transport", None)
        return _RealClient(*a, transport=transport, **kw)

    monkeypatch.setattr(pm.httpx, "AsyncClient", _client)
    with _paypal_live():
        yield fake


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def client(maker):
    from src.main import app

    app.state.session_factory = maker
    async with _RealClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _checkout(client, consent=True):
    return await client.post("/api/payments", json={
        "package": "bidaya", "method": "paypal", "customer_name": "Buyer",
        "customer_phone": "0555000111", "customer_email": None, "refund_consent": consent,
    }, headers={"idempotency-key": uuid.uuid4().hex})


async def _payment(maker, pid) -> Payment:
    async with maker() as s:
        return (await s.execute(select(Payment).where(Payment.id == __import__("uuid").UUID(pid)))).scalar_one()


class TestConversion:
    def test_peg_conversion(self):
        assert pm.sar_halalas_to_usd_cents(375) == 100
        assert pm.sar_halalas_to_usd_cents(57385) == 15303  # 573.85 SAR -> 153.0267 USD
        assert pm.sar_halalas_to_usd_cents(100, sar_per_usd=4) == 25

    def test_rate_is_configurable(self):
        with _paypal_live(rate=3.5):
            assert pm.sar_halalas_to_usd_cents(350) == 100

    def test_live_base_url(self):
        with _paypal_live() as s:
            assert pm._paypal_base_url(s) == "https://api-m.paypal.com"


class TestCheckout:
    async def test_consent_required(self, client, paypal):
        r = await _checkout(client, consent=False)
        assert r.status_code == 422
        assert not any(p == "/v2/checkout/orders" for _, p in paypal.calls)

    async def test_order_in_usd_and_both_amounts_stored(self, client, maker, paypal):
        r = await _checkout(client)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["gateway"] == "paypal" and data["redirect_url"].startswith("https://www.paypal.com/")
        assert data["charge_currency"] == "USD"
        assert data["charge_amount"] == pm.sar_halalas_to_usd_cents(data["total"])
        unit = paypal.last_create["purchase_units"][0]
        assert unit["amount"]["currency_code"] == "USD"
        assert unit["amount"]["value"] == f"{data['charge_amount'] / 100:.2f}"
        assert paypal.last_create["intent"] == "CAPTURE"
        p = await _payment(maker, data["payment_id"])
        assert p.currency == "SAR" and p.charge_currency == "USD" and p.charge_amount == data["charge_amount"]
        assert p.refund_consent_at is not None and p.gateway_payment_id == data["order_id"]

    async def test_capture_marks_paid_once(self, client, maker, paypal):
        data = (await _checkout(client)).json()
        r = await client.post(f"/api/payments/{data['payment_id']}/capture", json={"order_id": "IGNORED"})
        assert r.json()["status"] == "paid"
        r2 = await client.post(f"/api/payments/{data['payment_id']}/capture", json={})
        assert r2.json()["status"] == "paid"
        captures = [c for c in paypal.calls if c[1].endswith("/capture")]
        assert len(captures) == 1
        async with maker() as s:
            decisions = (await s.execute(select(Decision).where(Decision.reason == f"payment_ref:{data['payment_id']}"))).scalars().all()
        assert len(decisions) == 1

    async def test_amount_mismatch_goes_to_review(self, client, maker, paypal):
        paypal.capture_value_override = "1.00"
        data = (await _checkout(client)).json()
        r = await client.post(f"/api/payments/{data['payment_id']}/capture", json={})
        assert r.json()["status"] == pm.REVIEW_STATUS
        async with maker() as s:
            assert (await s.execute(select(ClientProject))).scalars().first() is None

    async def test_currency_mismatch_goes_to_review(self, client, paypal):
        paypal.capture_currency_override = "SAR"
        data = (await _checkout(client)).json()
        r = await client.post(f"/api/payments/{data['payment_id']}/capture", json={})
        assert r.json()["status"] == pm.REVIEW_STATUS


class TestInvoicePayment:
    async def _invoice(self, maker):
        async with maker() as s:
            p = Payment(amount=49900, currency="SAR", package="radd", gateway="invoice", status="invoice", customer_phone="0555")
            s.add(p)
            await s.commit()
            return str(p.id)

    async def test_requires_consent(self, client, maker, paypal):
        pid = await self._invoice(maker)
        r = await client.post(f"/api/payments/{pid}/pay-paypal", json={})
        assert r.status_code == 422

    async def test_creates_usd_order(self, client, maker, paypal):
        pid = await self._invoice(maker)
        r = await client.post(f"/api/payments/{pid}/pay-paypal", json={"refund_consent": True})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["charge_amount"] == pm.sar_halalas_to_usd_cents(pm.total_with_vat(49900))
        p = await _payment(maker, pid)
        assert p.gateway == "paypal" and p.refund_consent_at is not None

    async def test_paid_invoice_rejected(self, client, maker, paypal):
        async with maker() as s:
            p = Payment(amount=100, currency="SAR", package="radd", gateway="invoice", status="paid")
            s.add(p)
            await s.commit()
            pid = str(p.id)
        r = await client.post(f"/api/payments/{pid}/pay-paypal", json={"refund_consent": True})
        assert r.status_code == 409

    async def test_hidden_in_sandbox(self, client, maker, paypal):
        from src.config import settings as s

        pid = await self._invoice(maker)
        object.__setattr__(s, "paypal_mode", "sandbox")
        r = await client.post(f"/api/payments/{pid}/pay-paypal", json={"refund_consent": True})
        assert r.status_code == 503

    async def test_invoice_page_shows_usd_button(self, client, maker, paypal):
        pid = await self._invoice(maker)
        r = await client.get(f"/invoice/{pid}")
        usd = f"{pm.sar_halalas_to_usd_cents(pm.total_with_vat(49900)) / 100:.2f}"
        assert "invoicePayPayPal" in r.text and usd in r.text


def _hdrs():
    return {
        "paypal-auth-algo": "SHA256withRSA", "paypal-cert-url": "https://api.paypal.com/cert",
        "paypal-transmission-id": "t1", "paypal-transmission-sig": "sig", "paypal-transmission-time": "now",
    }


class TestWebhook:
    async def test_rejects_without_signature_headers(self, client, paypal):
        r = await client.post("/webhooks/paypal", json={"event_type": "PAYMENT.CAPTURE.COMPLETED"})
        assert r.status_code == 401

    async def test_rejects_failed_verification(self, client, paypal):
        paypal.verify_status = "FAILURE"
        r = await client.post("/webhooks/paypal", json={"event_type": "PAYMENT.CAPTURE.COMPLETED"}, headers=_hdrs())
        assert r.status_code == 401

    async def test_rejects_without_webhook_id(self, client, paypal):
        from src.config import settings as s

        object.__setattr__(s, "paypal_webhook_id", None)
        r = await client.post("/webhooks/paypal", json={"event_type": "PAYMENT.CAPTURE.COMPLETED"}, headers=_hdrs())
        assert r.status_code == 401

    async def test_order_approved_captures_and_replay_is_noop(self, client, maker, paypal):
        data = (await _checkout(client)).json()
        event = {"event_type": "CHECKOUT.ORDER.APPROVED", "resource": {
            "id": data["order_id"], "purchase_units": [{"custom_id": data["payment_id"]}]}}
        r = await client.post("/webhooks/paypal", json=event, headers=_hdrs())
        assert r.json()["status"] == "paid" and r.json()["already"] is False
        r = await client.post("/webhooks/paypal", json=event, headers=_hdrs())
        assert r.json()["already"] is True
        assert len([c for c in paypal.calls if c[1].endswith("/capture")]) == 1

    async def test_capture_completed_body_is_not_trusted(self, client, maker, paypal):
        data = (await _checkout(client)).json()
        paypal.capture_value_override = "0.01"
        event = {"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {
            "id": "CAPX", "status": "COMPLETED", "custom_id": data["payment_id"],
            "amount": {"currency_code": "USD", "value": f"{data['charge_amount'] / 100:.2f}"},
            "supplementary_data": {"related_ids": {"order_id": data["order_id"]}}}}
        r = await client.post("/webhooks/paypal", json=event, headers=_hdrs())
        assert r.json()["status"] == pm.REVIEW_STATUS

    async def test_unknown_event_ignored(self, client, paypal):
        r = await client.post("/webhooks/paypal", json={"event_type": "BILLING.PLAN.CREATED"}, headers=_hdrs())
        assert r.status_code == 200 and "ignored" in r.json()


def test_no_secret_in_capabilities():
    with _paypal_live():
        blob = json.dumps(pm.readiness())
    assert "client-secret" not in blob and "PAYPAL_WEBHOOK_ID" in blob
