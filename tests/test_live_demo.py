"""Live demo: fictional clinic via the tenant reply agent; rate-limited, 24h retention, no payments."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import ClientProject, Payment
from src.models.automation import ReplyDraft
from src.models.tenant import TenantContact
from src.services import live_demo
from src.services import payments as pm


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture(autouse=True)
def _limits():
    live_demo.reset_limits()
    yield
    live_demo.reset_limits()


async def test_answers_from_demo_kb_and_is_labelled(maker):
    async with maker() as s:
        r = await live_demo.chat(s, "abc", "متى أوقات الدوام؟")
        assert r["demo"] and "تجريبية" in r["label"]
        assert "الأحد" in r["reply"]
        proj = await live_demo.ensure_demo_project(s)
        assert proj.status == "demo" and proj.wa_access_token_enc is None
        drafts = (await s.execute(select(ReplyDraft).where(ReplyDraft.project_id == proj.id))).scalars().all()
        assert drafts and all(d.status == "demo" for d in drafts)


async def test_handoff_then_visitor_can_continue(maker):
    async with maker() as s:
        r1 = await live_demo.chat(s, "x", "أبي أكلم موظف")
        assert r1["kind"] == "handoff"
        r2 = await live_demo.chat(s, "x", "وين موقع العيادة؟")
        assert "شمال الرياض" in r2["reply"]


async def test_never_takes_payments(maker):
    async with maker() as s:
        r = await live_demo.chat(s, "p", "أبي أدفع عربون بالبطاقة")
        assert r["kind"] == "demo_no_payment" and "لا يتم فيها أي دفع" in r["reply"]
        assert "http" not in r["reply"]
        proj = await live_demo.ensure_demo_project(s)
        with pytest.raises(pm.PaymentError):
            await pm.create_payment(s, "radd", "x", "0555", None, project_id=proj.id)
        assert (await s.execute(select(func.count()).select_from(Payment))).scalar() == 0


async def test_demo_project_is_not_active_and_kb_seeded_once(maker):
    async with maker() as s:
        a = await live_demo.ensure_demo_project(s)
        b = await live_demo.ensure_demo_project(s)
        assert a.id == b.id
        n = (await s.execute(select(func.count()).select_from(ClientProject).where(ClientProject.status == "active"))).scalar()
        assert n == 0


async def test_purge_after_24h(maker):
    async with maker() as s:
        await live_demo.chat(s, "old", "كم سعر التبييض؟")
        proj = await live_demo.ensure_demo_project(s)
        assert await live_demo.purge_expired(s, datetime.now(UTC)) == 0
        purged = await live_demo.purge_expired(s, datetime.now(UTC) + timedelta(hours=25))
        await s.commit()
        assert purged >= 2
        assert (await s.execute(select(func.count()).select_from(ReplyDraft).where(ReplyDraft.project_id == proj.id))).scalar() == 0
        assert (await s.execute(select(func.count()).select_from(TenantContact).where(TenantContact.project_id == proj.id))).scalar() == 0


async def test_endpoint_rate_limited(maker, monkeypatch):
    from src.main import app

    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        info = (await c.get("/api/live-demo")).json()
        assert info["demo"] and info["retention_hours"] == 24
        codes = [(await c.post("/api/live-demo/chat", json={"session_id": "s", "text": "وين موقعكم؟"})).status_code
                 for _ in range(10)]
    assert codes[0] == 200 and 429 in codes


def test_whatsapp_demo_config_optional(monkeypatch):
    monkeypatch.delenv("DEMO_WHATSAPP_NUMBER", raising=False)
    assert live_demo.whatsapp_config()["enabled"] is False
    monkeypatch.setenv("DEMO_WHATSAPP_NUMBER", "+966 5000 00000")
    cfg = live_demo.whatsapp_config()
    assert cfg["enabled"] is True
    assert cfg["number"] == "966500000000"
    assert cfg["link"] is None


def test_landing_has_labelled_widget():
    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as client:
        html = client.get("/").text
    assert 'id="chat-demo"' in html and "مثال توضيحي" in html and "/api/live-demo/chat" not in html
