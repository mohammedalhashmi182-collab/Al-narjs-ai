"""Owner-gated smart replies, lead pipeline, Messenger webhook and social drafts."""

from __future__ import annotations

import hashlib
import hmac
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.models import AcquisitionLead, OutboundMessage, Payment
from src.models.automation import LeadPipeline, ReplyDraft, SocialPostDraft
from src.services import catalog, lead_pipeline, payments, smart_reply, social_agent
from src.services import whatsapp_sender as ws

SECRET = "TEST-APP-SECRET"
FB_SECRET = "FB-APP-SECRET"
WA_SENDER = "966511112222"


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _client(maker, owner: bool = True):
    from src.main import app

    app.state.session_factory = maker
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                             cookies={"narjis_owner": make_session_token()} if owner else {})


@pytest.fixture
async def api(maker):
    async with _client(maker) as c:
        yield c


@pytest.fixture
async def anon(maker):
    async with _client(maker, owner=False) as c:
        yield c


@contextmanager
def _settings(**values):
    from src.config import settings as s

    old = {k: getattr(s, k) for k in values}
    for k, v in values.items():
        object.__setattr__(s, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            object.__setattr__(s, k, v)


def _wa_creds():
    return _settings(whatsapp_token="TOK", whatsapp_phone_number_id="123", whatsapp_app_secret=SECRET,
                     whatsapp_webhook_verify_token="V", whatsapp_lead_cooldown_hours=0)


def _sig(raw: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _wa_payload(mid: str, text: str, sender: str = WA_SENDER) -> dict:
    return {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "contacts": [{"wa_id": sender}],
        "messages": [{"from": sender, "id": mid, "timestamp": 1700000000, "type": "text", "text": {"body": text}}],
    }}]}]}


async def _wa_post(api, payload: dict):
    raw = json.dumps(payload).encode()
    return await api.post("/webhooks/whatsapp", content=raw,
                          headers={"X-Hub-Signature-256": _sig(raw, SECRET), "Content-Type": "application/json"})


@pytest.fixture
def wa_sent(monkeypatch):
    calls: list[dict] = []

    async def _fake(record):
        calls.append({"to": record.phone, "text": record.text})
        return {"ok": True, "message_id": f"wamid.{len(calls)}", "provider_message_id": f"wamid.{len(calls)}"}

    monkeypatch.setattr(ws, "_post_message", _fake)
    return calls


PROBLEM = "عندي متجر إلكتروني والمبيعات ضعيفة والإعلانات ما تجيب نتيجة"


# --------------------------------------------------------------------------- wording

def test_offer_quotes_only_catalog_prices():
    text = smart_reply.plan_lines("numuw")
    assert "1,490" in text and "14,900" in text and "149" in text and "4,000" in text
    assert "رؤية 2030" in smart_reply.VISION_LINE
    for key, pkg in catalog.PACKAGES.items():
        assert f"{pkg['amount'] // 100:,}" in smart_reply.ladder_text()
    assert catalog.ADDON_AGENT["amount"] == 14900


def test_ladder_matches_owner_pricing():
    got = {k: (p["amount"] // 100, p.get("display_agents")) for k, p in catalog.PACKAGES.items()}
    assert got == {"bidaya": (790, 5), "numuw": (1490, 15), "sharikat": (2990, 35)}
    assert catalog.plan_amount("bidaya", "annual") == 10 * catalog.plan_amount("bidaya", "monthly")


# --------------------------------------------------------------------------- modes

async def test_default_mode_is_review_and_modes_validate(maker):
    async with maker() as s:
        assert await smart_reply.all_modes(s) == {"whatsapp": "review", "telegram": "review", "messenger": "review"}
        with pytest.raises(ValueError):
            await smart_reply.set_mode(s, "whatsapp", "yolo")
        with pytest.raises(ValueError):
            await smart_reply.set_mode(s, "sms", "auto")


async def test_owner_api_is_closed_to_anonymous(anon):
    for method, path in [("GET", "/api/owner/automation/channels"), ("GET", "/api/owner/automation/drafts"),
                         ("PUT", "/api/owner/automation/channels/whatsapp"), ("GET", "/api/owner/automation/setup"),
                         ("POST", "/api/owner/automation/social/generate-week")]:
        r = await anon.request(method, path, json={"mode": "auto"})
        assert r.status_code == 401, path
    r = await anon.get("/owner/automation", follow_redirects=False)
    assert r.status_code in (302, 303, 307) and r.headers["location"] == "/login"


async def test_console_page_renders_for_owner(api):
    r = await api.get("/owner/automation")
    assert r.status_code == 200
    assert "مركز الأتمتة" in r.text and "/api/owner/automation" in r.text


# --------------------------------------------------------------------------- review flow

async def test_whatsapp_inbound_in_review_mode_only_drafts(maker, api, wa_sent):
    with _wa_creds():
        r = await _wa_post(api, _wa_payload("wamid.in1", PROBLEM))
        assert r.status_code == 200
    assert wa_sent == []
    async with maker() as s:
        drafts = (await s.execute(select(ReplyDraft))).scalars().all()
        assert len(drafts) == 1
        d = drafts[0]
        assert d.status == "pending" and d.channel == "whatsapp" and d.recipient == WA_SENDER
        assert d.plan_key in catalog.PACKAGES
        assert "ريال" in d.draft_text and "رؤية 2030" in d.draft_text
        assert (await s.execute(select(OutboundMessage))).scalars().all() == []
        pipe = await s.get(LeadPipeline, d.lead_id)
        assert pipe.stage == "qualified" and pipe.plan_key == d.plan_key
        assert (await s.get(AcquisitionLead, d.lead_id)).source == "whatsapp_inbound"


async def test_duplicate_whatsapp_delivery_does_not_redraft(maker, api, wa_sent):
    with _wa_creds():
        await _wa_post(api, _wa_payload("wamid.dup", PROBLEM))
        await _wa_post(api, _wa_payload("wamid.dup", PROBLEM))
    async with maker() as s:
        assert len((await s.execute(select(ReplyDraft))).scalars().all()) == 1


async def test_edit_then_approve_sends_edited_text_and_advances_stage(maker, api, wa_sent):
    with _wa_creds():
        await _wa_post(api, _wa_payload("wamid.in2", PROBLEM))
        drafts = (await api.get("/api/owner/automation/drafts")).json()["drafts"]
        did = drafts[0]["id"]
        r = await api.post(f"/api/owner/automation/drafts/{did}/edit", json={"text": "نص معدّل من المالك"})
        assert r.status_code == 200 and r.json()["final_text"] == "نص معدّل من المالك"
        r = await api.post(f"/api/owner/automation/drafts/{did}/approve", json={})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "sent"
    assert wa_sent == [{"to": wa_sent[0]["to"], "text": "نص معدّل من المالك"}]
    async with maker() as s:
        d = (await s.execute(select(ReplyDraft))).scalars().one()
        pipe = await s.get(LeadPipeline, d.lead_id)
        assert pipe.stage == "offer_sent" and pipe.next_followup_at is not None
    # A decided draft cannot be approved twice.
    r = await api.post(f"/api/owner/automation/drafts/{did}/approve", json={})
    assert r.status_code == 409


async def test_reject_never_sends(maker, api, wa_sent):
    with _wa_creds():
        await _wa_post(api, _wa_payload("wamid.in3", PROBLEM))
        did = (await api.get("/api/owner/automation/drafts")).json()["drafts"][0]["id"]
        r = await api.post(f"/api/owner/automation/drafts/{did}/reject", json={"reason": "مو مناسب"})
        assert r.json()["status"] == "rejected"
    assert wa_sent == []
    assert (await api.get("/api/owner/automation/drafts")).json()["drafts"] == []


async def test_off_mode_records_nothing_and_auto_mode_sends(maker, api, wa_sent):
    with _wa_creds():
        assert (await api.put("/api/owner/automation/channels/whatsapp", json={"mode": "off"})).status_code == 200
        await _wa_post(api, _wa_payload("wamid.off", PROBLEM))
        async with maker() as s:
            assert (await s.execute(select(ReplyDraft))).scalars().all() == []
        await api.put("/api/owner/automation/channels/whatsapp", json={"mode": "auto"})
        await _wa_post(api, _wa_payload("wamid.auto", PROBLEM, sender="966533334444"))
    assert len(wa_sent) == 1
    async with maker() as s:
        assert (await s.execute(select(ReplyDraft))).scalars().one().status == "sent"


async def test_opt_out_creates_no_reply_and_marks_lost(maker):
    async with maker() as s:
        assert await smart_reply.handle_inbound(s, channel="telegram", recipient="77", text=PROBLEM) is not None
        assert await smart_reply.handle_inbound(s, channel="telegram", recipient="77", text="لا ترسل لي رسائل") is None
        pipe = (await s.execute(select(LeadPipeline))).scalars().one()
        assert pipe.stage == "lost" and pipe.lost_reason == "opt_out"
        assert (await s.get(AcquisitionLead, pipe.lead_id)).opt_out is True
        assert await smart_reply.handle_inbound(s, channel="telegram", recipient="77", text=PROBLEM) is None


async def test_short_hello_gets_one_greeting_not_spam(maker):
    async with maker() as s:
        first = await smart_reply.handle_inbound(s, channel="messenger", recipient="psid1", text="السلام عليكم")
        assert first is not None and "البداية" in first.draft_text
        assert await smart_reply.handle_inbound(s, channel="messenger", recipient="psid1", text="هلا") is None


# --------------------------------------------------------------------------- payment links

async def test_ready_to_buy_drafts_payment_link_created_only_on_approval(maker, monkeypatch):
    created: list[str] = []

    async def _fake_initiate(session, payment, source, **kw):
        created.append(str(payment.id))
        return {"id": "inv_1", "checkout_url": "https://checkout.moyasar.com/invoices/inv_1?lang=ar"}

    monkeypatch.setattr(payments, "initiate_moyasar", _fake_initiate)
    sent: list[str] = []

    async def _fake_deliver(session, channel, recipient, text, lead_id):
        sent.append(text)
        return {"ok": True}

    monkeypatch.setattr(smart_reply, "deliver", _fake_deliver)
    async with maker() as s:
        await smart_reply.handle_inbound(s, channel="telegram", recipient="55", text=PROBLEM)
        d = await smart_reply.handle_inbound(s, channel="telegram", recipient="55", text="موافق نبدأ")
        assert d.kind == "payment_link" and "{payment_url}" in d.draft_text
        assert created == []  # no invoice until the owner approves
        d = await smart_reply.approve(s, d.id)
        # The buyer gets our consent-gated invoice page, never a raw Moyasar link.
        pipe = await s.get(LeadPipeline, d.lead_id)
        assert d.status == "sent" and f"/invoice/{pipe.payment_id}" in sent[0]
        assert "checkout.moyasar.com" not in sent[0] and created == []
        assert pipe.stage == "payment_link_sent" and pipe.payment_url
        pay = await s.get(Payment, pipe.payment_id)
        assert pay.package == pipe.plan_key and pay.lead_id == d.lead_id


async def test_payment_link_failure_is_reported_not_sent(maker, monkeypatch):
    async def _boom(*a, **k):
        raise payments.PaymentError("Unknown package: scale")

    monkeypatch.setattr(payments, "create_payment", _boom)
    async with maker() as s:
        await smart_reply.handle_inbound(s, channel="telegram", recipient="56", text=PROBLEM)
        pipe = (await s.execute(select(LeadPipeline))).scalars().one()
        d = await lead_pipeline.request_payment_link(s, pipe.lead_id, "numuw", billing_period="annual")
        d = await smart_reply.approve(s, d.id)
        assert d.status == "failed" and "Unknown package" in d.send_result["error"]


async def test_owner_payment_link_endpoint_validates(api, maker):
    async with maker() as s:
        await smart_reply.handle_inbound(s, channel="telegram", recipient="57", text=PROBLEM)
        await s.commit()
        lead_id = (await s.execute(select(LeadPipeline))).scalars().one().lead_id
    r = await api.post(f"/api/owner/automation/pipeline/{lead_id}/payment-link", json={"plan_key": "nope"})
    assert r.status_code == 400
    r = await api.post(f"/api/owner/automation/pipeline/{lead_id}/payment-link", json={"plan_key": "numuw"})
    assert r.status_code == 200 and r.json()["kind"] == "payment_link" and r.json()["status"] == "pending"


# --------------------------------------------------------------------------- follow-ups

async def test_followups_draft_then_lost_and_paid_detection(maker, monkeypatch):
    async def _ok(session, channel, recipient, text, lead_id):
        return {"ok": True}

    monkeypatch.setattr(smart_reply, "deliver", _ok)
    async with maker() as s:
        d = await smart_reply.handle_inbound(s, channel="telegram", recipient="88", text=PROBLEM)
        await smart_reply.approve(s, d.id)
        pipe = await s.get(LeadPipeline, d.lead_id)
        assert pipe.stage == "offer_sent"

        now = datetime.now(UTC)
        assert (await lead_pipeline.run_followups(s, now=now))["followups"] == 0
        r = await lead_pipeline.run_followups(s, now=now + timedelta(hours=25))
        assert r["followups"] == 1
        fu = (await s.execute(select(ReplyDraft).where(ReplyDraft.kind == "followup"))).scalars().one()
        assert fu.status == "pending"  # review mode: follow-ups wait for the owner too
        # Exhaust the schedule without approving: no duplicate pending follow-ups, then lost.
        for h in (100, 200, 400, 800):
            await lead_pipeline.run_followups(s, now=now + timedelta(hours=h))
        assert len((await s.execute(select(ReplyDraft).where(ReplyDraft.kind == "followup"))).scalars().all()) == 1
        assert pipe.stage == "lost" and pipe.lost_reason == "no_response"

        # A paid invoice moves another lead to paid.
        d2 = await smart_reply.handle_inbound(s, channel="telegram", recipient="89", text=PROBLEM)
        p2 = await s.get(LeadPipeline, d2.lead_id)
        pay = Payment(amount=49900, currency="SAR", package="radd", status="paid", gateway="moyasar")
        s.add(pay)
        await s.flush()
        lead_pipeline.set_stage(p2, "payment_link_sent")
        p2.payment_id = pay.id
        assert (await lead_pipeline.run_followups(s))["paid"] == 1
        assert p2.stage == "paid"
        lead_pipeline.set_stage(p2, "lost")
        assert p2.stage == "paid"  # paid never drops back


async def test_followup_schedule_target_is_dispatched(maker):
    from uuid import uuid4

    from src.models import Schedule
    from src.services.schedule_service import execute_schedule

    async with maker() as s:
        sched = Schedule(name="automation_followups", target_type="automation_followups", target_id=uuid4(),
                         payload={}, cron_expression="0 * * * *", timezone="Asia/Riyadh")
        s.add(sched)
        await s.commit()
        out = await execute_schedule(s, sched.id)
    assert out["status"] == "ok" and "followups" in out


# --------------------------------------------------------------------------- messenger

async def test_messenger_webhook_verify_signature_and_draft(maker, api):
    with _settings(meta_app_secret=FB_SECRET, messenger_verify_token="VT", meta_page_access_token=None):
        ok = await api.get("/webhooks/messenger", params={"hub.mode": "subscribe", "hub.verify_token": "VT",
                                                          "hub.challenge": "42"})
        assert ok.status_code == 200 and ok.text == "42"
        bad = await api.get("/webhooks/messenger", params={"hub.mode": "subscribe", "hub.verify_token": "no",
                                                           "hub.challenge": "42"})
        assert bad.status_code == 403
        body = {"object": "page", "entry": [{"messaging": [
            {"sender": {"id": "2468"}, "message": {"mid": "m.1", "text": PROBLEM}},
            {"sender": {"id": "999"}, "message": {"mid": "m.2", "text": "echo", "is_echo": True}},
        ]}]}
        raw = json.dumps(body).encode()
        r = await api.post("/webhooks/messenger", content=raw, headers={"X-Hub-Signature-256": "sha256=00"})
        assert r.status_code == 403
        r = await api.post("/webhooks/messenger", content=raw, headers={"X-Hub-Signature-256": _sig(raw, FB_SECRET)})
        assert r.json()["processed"] == 1
        r = await api.post("/webhooks/messenger", content=raw, headers={"X-Hub-Signature-256": _sig(raw, FB_SECRET)})
        assert r.json()["duplicates"] == 1
    async with maker() as s:
        d = (await s.execute(select(ReplyDraft))).scalars().one()
        assert d.channel == "messenger" and d.recipient == "2468" and d.status == "pending"


async def test_messenger_webhook_inert_without_secrets(api):
    with _settings(meta_app_secret=None, messenger_verify_token=None):
        r = await api.post("/webhooks/messenger", content=b"{}")
        assert r.json()["status"] == "disabled"


# --------------------------------------------------------------------------- social + setup

def test_weekly_schedule_has_seven_real_posts():
    from datetime import date

    week = social_agent.weekly_schedule(date(2026, 10, 18))
    assert len(week) == 7
    assert len({w["scheduled_for"].date() for w in week}) == 7
    assert any("رؤية 2030" in w["text"] for w in week)
    joined = "\n".join(w["text"] for w in week)
    for key in ("bidaya", "numuw", "sharikat"):
        assert f"{catalog.PACKAGES[key]['amount'] // 100:,}" in joined
    assert "%" not in joined  # no invented performance percentages


async def test_generate_week_saves_drafts_idempotently(api, maker):
    r1 = await api.post("/api/owner/automation/social/generate-week")
    r2 = await api.post("/api/owner/automation/social/generate-week")
    assert len(r1.json()["posts"]) == 7 and len(r2.json()["posts"]) == 7
    async with maker() as s:
        rows = (await s.execute(select(SocialPostDraft))).scalars().all()
        assert len(rows) == 7 and {p.status for p in rows} == {"draft"}


async def test_setup_reports_presence_and_webhook_urls_never_values(api):
    with _settings(meta_page_access_token="SUPER-SECRET-PAGE-TOKEN", public_base_url="https://karmaai.online"):
        r = await api.get("/api/owner/automation/setup")
    body = r.json()
    assert "SUPER-SECRET" not in r.text
    assert body["messenger"]["env"]["META_PAGE_ACCESS_TOKEN"] is True
    assert body["whatsapp"]["webhook_url"] == "https://karmaai.online/webhooks/whatsapp"
    assert body["telegram"]["webhook_url"] == "https://karmaai.online/webhooks/telegram"
    assert body["messenger"]["webhook_url"] == "https://karmaai.online/webhooks/messenger"
