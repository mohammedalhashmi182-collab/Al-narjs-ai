"""Renewal reminders D-1/D0/D+3 use the WhatsApp template path and are never
marked dispatched/sent when the fallback path is used (lesson 8). Nothing is sent:
every provider call is mocked."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.config import settings as st
from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.models import ClientProject
from src.models.company import OutboundMessage
from src.services import collections, ops_monitor, wa_templates
from src.services import payments as pm

NOW = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    from src.services import email_service, telegram_sender

    async def owner(text):
        return {"ok": True}

    async def email(*a, **k):
        return True

    async def post(payload):  # pragma: no cover - must never be reached in fallback tests
        raise AssertionError("no real Meta call in tests")

    monkeypatch.setattr(telegram_sender, "send_owner_alert", owner)
    monkeypatch.setattr(email_service, "send_email", email)
    monkeypatch.setattr(wa_templates, "_post_template", post)
    monkeypatch.setattr(st, "billing_auto_send", False)
    ops_monitor._reset_throttle()
    yield
    ops_monitor._reset_throttle()


async def _project(s, end):
    proj = ClientProject(client_name="متجر", phone="0555111222", email=None, package="radd",
                         status="active", current_period_end=end)
    s.add(proj)
    await s.commit()
    pay = await pm.create_payment(s, "radd", "متجر", "0555111222", None, project_id=proj.id,
                                  is_renewal=True, founding=False)
    pay.status = "invoice"
    proj.renewal_payment_id = pay.id
    await s.commit()
    return proj, pay


@pytest.mark.parametrize("delta,stage", [(timedelta(hours=12), "d-1"), (timedelta(hours=-2), "d0"),
                                         (timedelta(days=-3, hours=-1), "d+3")])
async def test_auto_reminder_uses_renewal_template_path(maker, monkeypatch, delta, stage):
    calls = []

    async def fake_send(session, **kw):
        calls.append(kw)
        return {"ok": True, "path": "template", "template": "renewal_reminder_ar"}

    monkeypatch.setattr(st, "billing_auto_send", True)
    monkeypatch.setattr(wa_templates, "send_business_initiated", fake_send)
    async with maker() as s:
        _, pay = await _project(s, NOW + delta)
        r = await collections.run_collections(s, now=NOW, base_url="https://karmaai.online")
    assert r["reminders"][0]["stage"] == stage
    assert calls and calls[0]["purpose"] == "renewal"
    assert len(calls[0]["params"]) == 4 and calls[0]["params"][3].endswith(f"/invoice/{pay.id}")
    assert r["reminders"][0]["channels"]["whatsapp"] == "sent:template"
    assert not r["whatsapp_template_missing"]


async def test_auto_reminder_fallback_is_not_marked_sent(maker, monkeypatch):
    """No approved template -> fallback path -> recorded as fallback, never sent."""
    monkeypatch.setattr(st, "billing_auto_send", True)
    object.__setattr__(st, "whatsapp_token", "TEST-TOKEN")
    object.__setattr__(st, "whatsapp_phone_number_id", "123")
    try:
        async with maker() as s:
            await wa_templates.seed_defaults(s)  # all templates are draft
            await _project(s, NOW + timedelta(hours=12))
            r = await collections.run_collections(s, now=NOW)
            rows = (await s.execute(select(OutboundMessage).where(OutboundMessage.channel == "whatsapp"))).scalars().all()
    finally:
        object.__setattr__(st, "whatsapp_token", None)
        object.__setattr__(st, "whatsapp_phone_number_id", None)
    wa = r["reminders"][0]["channels"]["whatsapp"]
    assert wa == "fallback:awaiting_manual" and not wa.startswith("sent")
    assert r["whatsapp_template_missing"]
    assert rows and all(m.status not in ("sent", "dispatched") for m in rows)


async def test_owner_send_endpoint_fallback_not_dispatched(maker):
    from src.main import app

    async with maker() as s:
        proj, pay = await _project(s, NOW + timedelta(days=4))
        msg = OutboundMessage(id=uuid4(), channel="whatsapp", phone=proj.phone, text="تذكير",
                              status="draft", message_type="renewal")
        s.add(msg)
        await s.commit()
        mid = msg.id
    app.state.session_factory = maker
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                 cookies={"narjis_owner": make_session_token()}) as c:
        r = await c.post(f"/api/owner/ops/wa/renewal/{mid}")
    assert r.status_code == 200 and r.json()["path"] == "fallback"
    async with maker() as s:
        row = await s.get(OutboundMessage, mid)
    assert row.status == "fallback" and row.status != "dispatched"
