"""Launch payment fixes: Moyasar return URLs, webhook auth, amount checks,
idempotent order creation and the VAT-inclusive bank-transfer total."""

from __future__ import annotations

from contextlib import contextmanager

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import Payment
from src.services import payments as pm

@pytest.fixture(autouse=True)
def _bank_transfer_code_path(monkeypatch):
    """These tests exercise the invoice code path; customers do not see it unless the flag is on."""
    monkeypatch.setenv("CUSTOMER_BANK_TRANSFER_ENABLED", "1")


WEBHOOK_SECRET = "whsec-test-value"
LIVE_KEY = "sk_" + "live_" + "FAKE-VALUE-FOR-TESTS-ONLY-NOT-A-REAL-KEY"


@contextmanager
def _settings(**values):
    from src.config import settings as s

    old = {k: getattr(s, k) for k in values}
    for k, v in values.items():
        object.__setattr__(s, k, v)
    pm._credential_cache.clear()
    try:
        yield
    finally:
        for k, v in old.items():
            object.__setattr__(s, k, v)
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

    main.app.state.session_factory = maker
    main._payment_replays.clear()
    main._payment_locks.clear()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as c:
        yield c


async def _insert(maker, **kw) -> Payment:
    async with maker() as session:
        p = Payment(
            amount=kw.pop("amount", 999900), currency="SAR", package="team",
            gateway="moyasar", gateway_source="invoice",
            gateway_payment_id=kw.pop("gateway_payment_id", "inv_123"),
            status=kw.pop("status", "pending"), **kw,
        )
        session.add(p)
        await session.commit()
        await session.refresh(p)
        session.expunge(p)
        return p


def _fake_moyasar_get(monkeypatch, body: dict):
    calls = []

    async def _get(self, url, *a, **k):
        calls.append(url)
        return httpx.Response(200, json=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", _get)
    return calls


async def _status(maker, pid) -> str:
    from sqlalchemy import select

    async with maker() as s:
        return (await s.execute(select(Payment).where(Payment.id == pid))).scalar_one().status


def _event(payment: Payment, token=WEBHOOK_SECRET, type_="payment_paid"):
    body = {"type": type_, "data": {"id": "pay_1", "invoice_id": payment.gateway_payment_id,
                                     "metadata": {"order_id": str(payment.id)}}}
    if token is not None:
        body["secret_token"] = token
    return body


class TestReturnUrls:
    async def test_invoice_uses_success_back_and_webhook_callback(self, maker, monkeypatch):
        captured = {}

        async def _post(self, url, *a, **k):
            captured.update(k.get("json") or {})
            raise pm.PaymentError("stop")

        monkeypatch.setattr(httpx.AsyncClient, "post", _post)
        async with maker() as s:
            p = await pm.create_payment(s, "radd", "x", None, None)
            with _settings(moyasar_api_secret=LIVE_KEY), pytest.raises(pm.PaymentError):
                await pm.initiate_moyasar(
                    s, p, pm.source_mada(),
                    success_url="https://a/payment/success?id=1", back_url="https://a/payment/failure?id=1",
                    callback_url="https://a/webhooks/moyasar",
                )
        assert captured["success_url"].endswith("/payment/success?id=1")
        assert captured["back_url"].endswith("/payment/failure?id=1")
        assert captured["callback_url"] == "https://a/webhooks/moyasar"
        assert captured["metadata"]["order_id"] == str(p.id)

    async def test_api_builds_https_urls_from_forwarded_proto(self, anon, monkeypatch):
        captured = {}

        async def _initiate(session, payment, source, **kw):
            captured.update(kw)
            raise pm.PaymentError("stop")

        monkeypatch.setattr(pm, "initiate_moyasar", _initiate)
        with _settings(moyasar_api_secret=LIVE_KEY, public_base_url=None):
            await anon.post("/api/payments", json={"refund_consent": True, "package": "radd", "method": "mada"},
                            headers={"X-Forwarded-Proto": "https"})
        assert captured["success_url"].startswith("https://test/payment/success?id=")
        assert captured["back_url"].startswith("https://test/payment/failure?id=")
        assert captured["callback_url"] == "https://test/webhooks/moyasar"

    async def test_public_base_url_wins(self, anon, monkeypatch):
        captured = {}

        async def _initiate(session, payment, source, **kw):
            captured.update(kw)
            raise pm.PaymentError("stop")

        monkeypatch.setattr(pm, "initiate_moyasar", _initiate)
        with _settings(moyasar_api_secret=LIVE_KEY, public_base_url="https://alnarjs.example/"):
            await anon.post("/api/payments", json={"refund_consent": True, "package": "radd", "method": "mada"})
        assert captured["callback_url"] == "https://alnarjs.example/webhooks/moyasar"


class TestWebhookAuth:
    async def test_missing_token_is_401(self, anon, maker):
        p = await _insert(maker)
        with _settings(moyasar_webhook_secret=WEBHOOK_SECRET):
            r = await anon.post("/webhooks/moyasar", json=_event(p, token=None))
        assert r.status_code == 401
        assert await _status(maker, p.id) == "pending"

    async def test_wrong_token_is_401(self, anon, maker):
        p = await _insert(maker)
        with _settings(moyasar_webhook_secret=WEBHOOK_SECRET):
            r = await anon.post("/webhooks/moyasar", json=_event(p, token="nope"))
        assert r.status_code == 401

    async def test_unconfigured_secret_rejects_everything(self, anon, maker):
        p = await _insert(maker)
        with _settings(moyasar_webhook_secret=None):
            r = await anon.post("/webhooks/moyasar", json=_event(p, token=""))
        assert r.status_code == 401

    async def test_valid_paid_event_marks_paid_after_refetch(self, anon, maker, monkeypatch):
        p = await _insert(maker)
        calls = _fake_moyasar_get(monkeypatch, {"status": "paid", "amount": 1149885, "currency": "SAR"})
        with _settings(moyasar_webhook_secret=WEBHOOK_SECRET, moyasar_api_secret=LIVE_KEY):
            r = await anon.post("/webhooks/moyasar", json=_event(p))
        assert r.status_code == 200, r.text
        assert calls and calls[0].endswith("/invoices/inv_123")
        assert await _status(maker, p.id) == "paid"

    async def test_a_test_key_does_not_mark_the_order_paid(self, anon, maker, monkeypatch):
        p = await _insert(maker)
        test_key = "sk_" + "test_" + "FAKE-VALUE-FOR-TESTS-ONLY-NOT-A-REAL-KEY"
        _fake_moyasar_get(monkeypatch, {"status": "paid", "amount": 1149885, "currency": "SAR"})
        with _settings(moyasar_webhook_secret=WEBHOOK_SECRET, moyasar_api_secret=test_key):
            r = await anon.post("/webhooks/moyasar", json=_event(p))
        assert r.status_code == 200, r.text
        assert await _status(maker, p.id) != "paid"

    async def test_replay_on_paid_order_is_noop_200(self, anon, maker, monkeypatch):
        p = await _insert(maker, status="paid")
        calls = _fake_moyasar_get(monkeypatch, {"status": "failed", "amount": 1, "currency": "SAR"})
        with _settings(moyasar_webhook_secret=WEBHOOK_SECRET, moyasar_api_secret=LIVE_KEY):
            r = await anon.post("/webhooks/moyasar", json=_event(p, type_="payment_failed"))
        assert r.status_code == 200 and r.json()["already"] is True
        assert calls == []
        assert await _status(maker, p.id) == "paid"

    async def test_failed_event_marks_failed(self, anon, maker, monkeypatch):
        p = await _insert(maker)
        _fake_moyasar_get(monkeypatch, {"status": "failed", "amount": 1149885, "currency": "SAR"})
        with _settings(moyasar_webhook_secret=WEBHOOK_SECRET, moyasar_api_secret=LIVE_KEY):
            r = await anon.post("/webhooks/moyasar", json=_event(p, type_="payment_failed"))
        assert r.status_code == 200
        assert await _status(maker, p.id) == "failed"


class TestAmountMismatch:
    async def test_webhook_wrong_amount_goes_to_review(self, anon, maker, monkeypatch):
        p = await _insert(maker)
        _fake_moyasar_get(monkeypatch, {"status": "paid", "amount": 999900, "currency": "SAR"})
        with _settings(moyasar_webhook_secret=WEBHOOK_SECRET, moyasar_api_secret=LIVE_KEY):
            r = await anon.post("/webhooks/moyasar", json=_event(p))
        assert r.status_code == 200
        assert await _status(maker, p.id) == pm.REVIEW_STATUS

    async def test_success_page_verification_wrong_currency_not_paid(self, maker, monkeypatch):
        p = await _insert(maker)
        _fake_moyasar_get(monkeypatch, {"status": "paid", "amount": 1149885, "currency": "USD"})
        with _settings(moyasar_api_secret=LIVE_KEY):
            async with maker() as s:
                got = await pm.verify_payment(s, p.id)
        assert got.status == pm.REVIEW_STATUS

    async def test_success_page_verification_exact_amount_is_paid(self, anon, maker, monkeypatch):
        p = await _insert(maker)
        _fake_moyasar_get(monkeypatch, {"status": "paid", "amount": 1149885, "currency": "SAR"})
        with _settings(moyasar_api_secret=LIVE_KEY):
            r = await anon.get(f"/api/payments/{p.id}")
        assert r.json()["status"] == "paid"


class TestIdempotency:
    async def test_same_idempotency_key_creates_one_order(self, anon, maker):
        from sqlalchemy import func, select

        with _settings(moyasar_api_secret=None):
            h = {"Idempotency-Key": "abc-123"}
            r1 = await anon.post("/api/payments", json={"refund_consent": True, "package": "radd", "method": "invoice"}, headers=h)
            r2 = await anon.post("/api/payments", json={"refund_consent": True, "package": "radd", "method": "invoice"}, headers=h)
        assert r1.json()["payment_id"] == r2.json()["payment_id"]
        assert r2.json().get("replayed") is True
        async with maker() as s:
            assert (await s.execute(select(func.count()).select_from(Payment))).scalar_one() == 1

    async def test_same_customer_double_click_without_key_is_deduped(self, anon):
        body = {"refund_consent": True, "package": "radd", "method": "invoice", "customer_phone": "0555000000"}
        with _settings(moyasar_api_secret=None):
            r1 = await anon.post("/api/payments", json=body)
            r2 = await anon.post("/api/payments", json=body)
        assert r1.json()["payment_id"] == r2.json()["payment_id"]

    async def test_different_keys_create_different_orders(self, anon):
        with _settings(moyasar_api_secret=None):
            r1 = await anon.post("/api/payments", json={"refund_consent": True, "package": "radd", "method": "invoice"}, headers={"Idempotency-Key": "a"})
            r2 = await anon.post("/api/payments", json={"refund_consent": True, "package": "radd", "method": "invoice"}, headers={"Idempotency-Key": "b"})
        assert r1.json()["payment_id"] != r2.json()["payment_id"]

    def test_pay_button_is_disabled_and_sends_a_key(self):
        html = open("src/web/templates/portal.html", encoding="utf-8").read()
        assert "'Idempotency-Key': idemKey" in html
        assert "b.disabled = true" in html


class TestBankTransferTotal:
    async def test_bank_transfer_total_matches_invoice(self, anon):
        with _settings(moyasar_api_secret=None):
            r = await anon.post("/api/payments", json={"refund_consent": True, "package": "bay", "method": "invoice"})
        data = r.json()
        base = data["amount"]
        assert data["total"] == data["invoice_total"] == pm.total_with_vat(base)
        assert data["vat"] == pm.vat_amount(base)

    async def test_team_is_1723_85_sar_with_vat(self, anon):
        from src.services import catalog

        if catalog.PACKAGES.get("team", {}).get("amount") != 149900:
            pytest.skip("team package price changed")
        with _settings(moyasar_api_secret=None):
            r = await anon.post("/api/payments", json={"refund_consent": True, "package": "bay", "method": "invoice"})
        assert r.json()["total"] == 172385  # halalas == 1,723.85 SAR, not the 149900 base
