"""WhatsApp Business Cloud API end-to-end integration tests (in-memory DB).

Covers: credential gating, ack-based send lifecycle, webhook signature
verification, inbound mapping + intent classification, duplicate protection,
opt-out governance, conversation-led reprioritization, delivery statuses, and
secret leakage prevention.
"""

from __future__ import annotations

import hashlib
import hmac
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
from src.models import AcquisitionLead, InboundMessage, LeadEvent, OutboundMessage
from src.services import whatsapp_sender as ws
from src.services.lead_normalize import normalize_phone


# ---------------------------------------------------------------------------
# Fixtures (in-memory DB + real app), mirroring test_revenue_engine.py
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SECRET = "TEST-APP-SECRET"
VERIFY = "TEST-VERIFY-TOKEN"
TOKEN = "TOPSECRETTOKEN"
PHONE_ID = "1111222233334444"


@contextmanager
def _creds(token=TOKEN, phone_id=PHONE_ID, secret=SECRET, verify=VERIFY, cooldown=0):
    """Override the settings singleton deterministically, restore afterwards."""
    from src.config import settings as s

    names = ("whatsapp_token", "whatsapp_phone_number_id", "whatsapp_app_secret",
             "whatsapp_webhook_verify_token", "whatsapp_lead_cooldown_hours")

    def _values(s, names):
        return [getattr(s, n) for n in names]

    old = _values(s, names)
    object.__setattr__(s, "whatsapp_token", token)
    object.__setattr__(s, "whatsapp_phone_number_id", phone_id)
    object.__setattr__(s, "whatsapp_app_secret", secret)
    object.__setattr__(s, "whatsapp_webhook_verify_token", verify)
    object.__setattr__(s, "whatsapp_lead_cooldown_hours", cooldown)
    try:
        yield
    finally:
        for n, v in zip(names, old):
            object.__setattr__(s, n, v)


def _sig(raw: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


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


def _inbound_payload(msg_id: str, text: str, sender: str = "966555555555") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "1",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "06552978753", "phone_number_id": PHONE_ID},
                    "contacts": [{"profile": {"name": "اختبار"}, "wa_id": sender}],
                    "messages": [{
                        "from": sender,
                        "id": msg_id,
                        "timestamp": 1700000000,
                        "type": "text",
                        "text": {"body": text},
                    }],
                },
            }],
        }],
    }


def _status_payload(provider_message_id: str, status: str, failed: bool = False) -> dict:
    entry = {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "06552978753", "phone_number_id": PHONE_ID},
        "statuses": [{
            "id": provider_message_id,
            "status": status,
            "timestamp": 1700000001,
            **({"errors": [{"code": 131026, "title": "Re-engagement message"}], "status": "failed"} if failed else {}),
        }],
    }
    return {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{"field": "messages", "value": entry}]}]}


async def _webhook_post(client, payload: dict):
    raw = json.dumps(payload).encode("utf-8")
    return await client.post(
        "/webhooks/whatsapp",
        content=raw,
        headers={"X-Hub-Signature-256": _sig(raw)},
    )


# ---------------------------------------------------------------------------
# 1-2) Credential gating + secret-free status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_disabled_without_token_or_phone(self):
        with _creds(token=None, phone_id=None):
            assert ws.is_enabled() is False
            status = ws.send_status()
            assert status["enabled"] is False
            assert status["connected"] is False
            assert status["token_configured"] is False
            assert status["phone_id_configured"] is False
            assert "wa.me" in status["fallback"]
            assert TOKEN not in json.dumps(status)
            assert PHONE_ID not in json.dumps(status)

    def test_enabled_only_with_both_credentials(self):
        with _creds(token=TOKEN, phone_id=PHONE_ID):
            assert ws.is_enabled() is True
            status = ws.send_status()
            assert status["enabled"] is True
            assert status["connected"] is True
            assert status["disabled_reason"] is None
            assert TOKEN not in json.dumps(status)
            assert PHONE_ID not in json.dumps(status)


# ---------------------------------------------------------------------------
# 3-5) Send lifecycle: ack required, never silently sent
# ---------------------------------------------------------------------------

class TestSendLifecycle:
    async def test_send_success_requires_provider_ack(self, maker):
        with _creds():
            lead = await _insert_lead(maker)
            original = ws._post_message
            ws._post_message = _ok_post  # type: ignore[assignment]

            async with maker() as s:
                result = await ws.send_now(s, lead_id=lead.id, phone=lead.phone, text="مرحباً بك مع النرجس 👋")
                assert result["status"] == "sent"
                assert result["acknowledged"] is True
                assert result["provider_message_id"] == "wamid.OUT123"
                assert result["provider"] == "meta_whatsapp_cloud"
                assert result["sent_at"] is not None

                record = (await s.execute(
                    select(OutboundMessage).order_by(OutboundMessage.created_at.desc()).limit(1)
                )).scalar_one()
                assert record.status == "sent"
                assert record.acknowledged is True
                assert record.acknowledged_at is not None
                assert record.provider_message_id == "wamid.OUT123"
                assert record.wa_me_link

                refreshed = (await s.execute(
                    select(AcquisitionLead).where(AcquisitionLead.id == lead.id)
                )).scalar_one()
                assert refreshed.lead_status in ("CONTACTED",)
                events = (await s.execute(
                    select(LeadEvent).where(LeadEvent.lead_id == lead.id)
                )).scalars().all()
                assert any(e.event_type == "message_sent" for e in events)
            ws._post_message = original  # type: ignore[assignment]

    async def test_send_failure_never_marks_sent(self, maker):
        with _creds():
            lead = await _insert_lead(maker)
            original = ws._post_message
            ws._post_message = _fail_post  # type: ignore[assignment]

            async with maker() as s:
                result = await ws.send_now(s, lead_id=lead.id, phone=lead.phone, text="مرحباً")
                assert result["status"] == "failed"
                assert result["acknowledged"] is False
                assert result["error_code"] == "130429"
                assert result["sent_at"] is None
                record = (await s.execute(
                    select(OutboundMessage).order_by(OutboundMessage.created_at.desc()).limit(1)
                )).scalar_one()
                assert record.status == "failed"
                assert record.acknowledged is False
                assert record.provider_message_id is None
                assert record.retry_count == 1
                events = (await s.execute(
                    select(LeadEvent).where(LeadEvent.lead_id == lead.id)
                )).scalars().all()
                assert any(e.event_type == "send_failed" for e in events)
            ws._post_message = original  # type: ignore[assignment]

    async def test_no_credentials_holds_awaiting_credential(self, maker):
        with _creds(token=None, phone_id=None):
            lead = await _insert_lead(maker)
            async with maker() as s:
                result = await ws.send_now(s, lead_id=lead.id, phone=lead.phone, text="مرحباً")
                assert result["status"] == "awaiting_credential"
                assert result["fallback"] == "wa.me"
                record = (await s.execute(
                    select(OutboundMessage).order_by(OutboundMessage.created_at.desc()).limit(1)
                )).scalar_one()
                assert record.status == "awaiting_credential"
                assert record.acknowledged is False

    async def test_delivery_status_applied_via_ack(self, maker):
        with _creds():
            lead = await _insert_lead(maker)
            original = ws._post_message
            ws._post_message = _ok_post  # type: ignore[assignment]
            async with maker() as s:
                await ws.send_now(s, lead_id=lead.id, phone=lead.phone, text="مرحباً")
                await s.commit()
            ws._post_message = original  # type: ignore[assignment]

            async with maker() as s:
                record = (await s.execute(
                    select(OutboundMessage).order_by(OutboundMessage.created_at.desc()).limit(1)
                )).scalar_one()
                updated = await ws.acknowledge_status(s, record.provider_message_id, "delivered")
                assert updated is not None
                assert updated.provider_status == "delivered"

                failed = await ws.acknowledge_status(s, record.provider_message_id, "failed", error_code="131026")
                assert failed is not None and failed.provider_status == "failed"
                assert failed.status == "failed"
                assert failed.error_code == "131026"

                with _creds(token=None, phone_id=None):
                    never_acked = await ws.acknowledge_status(s, "wamid.NOTHING", "delivered")
                    assert never_acked is None


# ---------------------------------------------------------------------------
# 6-7) Webhook verification + signature
# ---------------------------------------------------------------------------

class TestWebhookVerification:
    async def test_verify_get_returns_challenge(self, api):
        with _creds():
            r = await api.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": VERIFY, "hub.challenge": "12345"})
            assert r.status_code == 200
            assert r.text == "12345"

    async def test_verify_get_wrong_token_rejected(self, api):
        with _creds():
            r = await api.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345"})
            assert r.status_code == 403

    async def test_post_requires_valid_signature(self, api):
        with _creds():
            raw = json.dumps(_inbound_payload("m1", "كم السعر؟")).encode("utf-8")
            r = await api.post(
                "/webhooks/whatsapp",
                content=raw,
                headers={"X-Hub-Signature-256": "sha256=" + "0" * 64},
            )
            assert r.status_code == 403

    async def test_post_without_app_secret_is_gated(self, api):
        with _creds(secret=None, verify=None):
            raw = json.dumps(_inbound_payload("m1", "مرحباً")).encode("utf-8")
            r = await api.post(
                "/webhooks/whatsapp", content=raw,
                headers={"X-Hub-Signature-256": _sig(raw)},
            )
            assert r.status_code == 200
            assert r.json()["status"] == "disabled"


# ---------------------------------------------------------------------------
# 8) Inbound mapping + intent promotion
# ---------------------------------------------------------------------------

class TestInbound:
    async def test_inbound_maps_and_promotes_lead(self, maker, api):
        with _creds():
            lead = await _insert_lead(maker, company="BuyerCo")
            r = await _webhook_post(api, _inbound_payload("wamid.IN1", "كم السعر في الباقة؟"))
            assert r.status_code == 200
            body = r.json()
            assert body["summary"]["messages_processed"] == 1
            assert body["summary"]["mapped_leads"] == 1

            async with maker() as s:
                msg = (await s.execute(
                    select(InboundMessage).where(InboundMessage.provider_message_id == "wamid.IN1")
                )).scalar_one()
                assert msg.lead_id == lead.id
                assert msg.intent == "PRICE"
                assert msg.buying_signal is True
                assert msg.payload_hash

                refreshed = (await s.execute(
                    select(AcquisitionLead).where(AcquisitionLead.id == lead.id)
                )).scalar_one()
                assert refreshed.lead_status == "INTERESTED"
                assert refreshed.buying_signal is True
                assert refreshed.intent == "PRICE"
                assert refreshed.last_reply_at is not None
                assert refreshed.priority == "HIGH"

                events = (await s.execute(
                    select(LeadEvent).where(LeadEvent.lead_id == lead.id)
                )).scalars().all()
                assert any(e.event_type == "message_received" for e in events)
                assert any("buying_signal=True" in (e.note or "") for e in events)

    async def test_html_intent_promotes_to_demo(self, maker, api):
        with _creds():
            lead = await _insert_lead(maker, company="DemoCo")
            r = await _webhook_post(api, _inbound_payload("wamid.IN2", "ارسلوا العرض أو جربوا ديمو"))
            assert r.status_code == 200
            assert r.json()["summary"]["mapped_leads"] == 1
            async with maker() as s:
                msg = (await s.execute(
                    select(InboundMessage).where(InboundMessage.provider_message_id == "wamid.IN2")
                )).scalar_one()
                assert msg.intent
                assert msg.buying_signal is True


# ---------------------------------------------------------------------------
# 9) Duplicate protection
# ---------------------------------------------------------------------------

class TestDedup:
    async def test_duplicate_provider_message_id_skipped(self, maker, api):
        with _creds():
            await _insert_lead(maker)
            payload = _inbound_payload("wamid.DUP1", "أهلاً")
            first = await _webhook_post(api, payload)
            second = await _webhook_post(api, payload)
            assert first.json()["summary"]["messages_processed"] == 1
            assert second.json()["summary"]["duplicates_skipped"] == 1
            async with maker() as s:
                count = len((await s.execute(select(InboundMessage))).scalars().all())
                assert count == 1


# ---------------------------------------------------------------------------
# 10) Opt-out governance
# ---------------------------------------------------------------------------

class TestOptOut:
    async def test_opt_out_marks_do_not_contact_and_blocks_sends(self, maker, api):
        with _creds():
            lead = await _insert_lead(maker, company="OptOutCo")
            r = await _webhook_post(api, _inbound_payload("wamid.OPTOUT1", "لا ترسل لي رسائل مرة أخرى"))
            assert r.status_code == 200
            async with maker() as s:
                refreshed = (await s.execute(
                    select(AcquisitionLead).where(AcquisitionLead.id == lead.id)
                )).scalar_one()
                assert refreshed.opt_out is True
                assert refreshed.lead_status == "DO_NOT_CONTACT"
                assert refreshed.buying_signal is False

            original = ws._post_message

            async def _boom(*args, **kwargs):
                raise AssertionError("opt-out lead must never be sent")

            ws._post_message = _boom  # type: ignore[assignment]
            async with maker() as s:
                result = await ws.send_now(s, lead_id=lead.id, phone=lead.phone, text="مرحباً")
                assert result["status"] == "blocked"
                assert result["reason"] == "opted_out"
            ws._post_message = original  # type: ignore[assignment]

    async def test_opted_out_leads_excluded_from_wave(self, maker):
        with _creds():
            from src.services.revenue_radar import build_wave

            active = await _insert_lead(maker, company="ActiveCo")
            opted = await _insert_lead(maker, company="OptedCo")
            async with maker() as s:
                opted = (await s.execute(select(AcquisitionLead).where(AcquisitionLead.id == opted.id))).scalar_one()
                opted.opt_out = True
                await s.commit()
            wave = await build_wave(maker())
            names = [p["company"] for p in wave["wave"]]
            assert "ActiveCo" in names
            assert "OptedCo" not in names


# ---------------------------------------------------------------------------
# 11) Conversation-led reprioritization
# ---------------------------------------------------------------------------

class TestPrioritization:
    async def test_buying_signal_lead_leads_the_wave(self, maker):
        with _creds():
            from src.services.revenue_radar import build_wave

            cold = await _insert_lead(maker, company="ColdCo", status="NEW")
            hot = await _insert_lead(maker, company="HotCo", status="NEW", buying_signal=True)
            wave = await build_wave(maker())
            assert wave["wave"][0]["company"] == "HotCo"
            assert wave["wave"][0]["whatsapp"]["buying_signal"] is True


# ---------------------------------------------------------------------------
# Conversation summary + CEO visibility
# ---------------------------------------------------------------------------

class TestConversationStats:
    async def test_conversation_summary_reports_verified_only(self, maker):
        with _creds():
            lead = await _insert_lead(maker)
            original = ws._post_message
            ws._post_message = _ok_post  # type: ignore[assignment]
            async with maker() as s:
                await ws.send_now(s, lead_id=lead.id, phone=lead.phone, text="مرحباً")
                await s.commit()
            ws._post_message = original  # type: ignore[assignment]

            async with maker() as s:
                summary = await ws.conversation_summary(s)
            assert summary["totals"]["sent"] == 1
            assert summary["status"]["enabled"] is True

            with _creds(token=None, phone_id=None):
                async with maker() as s:
                    gated = await ws.conversation_summary(s)
                assert gated["connected"] is False
                assert gated["status"]["enabled"] is False

    async def test_observatory_exposes_whatsapp_block(self, maker):
        with _creds():
            from src.services.company_observatory import CompanyObservatory

            obs = CompanyObservatory(maker)
            snap = await obs.snapshot()
            assert "whatsapp" in snap
            assert "status" in snap["whatsapp"]
            assert "replies_total" in snap["whatsapp"]


# ---------------------------------------------------------------------------
# 12) Secret leakage prevention
# ---------------------------------------------------------------------------

class TestSecrets:
    async def test_api_responses_never_contain_credentials(self, maker, api):
        with _creds():
            await _insert_lead(maker)
            endpoints = [
                "/api/company/queue",
                "/api/company/radar",
                "/webhooks/whatsapp/health",
            ]
            for ep in endpoints:
                r = await api.get(ep)
                assert r.status_code == 200, ep
                text = r.text
                assert TOKEN not in text, ep
                assert PHONE_ID not in text, ep
                assert "Authorization" not in text, ep

            st = ws.send_status()
            assert TOKEN not in json.dumps(st)
            assert PHONE_ID not in json.dumps(st)

    async def test_outbound_record_never_stores_secrets(self, maker):
        with _creds():
            lead = await _insert_lead(maker)
            original = ws._post_message
            ws._post_message = _ok_post  # type: ignore[assignment]
            async with maker() as s:
                await ws.send_now(s, lead_id=lead.id, phone=lead.phone, text="مرحباً")
                record = (await s.execute(
                    select(OutboundMessage).order_by(OutboundMessage.created_at.desc()).limit(1)
                )).scalar_one()
                dumped = json.dumps(record.to_dict())
                assert TOKEN not in dumped
                assert PHONE_ID not in dumped
                assert record.error is None
            ws._post_message = original  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Stub posts (override the real HTTP seam)
# ---------------------------------------------------------------------------

async def _ok_post(record) -> dict:
    return {"ok": True, "status_code": 200, "provider_message_id": "wamid.OUT123"}


async def _fail_post(record) -> dict:
    return {
        "ok": False,
        "status_code": 429,
        "error": "Rate limit hit",
        "error_code": "130429",
    }