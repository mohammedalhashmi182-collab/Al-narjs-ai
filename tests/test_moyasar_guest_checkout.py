"""Guest checkout is Moyasar card payment. Bank transfer and Apple Pay are not offered."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import httpx

from src.config.settings import get_settings
from src.models import Payment
from src.services import payments as pm

LIVE_SECRET = "sk_" + "live_unit_not_a_real_key"
LIVE_PUBLIC = "pk_" + "live_unit_not_a_real_key"
TEST_SECRET = "sk_" + "test_unit_not_a_real_key"
WEBHOOK_SECRET = "whsec_unit_not_a_real_secret"


def _live(monkeypatch, *, secret=LIVE_SECRET, public=LIVE_PUBLIC, webhook=WEBHOOK_SECRET):
    settings = get_settings()
    monkeypatch.setattr(settings, "moyasar_api_secret", secret)
    monkeypatch.setattr(settings, "moyasar_publishable_key", public)
    monkeypatch.setattr(settings, "moyasar_webhook_secret", webhook)
    pm._credential_cache.clear()


def test_live_keys_open_card_methods_and_hide_apple_pay_and_bank_transfer(monkeypatch):
    _live(monkeypatch)
    caps = pm.capabilities(card_state="ok")
    assert caps["card"] is True
    assert caps["methods"]["mada"] is True
    assert caps["methods"]["creditcard"] is True
    assert caps["methods"]["stcpay"] is True
    assert caps["methods"].get("applepay") is not True
    assert caps["methods"]["invoice"] is False
    assert caps["bank"] == {}
    assert pm.customer_bank_transfer_enabled() is False
    assert "applepay" not in pm.CARD_METHODS


def test_test_keys_do_not_open_checkout(monkeypatch):
    _live(monkeypatch, secret=TEST_SECRET, public="pk_" + "test_unit")
    assert pm.moyasar_collects_money() is False
    assert pm.capabilities(card_state="ok")["card"] is False


def test_portal_offers_mada_in_arabic_and_english_and_not_apple_pay_or_iban():
    from pathlib import Path

    portal = Path("src/web/templates/portal.html").read_text(encoding="utf-8")
    assert "مدى / بطاقة مصرفية" in portal
    assert "mada / Bank Card" in portal
    assert "Apple Pay" not in portal
    assert "تحويل بنكي" not in portal
    assert "iban" not in portal.lower()
    invoice_ar = Path("src/web/templates/invoice.html").read_text(encoding="utf-8")
    invoice_en = Path("src/web/templates/invoice_en.html").read_text(encoding="utf-8")
    assert "آيبان" not in invoice_ar and "IBAN" not in invoice_en
    assert "مدى / فيزا / ماستركارد" in invoice_ar
    assert "mada / Visa / Mastercard" in invoice_en
    consent = Path("src/web/templates/partials/_invoice_consent.html").read_text(encoding="utf-8")
    assert "ادفع بالبطاقة (مدى / فيزا / ماستركارد)" in consent
    assert "Pay by card (mada / Visa / Mastercard)" in consent


def test_amount_mismatch_is_review_not_paid(monkeypatch):
    _live(monkeypatch)
    payment = Payment(id=uuid4(), amount=49900, total_halalas=49900, status="pending", currency="SAR")
    pm.apply_gateway_status(payment, {"status": "paid", "amount": 100, "currency": "SAR"})
    assert payment.status == pm.REVIEW_STATUS


def test_matching_paid_invoice_marks_the_order_paid(monkeypatch):
    _live(monkeypatch)
    payment = Payment(
        id=uuid4(),
        amount=49900,
        total_halalas=49900,
        status="pending",
        currency="SAR",
        pricing_snapshot={"expected_total_halalas": 49900},
    )
    pm.apply_gateway_status(payment, {"status": "paid", "amount": 49900, "currency": "SAR"})
    assert payment.status == "paid"


async def test_webhook_rejects_a_bad_token_and_marks_a_verified_payment_paid(monkeypatch):
    _live(monkeypatch)
    from src.main import app

    payment_id = uuid4()
    payment = Payment(
        id=payment_id,
        amount=49900,
        total_halalas=49900,
        status="pending",
        currency="SAR",
        gateway="moyasar",
        gateway_payment_id="inv_unit",
        gateway_source="invoice",
        package="bidaya",
        pricing_snapshot={"expected_total_halalas": 49900},
    )

    class _Result:
        def scalar_one_or_none(self):
            return payment

        def scalars(self):
            return self

        def first(self):
            return payment

    class _Session:
        async def execute(self, _query):
            return _Result()

        async def commit(self):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(app.state, "session_factory", _Session, raising=False)

    paid = {"id": "inv_unit", "status": "paid", "amount": 49900, "currency": "SAR", "source": {"type": "creditcard"}}

    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            return paid

    real_client = httpx.AsyncClient

    class _Client(real_client):
        async def get(self, url, *args, **kwargs):
            if "api.moyasar.com" in str(url):
                return _Resp()
            return await super().get(url, *args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    applied = AsyncMock(return_value={"applied": True})
    monkeypatch.setattr("src.main._apply_paid_outcome", applied)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        bad = await client.post("/webhooks/moyasar", json={"type": "payment_paid", "secret_token": "nope"})
        assert bad.status_code == 401
        ok = await client.post(
            "/webhooks/moyasar",
            json={
                "type": "payment_paid",
                "secret_token": WEBHOOK_SECRET,
                "data": {"id": "pay_unit", "invoice_id": "inv_unit", "metadata": {"order_id": str(payment_id)}},
            },
        )
        assert ok.status_code == 200, ok.text
        body = ok.json()
        assert body["status"] == "paid"
        assert body["payment_id"] == str(payment_id)
    assert payment.status == "paid"
    applied.assert_awaited()


async def test_guest_invoice_is_refused_and_mada_redirects_to_moyasar(monkeypatch):
    _live(monkeypatch)
    from src.main import app

    created = {}

    async def _create(session, package, *args, **kwargs):
        payment = Payment(
            id=uuid4(),
            amount=79000,
            total_halalas=79000,
            status="pending",
            currency="SAR",
            package=package,
            gateway="invoice",
            description="اختبار",
            pricing_snapshot={"expected_total_halalas": 79000},
        )
        created["payment"] = payment
        session.add(payment)
        return payment

    class _Session:
        def add(self, obj):
            created["added"] = obj

        async def commit(self):
            return None

        async def delete(self, obj):
            created["deleted"] = obj

        async def refresh(self, obj):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(app.state, "session_factory", _Session, raising=False)
    monkeypatch.setattr(pm, "create_payment", _create)

    async def _initiate(session, payment, source, **kwargs):
        assert source["type"] == "creditcard"
        assert kwargs["callback_url"].endswith("/webhooks/moyasar")
        payment.gateway = "moyasar"
        payment.gateway_payment_id = "inv_redirect"
        return {"id": "inv_redirect", "checkout_url": "https://checkout.moyasar.com/invoices/inv_redirect?lang=ar"}

    monkeypatch.setattr(pm, "initiate_moyasar", _initiate)
    monkeypatch.setattr("src.services.funnel.track", AsyncMock())

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        refused = await client.post(
            "/api/payments",
            json={"package": "bidaya", "method": "invoice", "refund_consent": True, "customer_phone": "0550000000"},
        )
        assert refused.status_code == 400
        assert "Bank transfer" in refused.text
        apple = await client.post(
            "/api/payments",
            json={"package": "bidaya", "method": "applepay", "refund_consent": True, "customer_phone": "0550000001"},
        )
        assert apple.status_code == 400
        card = await client.post(
            "/api/payments",
            json={"package": "bidaya", "method": "mada", "refund_consent": True, "customer_phone": "0550000002"},
        )
        assert card.status_code == 200, card.text
        payload = card.json()
        assert payload["gateway"] == "moyasar"
        assert payload["redirect_url"].startswith("https://checkout.moyasar.com/invoices/")
        assert "sk_" not in card.text
