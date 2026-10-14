"""Tenant Reply Agent: a customer's own WhatsApp number answers from *that*
customer's knowledge base, never pitches Al-Narjis, never lands in the lead CRM."""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core import portal_auth
from src.db.session import Base
from src.models import AcquisitionLead, ClientProject, InboundMessage
from src.models.automation import LeadPipeline, ReplyDraft
from src.models.tenant import TenantContact
from src.models.usage import UsageEvent
from src.services import smart_reply, tenant_reply, whatsapp_webhook
from src.services.agent_tools import knowledge_base

NOW = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
FAQ_A = "ساعات العمل: نفتح يوميًا من الساعة 9 صباحًا حتى 11 مساءً. التوصيل داخل الرياض مجاني للطلبات فوق 200 ريال."
FAQ_B = "سياسة الاسترجاع في مخبز السنابل: يمكن الاسترجاع خلال 3 أيام مع الفاتورة."


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    async def _fake(*a, **k):
        return {"ok": True}

    from src.services import telegram_sender

    monkeypatch.setattr(telegram_sender, "send_owner_alert", _fake)


@pytest.fixture
def posts(monkeypatch):
    sent: list[tuple] = []

    async def _post(pnid, token, body):
        sent.append((pnid, token, body))
        return {"ok": True, "provider_message_id": f"wamid.out{len(sent)}"}

    monkeypatch.setattr(tenant_reply, "_post_tenant", _post)
    return sent


async def _setup(s):
    a = ClientProject(client_name="متجر الورد", phone="0555000001", package="radd", status="active",
                      wa_phone_number_id="111")
    b = ClientProject(client_name="مخبز السنابل", phone="0555000002", package="radd", status="active",
                      wa_phone_number_id="222")
    s.add_all([a, b])
    await s.flush()
    await knowledge_base.add_doc(s, "FAQ", FAQ_A, project_id=a.id)
    await knowledge_base.add_doc(s, "FAQ", FAQ_B, project_id=b.id)
    await knowledge_base.add_doc(s, "Narjis", "باقة ردّ من النرجس للذكاء بسعر 599 ريال", project_id=None)
    await s.commit()
    return a, b


def _payload(pnid, mid, text, sender="966511111111"):
    return {"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": pnid},
        "contacts": [{"wa_id": sender, "profile": {"name": "سارة"}}],
        "messages": [{"id": mid, "from": sender, "type": "text", "text": {"body": text},
                      "timestamp": str(int(NOW.timestamp()))}],
    }}]}]}


async def test_inbound_on_customer_number_is_tagged_and_kept_out_of_the_lead_crm(maker):
    async with maker() as s:
        a, _ = await _setup(s)
        summary = await whatsapp_webhook.process_inbound_payload(s, _payload("111", "wamid.t1", "متى ساعات العمل؟"))
        await s.commit()
        assert summary["tenant_messages"] == 1
        rec = (await s.execute(select(InboundMessage))).scalar_one()
        assert rec.project_id == a.id and rec.processing_status == "tenant" and rec.lead_id is None
        assert (await s.execute(select(AcquisitionLead))).scalars().all() == []
        c = (await s.execute(select(TenantContact))).scalar_one()
        assert c.project_id == a.id and c.display_name == "سارة"
        # usage metering keeps working
        assert [e.kind for e in (await s.execute(select(UsageEvent))).scalars()] == ["conversation"]


async def test_reply_comes_from_the_projects_own_kb_only(maker):
    async with maker() as s:
        a, b = await _setup(s)
        d = await tenant_reply.handle_inbound(s, project=a, contact="966511111111", text="متى ساعات العمل والتوصيل؟")
        assert d.project_id == a.id and d.status == "pending" and d.lead_id is None
        assert "9 صباحًا" in d.draft_text
        assert "الاسترجاع" not in d.draft_text  # project B's KB never leaks into A
        assert not tenant_reply.contains_pitch(d.draft_text)
        assert (await s.execute(select(LeadPipeline))).scalars().all() == []
        assert (await s.execute(select(AcquisitionLead))).scalars().all() == []


async def test_never_pitches_narjis_plans_even_on_buying_language(maker):
    async with maker() as s:
        a, _ = await _setup(s)
        for i, text in enumerate(["أبغى أشترك في الباقة كم السعر", "ابي اشتري الحين", "عندي مشكلة في المبيعات وأحتاج نظام ذكاء اصطناعي"]):
            d = await tenant_reply.handle_inbound(s, project=a, contact=f"96650000000{i}", text=text)
            assert d is not None
            assert not tenant_reply.contains_pitch(d.draft_text), d.draft_text
            assert "599" not in d.draft_text and "payment_url" not in d.draft_text
            assert d.kind in ("reply", "handoff")


def test_pitch_guard_catches_narjis_content():
    assert tenant_reply.contains_pitch("اشترك في باقة «ردّ» عبر karmaai.online")
    assert tenant_reply.contains_pitch("رابط الدفع {payment_url}")
    assert not tenant_reply.contains_pitch("التوصيل مجاني داخل الرياض")


async def test_no_answer_and_explicit_request_hand_off_to_a_human(maker):
    async with maker() as s:
        a, _ = await _setup(s)
        d = await tenant_reply.handle_inbound(s, project=a, contact="966522222222", text="أبي أكلم موظف")
        assert d.kind == "handoff" and "متجر الورد" in d.draft_text
        # while handed off, the agent stays silent
        assert await tenant_reply.handle_inbound(s, project=a, contact="966522222222", text="ساعات العمل؟") is None
        d2 = await tenant_reply.handle_inbound(s, project=a, contact="966533333333", text="هل تبيعون سيارات مستعملة؟")
        assert d2.kind == "handoff" and d2.meta["handoff"] == "no_answer"


async def test_review_mode_is_default_and_auto_sends_from_the_customer_number(maker, posts):
    async with maker() as s:
        a, _ = await _setup(s)
        assert tenant_reply.mode_of(a) == "review"
        d = await tenant_reply.handle_inbound(s, project=a, contact="966544444444", text="ساعات العمل؟")
        assert d.status == "pending" and posts == []
        a.reply_mode = "auto"
        # auto without a per-project token: queued, never sent from Al-Narjis's number
        d = await tenant_reply.handle_inbound(s, project=a, contact="966555555555", text="ساعات العمل؟")
        assert d.status == "pending" and d.meta.get("queued") == "no_project_token" and posts == []
        a.wa_access_token_enc = tenant_reply.encrypt_token("customer-token-x")
        d = await tenant_reply.handle_inbound(s, project=a, contact="966566666666", text="ساعات العمل؟")
        assert d.status == "sent"
        assert posts[0][0] == "111" and posts[0][1] == "customer-token-x"
        assert "customer-token-x" not in (a.wa_access_token_enc or "")


async def test_inactive_or_off_projects_do_not_reply(maker):
    async with maker() as s:
        a, b = await _setup(s)
        a.status = "expired"
        b.reply_mode = "off"
        assert await tenant_reply.handle_inbound(s, project=a, contact="9665", text="ساعات العمل؟") is None
        assert await tenant_reply.handle_inbound(s, project=b, contact="9665", text="الاسترجاع؟") is None


async def test_owner_queue_excludes_tenant_drafts(maker):
    async with maker() as s:
        a, _ = await _setup(s)
        d = await tenant_reply.handle_inbound(s, project=a, contact="966577777777", text="ساعات العمل؟")
        s.add(ReplyDraft(channel="telegram", recipient="1", kind="reply", draft_text="x", status="pending"))
        await s.commit()
        owner = await smart_reply.list_drafts(s)
        assert len(owner) == 1 and owner[0].project_id is None
        with pytest.raises(LookupError):
            await smart_reply.approve(s, d.id)


# ---------------------------------------------------------------- portal queue isolation

def _client(maker, project=None):
    from src.main import app

    app.state.session_factory = maker
    cookies = {portal_auth.COOKIE_NAME: portal_auth.make_session_token(project)} if project else {}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", cookies=cookies)


async def test_portal_queue_is_per_project(maker, posts):
    async with maker() as s:
        a, b = await _setup(s)
        da = await tenant_reply.handle_inbound(s, project=a, contact="966588888888", text="ساعات العمل؟")
        await s.commit()
    async with _client(maker, project=b) as c:
        r = await c.get(f"/api/portal/projects/{b.id}/replies")
        assert r.status_code == 200 and r.json()["drafts"] == []
        # B cannot read or act on A's queue, even knowing A's ids
        assert (await c.get(f"/api/portal/projects/{a.id}/replies")).status_code == 401
        assert (await c.post(f"/api/portal/projects/{b.id}/replies/{da.id}/approve")).status_code == 404
    async with _client(maker) as c:
        assert (await c.get(f"/api/portal/projects/{a.id}/replies")).status_code == 401
    async with _client(maker, project=a) as c:
        r = await c.get(f"/api/portal/projects/{a.id}/replies")
        assert [d["id"] for d in r.json()["drafts"]] == [str(da.id)]
        r = await c.post(f"/api/portal/projects/{a.id}/replies/{da.id}/approve", json={"text": "نفتح 9 صباحًا 🌿"})
        assert r.status_code == 200 and r.json()["final_text"] == "نفتح 9 صباحًا 🌿"
        assert (await c.post(f"/api/portal/projects/{a.id}/reply-settings", json={"mode": "auto"})).status_code == 403
        assert (await c.post(f"/api/portal/projects/{a.id}/reply-settings", json={"mode": "off"})).json()["mode"] == "off"
        contacts = (await c.get(f"/api/portal/projects/{a.id}/contacts")).json()["contacts"]
        assert [x["contact"] for x in contacts] == ["966588888888"]


async def test_owner_sets_token_without_it_ever_being_returned(maker):
    from src.core.owner_auth import make_session_token

    async with maker() as s:
        a, _ = await _setup(s)
    from src.main import app

    app.state.session_factory = maker
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                 cookies={"narjis_owner": make_session_token()}) as c:
        r = await c.post(f"/api/owner/projects/{a.id}/whatsapp-token", json={"token": "secret-tok-123"})
        assert r.status_code == 200 and "secret-tok-123" not in r.text and r.json()["can_send"] is True
        r = await c.post(f"/api/owner/projects/{a.id}/reply-settings", json={"mode": "auto"})
        assert r.json()["mode"] == "auto"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.post(f"/api/owner/projects/{a.id}/whatsapp-token", json={"token": "x"})).status_code == 401


async def test_webhook_smart_replies_route_tenant_traffic_away_from_the_sales_advisor(maker, monkeypatch):
    from types import SimpleNamespace

    from src.interfaces import whatsapp_routes

    async with maker() as s:
        a, _ = await _setup(s)
        await whatsapp_webhook.process_inbound_payload(s, _payload("111", "wamid.r1", "ساعات العمل؟"))
        await s.commit()

    async def _never(*a, **k):
        raise AssertionError("Al-Narjis sales advisor must not answer a customer's customers")

    monkeypatch.setattr(smart_reply, "safe_handle_inbound", _never)
    req = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(session_factory=maker, model_provider=None)))
    await whatsapp_routes._smart_replies(req, _payload("111", "wamid.r1", "ساعات العمل؟"), set())
    async with maker() as s:
        d = (await s.execute(select(ReplyDraft))).scalar_one()
        assert d.project_id == a.id and "9 صباحًا" in d.draft_text
