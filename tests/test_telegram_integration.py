"""Telegram Bot API integration tests (in-memory DB).

Covers: credential gating, secret-header verification, inbound mapping +
intent classification, duplicate protection, opt-out governance, health probe,
and secret leakage prevention.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.models import AcquisitionLead, InboundMessage, OutboundMessage
from src.services import telegram_sender as ts
from src.interfaces.telegram_routes import WELCOME_TEXT
from src.services.lead_normalize import normalize_phone
from src.services.telegram_webhook import derived_secrets


async def _make_engine():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def maker():
    engine, maker = await _make_engine()
    yield maker
    await engine.dispose()


@pytest.fixture
async def api(maker):
    from src.main import app

    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"narjis_owner": make_session_token()},
    ) as client:
        yield client


SECRET = "TEST-TG-SECRET"
TOKEN = "123456:TEST-BOT-TOKEN"
CHAT = "966555555555"      # chat id used as the sender handle
OWNER_CHAT = "777777"


@contextmanager
def _creds(token=TOKEN, secret=SECRET, owner=OWNER_CHAT):
    from src.config import settings as s

    names = ("telegram_token", "telegram_webhook_secret", "telegram_owner_chat_id")
    old = [getattr(s, n) for n in names]
    object.__setattr__(s, "telegram_token", token)
    object.__setattr__(s, "telegram_webhook_secret", secret)
    object.__setattr__(s, "telegram_owner_chat_id", owner)
    try:
        yield
    finally:
        for n, v in zip(names, old):
            object.__setattr__(s, n, v)


async def _insert_lead(maker, *, company="TestCo", phone="0555555555", status="NEW", **kw) -> AcquisitionLead:
    async with maker() as s:
        lead = AcquisitionLead(
            id=uuid4(),
            company_name=company,
            segment=kw.pop("segment", "services"),
            suggested_package=kw.pop("suggested_package", "social"),
            phone=normalize_phone(phone),
            phone_raw=phone,
            lead_status=status,
            priority=kw.pop("priority", "MEDIUM"),
            **kw,
        )
        s.add(lead)
        await s.commit()
        await s.refresh(lead)
        return lead


def _update(message_id: int, text: str, chat_id: str = CHAT) -> dict:
    return {
        "update_id": 1000 + message_id,
        "message": {
            "message_id": message_id,
            "from": {"id": 42, "is_bot": False, "first_name": "عميل"},
            "chat": {"id": int(chat_id), "type": "private"},
            "date": 1700000000,
            "text": text,
        },
    }


async def _post(client, update: dict, secret: str = SECRET):
    raw = json.dumps(update).encode("utf-8")
    return await client.post(
        "/webhooks/telegram",
        content=raw,
        headers={"X-Telegram-Bot-Api-Secret-Token": secret},
    )


@pytest.fixture(autouse=True)
def _no_real_telegram_http(monkeypatch):
    """Webhook side effects (welcome/alert) must never reach the network in tests."""
    monkeypatch.setattr(ts, "_post", _ok_post)


# ---------------------------------------------------------------------------
# 1) Credential gating + secret-free status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_disabled_without_token(self):
        with _creds(token=None):
            assert ts.is_enabled() is False
            status = ts.send_status()
            assert status["enabled"] is False
            assert status["token_configured"] is False
            assert status["fallback"] == "t.me"
            assert TOKEN not in json.dumps(status)

    def test_enabled_with_token(self):
        with _creds():
            assert ts.is_enabled() is True
            status = ts.send_status()
            assert status["enabled"] is True
            assert status["disabled_reason"] is None
            assert TOKEN not in json.dumps(status)


# ---------------------------------------------------------------------------
# 2-3) Webhook verification: secret header
# ---------------------------------------------------------------------------

class TestWebhookSecurity:
    async def test_missing_secret_header_rejected(self, api):
        with _creds():
            r = await api.post("/webhooks/telegram", content=json.dumps(_update(1, "مرحباً")).encode())
            assert r.status_code == 403
            assert r.json()["status"] == "invalid_secret"

    async def test_wrong_secret_rejected(self, api):
        with _creds():
            r = await _post(api, _update(1, "مرحباً"), secret="wrong")
            assert r.status_code == 403
            assert r.json()["status"] == "invalid_secret"

    async def test_without_env_secret_uses_derived_secret(self, api):
        with _creds(secret=None):
            for i, candidate in enumerate(derived_secrets(), start=1):
                r = await _post(api, _update(i, "مرحباً"), secret=candidate)
                assert r.status_code == 200
                assert r.json()["status"] == "ok"

            bad = await _post(api, _update(99, "مرحباً"), secret="wrong")
            assert bad.status_code == 403
            assert bad.json()["status"] == "invalid_secret"

    async def test_rejections_visible_in_health_without_secrets(self, api):
        with _creds():
            await _post(api, _update(1, "مرحباً"), secret="wrong")
            health = (await api.get("/webhooks/telegram/health")).json()
            rx = health["webhook_rx"]
            assert rx["rejected_total"] >= 1
            assert rx["last_reject"]["reason"] == "secret_mismatch"
            assert TOKEN not in json.dumps(health)
            assert SECRET not in json.dumps(health)


# ---------------------------------------------------------------------------
# 4) Inbound mapping + intent promotion
# ---------------------------------------------------------------------------

class TestInbound:
    async def test_inbound_maps_and_promotes_lead_by_phone(self, maker, api):
        with _creds():
            lead = await _insert_lead(maker, company="BuyerCo", phone="0555555555")
            r = await _post(api, _update(1, "كم السعر في الباقة؟ 0555555555"))
            assert r.status_code == 200
            body = r.json()
            assert body["summary"]["messages_processed"] == 1
            assert body["summary"]["mapped_leads"] == 1

            async with maker() as s:
                msg = (await s.execute(
                    select(InboundMessage).where(InboundMessage.provider_message_id == "tg:" + CHAT + ":1")
                )).scalar_one()
                assert msg.lead_id == lead.id
                assert msg.intent == "PRICE"
                assert msg.buying_signal is True
                assert msg.payload_hash

                refreshed = (await s.execute(
                    select(AcquisitionLead).where(AcquisitionLead.id == lead.id)
                )).scalar_one()
                assert refreshed.lead_status == "INTERESTED"
                assert refreshed.priority == "HIGH"

    async def test_unmatched_when_no_phone_known(self, maker, api):
        with _creds():
            await _insert_lead(maker, company="OtherCo", phone="0500000000")
            r = await _post(api, _update(10, "أهلاً، أبي معلومات"))
            assert r.status_code == 200
            assert r.json()["summary"]["unmatched"] == 1

    async def test_second_message_reuses_prior_lead_link(self, maker, api):
        with _creds():
            await _insert_lead(maker, company="ReturnCo", phone="0555555555")
            first = await _post(api, _update(20, "مرحبا 0555555555"))
            assert first.json()["summary"]["mapped_leads"] == 1

            second = await _post(api, _update(21, "طيب خلونا نبدأ"))
            assert second.json()["summary"]["mapped_leads"] == 1

            async with maker() as s:
                rows = (await s.execute(
                    select(InboundMessage).where(InboundMessage.provider_message_id.like("tg:%"))
                )).scalars().all()
                assert len(rows) == 2
                assert all(r.lead_id is not None for r in rows)


# ---------------------------------------------------------------------------
# 5) Duplicate protection
# ---------------------------------------------------------------------------

class TestDedup:
    async def test_duplicate_message_id_skipped(self, maker, api):
        with _creds():
            await _insert_lead(maker)
            payload = _update(30, "أهلاً 0555555555")
            first = await _post(api, payload)
            second = await _post(api, payload)
            assert first.json()["summary"]["messages_processed"] == 1
            assert second.json()["summary"]["duplicates_skipped"] == 1
            async with maker() as s:
                count = len((await s.execute(select(InboundMessage))).scalars().all())
                assert count == 1


# ---------------------------------------------------------------------------
# 6) Opt-out governance
# ---------------------------------------------------------------------------

class TestOptOut:
    async def test_opt_out_marks_do_not_contact_and_blocks_sends(self, maker, api):
        with _creds():
            lead = await _insert_lead(maker, company="OptOutCo", phone="0555555555")
            r = await _post(api, _update(40, "لا ترسل لي رسائل 0555555555"))
            assert r.status_code == 200

            async with maker() as s:
                refreshed = (await s.execute(
                    select(AcquisitionLead).where(AcquisitionLead.id == lead.id)
                )).scalar_one()
                assert refreshed.opt_out is True
                assert refreshed.lead_status == "DO_NOT_CONTACT"

            original = ts._post

            async def _boom(*args, **kwargs):
                raise AssertionError("opt-out lead must never be sent")

            ts._post = _boom  # type: ignore[assignment]
            async with maker() as s:
                result = await ts.send_now(s, lead_id=lead.id, chat_id=CHAT, text="مرحباً")
                assert result["status"] == "blocked"
                assert result["reason"] == "opted_out"
            ts._post = original  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 7) Send lifecycle: ack required, never silently sent
# ---------------------------------------------------------------------------

class TestSendLifecycle:
    async def test_send_success_requires_ack(self, maker):
        with _creds():
            lead = await _insert_lead(maker)
            original = ts._post
            ts._post = _ok_post  # type: ignore[assignment]
            async with maker() as s:
                result = await ts.send_now(s, lead_id=lead.id, chat_id=CHAT, text="مرحباً 👋")
                assert result["status"] == "sent"
                assert result["acknowledged"] is True
                assert result["provider"] == "telegram_bot"
                record = (await s.execute(
                    select(OutboundMessage).order_by(OutboundMessage.created_at.desc()).limit(1)
                )).scalar_one()
                assert record.status == "sent"
                assert record.acknowledged is True
                assert record.sent_at is not None
            ts._post = original  # type: ignore[assignment]

    async def test_send_failure_never_marks_sent(self, maker):
        with _creds():
            lead = await _insert_lead(maker)
            original = ts._post
            ts._post = _fail_post  # type: ignore[assignment]
            async with maker() as s:
                result = await ts.send_now(s, lead_id=lead.id, chat_id=CHAT, text="مرحباً")
                assert result["status"] == "failed"
                assert result["acknowledged"] is False
                assert result["sent_at"] is None
                record = (await s.execute(
                    select(OutboundMessage).order_by(OutboundMessage.created_at.desc()).limit(1)
                )).scalar_one()
                assert record.status == "failed"
                assert record.retry_count == 1
            ts._post = original  # type: ignore[assignment]

    async def test_no_credentials_holds_awaiting_credential(self, maker):
        with _creds(token=None):
            lead = await _insert_lead(maker)
            async with maker() as s:
                result = await ts.send_now(s, lead_id=lead.id, chat_id=CHAT, text="مرحباً")
                assert result["status"] == "awaiting_credential"
                assert result["fallback"] == "t.me"
                record = (await s.execute(
                    select(OutboundMessage).order_by(OutboundMessage.created_at.desc()).limit(1)
                )).scalar_one()
                assert record.status == "awaiting_credential"


# ---------------------------------------------------------------------------
# 8) Health probe
# ---------------------------------------------------------------------------

class TestHealth:
    async def test_health_reports_configured_and_inbound_stats(self, maker, api):
        with _creds():
            await _insert_lead(maker)
            r0 = await api.get("/webhooks/telegram/health")
            assert r0.status_code == 200
            assert r0.json()["configured"] is True
            assert r0.json()["secret_source"] == "explicit"
            assert r0.json()["sender_enabled"] is True

            await _post(api, _update(50, "كم السعر؟ 0555555555"))

            health = (await api.get("/webhooks/telegram/health")).json()
            assert health["telegram"]["total"] >= 1
            assert health["telegram"]["mapped"] >= 1
            assert health["inbound"]["last_processing_status"] == "processed"

    async def test_health_reports_derived_secret_when_env_missing(self, api):
        with _creds(secret=None):
            health = (await api.get("/webhooks/telegram/health")).json()
            assert health["configured"] is True
            assert health["disabled_reason"] is None
            assert health["secret_source"] == "derived"
            body = json.dumps(health)
            for candidate in derived_secrets():
                assert candidate not in body


# ---------------------------------------------------------------------------
# 9) Secret leakage prevention
# ---------------------------------------------------------------------------

class TestSecrets:
    async def test_endpoints_never_contain_credentials(self, api):
        with _creds():
            for ep in ("/webhooks/telegram/health", "/webhooks/whatsapp/health"):
                r = await api.get(ep)
                assert r.status_code == 200, ep
                assert TOKEN not in r.text, ep
                assert SECRET not in r.text, ep

            status = ts.send_status()
            assert TOKEN not in json.dumps(status)
            assert SECRET not in json.dumps(status)

    async def test_outbound_record_never_stores_secrets(self, maker):
        with _creds():
            lead = await _insert_lead(maker)
            original = ts._post
            ts._post = _ok_post  # type: ignore[assignment]
            async with maker() as s:
                await ts.send_now(s, lead_id=lead.id, chat_id=CHAT, text="مرحباً")
                record = (await s.execute(
                    select(OutboundMessage).order_by(OutboundMessage.created_at.desc()).limit(1)
                )).scalar_one()
                dumped = json.dumps(record.to_dict())
                assert TOKEN not in dumped
                assert SECRET not in dumped
            ts._post = original  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 10) Side effects: first-contact welcome + owner alert
# ---------------------------------------------------------------------------

class TestSideEffects:
    @staticmethod
    def _capture(monkeypatch):
        alerts: list[str] = []

        async def _rec(text: str) -> dict:
            alerts.append(text)
            return {"ok": True}

        monkeypatch.setattr(ts, "send_owner_alert", _rec)
        return alerts

    async def test_welcome_sent_once_and_owner_alerted_per_message(self, maker, api, monkeypatch):
        alerts = self._capture(monkeypatch)
        with _creds():
            first = await _post(api, _update(60, "مرحبا، كم الأسعار؟"))
            second = await _post(api, _update(61, "طيب"))
            assert first.status_code == 200
            assert second.status_code == 200

        async with maker() as s:
            rows = (await s.execute(
                select(OutboundMessage).where(OutboundMessage.channel == "telegram")
            )).scalars().all()
            assert len(rows) == 1
            assert rows[0].status == "sent"
            assert rows[0].phone == CHAT
            assert rows[0].text == WELCOME_TEXT

        assert len(alerts) == 2
        assert "كم الأسعار؟" in alerts[0]
        assert str(int(CHAT)) in alerts[0]

    async def test_owner_own_chat_gets_welcome_but_no_self_alert(self, maker, api, monkeypatch):
        alerts = self._capture(monkeypatch)
        with _creds(owner=CHAT):
            r = await _post(api, _update(70, "تجربة من المالك"))
            assert r.status_code == 200

        assert alerts == []
        async with maker() as s:
            rows = (await s.execute(
                select(OutboundMessage).where(OutboundMessage.channel == "telegram")
            )).scalars().all()
            assert len(rows) == 1
            assert rows[0].status == "sent"

    async def test_duplicate_update_triggers_no_side_effects(self, maker, api, monkeypatch):
        alerts = self._capture(monkeypatch)
        payload = _update(80, "أهلاً")
        with _creds():
            await _post(api, payload)
            alerts.clear()
            dup = await _post(api, payload)
            assert dup.json()["summary"]["duplicates_skipped"] == 1

        assert alerts == []
        async with maker() as s:
            rows = (await s.execute(
                select(OutboundMessage).where(OutboundMessage.channel == "telegram")
            )).scalars().all()
            assert len(rows) == 1


# ---------------------------------------------------------------------------
# Stub posts (override the real HTTP seam)
# ---------------------------------------------------------------------------

async def _ok_post(method, payload) -> dict:
    return {"ok": True, "status_code": 200, "provider_message_id": 998877}


async def _fail_post(method, payload) -> dict:
    return {
        "ok": False,
        "status_code": 403,
        "error": "Forbidden: bot was blocked by the user",
        "error_code": "403",
    }
