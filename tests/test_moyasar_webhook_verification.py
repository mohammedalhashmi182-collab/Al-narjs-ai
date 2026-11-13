"""Moyasar webhook verification and payment-event authentication.

Docs checked 12 Nov 2026 (pages last updated 11 Nov 2026): payment events carry
``secret_token`` in the JSON body. No signature header is documented.
``webhook_verification`` carries ``data.verification_code`` and is not a payment.

Payment events fail closed. An empty ``MOYASAR_WEBHOOK_SECRET`` is 503. A
configured secret is compared with ``hmac.compare_digest``; a mismatch is 401.
"""

from __future__ import annotations

import logging
from uuid import uuid4

import httpx

from src.config.settings import get_settings
from src.models import Payment
from src.services import payments as pm

LIVE_SECRET = "sk_" + "live_unit_not_a_real_key"
LIVE_PUBLIC = "pk_" + "live_unit_not_a_real_key"
WEBHOOK_SECRET = "whsec_unit_not_a_real_secret"


def _live(monkeypatch, *, webhook=WEBHOOK_SECRET, secret=LIVE_SECRET):
    settings = get_settings()
    monkeypatch.setattr(settings, "moyasar_api_secret", secret)
    monkeypatch.setattr(settings, "moyasar_publishable_key", LIVE_PUBLIC)
    monkeypatch.setattr(settings, "moyasar_webhook_secret", webhook)
    pm._credential_cache.clear()


class _Result:
    def __init__(self, payment):
        self._payment = payment

    def scalar_one_or_none(self):
        return self._payment

    def scalars(self):
        return self

    def first(self):
        return self._payment


class _Session:
    def __init__(self, payment):
        self.payment = payment
        self.commits = 0

    async def execute(self, _query):
        return _Result(self.payment)

    async def commit(self):
        self.commits += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


def _payment():
    return Payment(
        id=uuid4(),
        amount=49900,
        total_halalas=49900,
        status="pending",
        currency="SAR",
        gateway="moyasar",
        gateway_payment_id="inv_unit",
        gateway_source="invoice",
        package="bidaya",
        pricing_snapshot={"expected_total_halalas": 49900, "amount": 49900, "currency": "SAR"},
    )


def _api(monkeypatch, payload):
    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            return payload

    real_client = httpx.AsyncClient

    class _Client(real_client):
        async def get(self, url, *args, **kwargs):
            if "api.moyasar.com" in str(url):
                return _Resp()
            return await super().get(url, *args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _Client)


async def _post(app, body):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/webhooks/moyasar", json=body)


async def test_verification_is_logged_once_and_skips_payment_logic(monkeypatch, caplog):
    _live(monkeypatch, webhook=None)
    from src.main import app

    def _no_session():
        raise AssertionError("verification must not open a database session")

    monkeypatch.setattr(app.state, "session_factory", _no_session, raising=False)
    secret_in_body = "whsec_must_not_appear_in_logs"
    caplog.set_level(logging.INFO, logger="src.main")
    response = await _post(
        app,
        {
            "type": "webhook_verification",
            "secret_token": secret_in_body,
            "data": {"webhook_id": "wh_1", "verification_code": "482913"},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True, "type": "webhook_verification"}
    assert "482913" not in response.text
    assert secret_in_body not in response.text
    marks = [
        record.getMessage()
        for record in caplog.records
        if "MOYASAR_WEBHOOK_VERIFICATION_CODE=" in record.getMessage()
    ]
    assert len(marks) == 1
    assert "MOYASAR_WEBHOOK_VERIFICATION_CODE=482913" in marks[0]
    assert secret_in_body not in caplog.text
    assert LIVE_SECRET not in caplog.text


async def test_verification_accepts_an_integer_code_even_when_a_secret_is_set(monkeypatch, caplog):
    _live(monkeypatch)
    from src.main import app

    monkeypatch.setattr(app.state, "session_factory", lambda: (_ for _ in ()).throw(AssertionError("no db")), raising=False)
    caplog.set_level(logging.INFO, logger="src.main")
    response = await _post(
        app,
        {
            "type": "webhook_verification",
            "secret_token": "not-the-configured-secret",
            "data": {"verification_code": 190274},
        },
    )
    assert response.status_code == 200, response.text
    assert "MOYASAR_WEBHOOK_VERIFICATION_CODE=190274" in caplog.text
    assert WEBHOOK_SECRET not in caplog.text
    assert "not-the-configured-secret" not in caplog.text


async def test_verification_without_a_code_is_still_200_and_does_not_invent_one(monkeypatch, caplog):
    _live(monkeypatch, webhook=None)
    from src.main import app

    monkeypatch.setattr(app.state, "session_factory", lambda: (_ for _ in ()).throw(AssertionError("no db")), raising=False)
    caplog.set_level(logging.INFO, logger="src.main")
    response = await _post(app, {"type": "webhook_verification", "data": {"verification_code": "12ab34"}})
    assert response.status_code == 200, response.text
    assert "MOYASAR_WEBHOOK_VERIFICATION_CODE=" not in caplog.text
    assert "12ab34" not in caplog.text
    assert "without a 6-digit code" in caplog.text


def _reject_transport(monkeypatch, app):
    def _no_session():
        raise AssertionError("a rejected payment event must not be processed")

    class _Client(httpx.AsyncClient):
        async def get(self, url, *args, **kwargs):
            raise AssertionError("a rejected payment event must not call Moyasar")

    monkeypatch.setattr(app.state, "session_factory", _no_session, raising=False)
    monkeypatch.setattr(httpx, "AsyncClient", _Client)


async def test_no_secret_rejects_payment_events(monkeypatch, caplog):
    from src.main import app

    _reject_transport(monkeypatch, app)
    caplog.set_level(logging.WARNING, logger="src.main")
    attacker = "attacker-token"
    for blank in (None, "", "   "):
        _live(monkeypatch, webhook=blank)
        response = await _post(
            app,
            {
                "type": "payment_paid",
                "secret_token": attacker,
                "data": {
                    "status": "paid",
                    "amount": 1,
                    "currency": "USD",
                    "metadata": {"order_id": str(uuid4())},
                },
            },
        )
        assert response.status_code == 503, response.text
        assert "ok" not in response.json()
        assert attacker not in response.text
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.WARNING and "MOYASAR_WEBHOOK_SECRET" in record.getMessage()
    ]
    assert len(warnings) == 3
    assert all("not configured" in message for message in warnings)
    assert attacker not in caplog.text
    assert LIVE_SECRET not in caplog.text
    assert WEBHOOK_SECRET not in caplog.text


async def test_wrong_secret_is_rejected(monkeypatch):
    _live(monkeypatch)
    from src.main import app

    _reject_transport(monkeypatch, app)
    bodies = [
        {"type": "payment_paid", "secret_token": "nope", "data": {"status": "paid"}},
        {"type": "payment_paid", "secret_token": WEBHOOK_SECRET + "x", "data": {"status": "paid"}},
        {"type": "payment_paid", "data": {"status": "paid"}},
        {"type": "payment_paid", "secret_token": "", "data": {"status": "paid"}},
    ]
    for body in bodies:
        response = await _post(app, body)
        assert response.status_code == 401, response.text
        assert WEBHOOK_SECRET not in response.text


def test_secret_match_uses_compare_digest(monkeypatch):
    import hmac

    from src.main import _moyasar_secret_ok

    calls = []
    real = hmac.compare_digest

    def _spy(left, right):
        calls.append((left, right))
        return real(left, right)

    monkeypatch.setattr(hmac, "compare_digest", _spy)
    assert _moyasar_secret_ok({"secret_token": WEBHOOK_SECRET}, WEBHOOK_SECRET.encode()) is True
    assert calls == [(WEBHOOK_SECRET.encode(), WEBHOOK_SECRET.encode())]
    assert _moyasar_secret_ok({"secret_token": "nope"}, WEBHOOK_SECRET.encode()) is False
    assert _moyasar_secret_ok({"secret_token": 123456}, WEBHOOK_SECRET.encode()) is False
    assert len(calls) == 2


async def test_correct_secret_is_accepted(monkeypatch, caplog):
    _live(monkeypatch)
    from src.main import app

    payment = _payment()
    session = _Session(payment)
    monkeypatch.setattr(app.state, "session_factory", lambda: session, raising=False)
    _api(
        monkeypatch,
        {"id": "inv_unit", "status": "paid", "amount": 49900, "currency": "SAR", "source": {"type": "creditcard"}},
    )
    applied = {"called": False}

    async def _apply(*_args, **_kwargs):
        applied["called"] = True
        return {"applied": True}

    monkeypatch.setattr("src.main._apply_paid_outcome", _apply)
    caplog.set_level(logging.DEBUG, logger="src.main")
    response = await _post(
        app,
        {
            "type": "payment_paid",
            "secret_token": WEBHOOK_SECRET,
            "data": {
                "status": "failed",
                "amount": 1,
                "currency": "USD",
                "metadata": {"order_id": str(payment.id)},
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "paid"
    assert body["payment_id"] == str(payment.id)
    assert payment.status == "paid"
    assert applied["called"] is True
    assert WEBHOOK_SECRET not in response.text
    assert WEBHOOK_SECRET not in caplog.text
    assert LIVE_SECRET not in caplog.text
