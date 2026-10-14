"""DPA: customer content of ended subscriptions is deleted 30 days after the end,
scoped to that project, dry-run by default, audited. Tests only (in-memory DB)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import AuditLog, ClientProject, Payment
from src.models.agent_tools import KnowledgeDoc
from src.models.automation import ReplyDraft
from src.models.company import InboundMessage
from src.models.tenant import TenantContact
from src.services import data_retention, schedule_service

NOW = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _project(s, status, end):
    p = ClientProject(client_name="c", phone="0555", package="radd", status=status, current_period_end=end)
    s.add(p)
    await s.flush()
    s.add_all([
        InboundMessage(project_id=p.id, sender_number="9665", provider_message_id=str(uuid4()), text="hi"),
        ReplyDraft(channel="whatsapp", recipient="9665", project_id=p.id, draft_text="x"),
        KnowledgeDoc(project_id=p.id, title="t", content="c"),
        TenantContact(project_id=p.id, contact="9665"),
        Payment(amount=59900, package="radd", project_id=p.id, status="paid"),
    ])
    await s.commit()
    return p


async def _count(s, model, pid):
    return (await s.execute(select(func.count()).select_from(model).where(model.project_id == pid))).scalar()


async def _seed(s):
    old = await _project(s, "expired", NOW - timedelta(days=31))
    recent = await _project(s, "expired", NOW - timedelta(days=10))
    active = await _project(s, "active", NOW - timedelta(days=60))
    s.add(KnowledgeDoc(project_id=None, title="own", content="owner kb"))
    await s.commit()
    return old, recent, active


async def test_dry_run_is_default_and_writes_nothing(maker):
    async with maker() as s:
        old, _, _ = await _seed(s)
        r = await data_retention.purge_ended_projects(s, now=NOW)
        assert r["dry_run"] and r["count"] == 1 and r["projects"][0]["project_id"] == str(old.id)
        assert r["projects"][0]["counts"]["inbound_messages"] == 1
        assert await _count(s, InboundMessage, old.id) == 1
        assert (await s.execute(select(func.count()).select_from(AuditLog))).scalar() == 0


async def test_live_purge_is_scoped_keeps_invoices_and_is_audited(maker):
    async with maker() as s:
        old, recent, active = await _seed(s)
        r = await data_retention.purge_ended_projects(s, now=NOW, dry_run=False)
        assert r["count"] == 1
        for m in (InboundMessage, ReplyDraft, KnowledgeDoc, TenantContact):
            assert await _count(s, m, old.id) == 0
            assert await _count(s, m, recent.id) == 1 and await _count(s, m, active.id) == 1
        assert await _count(s, Payment, old.id) == 1  # ZATCA records kept
        assert (await s.execute(select(func.count()).select_from(KnowledgeDoc)
                                .where(KnowledgeDoc.project_id.is_(None)))).scalar() == 1
        audit = (await s.execute(select(AuditLog))).scalars().all()
        assert len(audit) == 1 and audit[0].action == "dpa_retention_purge" and audit[0].resource_id == old.id


async def test_scheduled_job_is_dry_run_unless_env(maker, monkeypatch):
    from src.models import Schedule

    monkeypatch.delenv(data_retention.LIVE_ENV, raising=False)
    async with maker() as s:
        old, _, _ = await _seed(s)
        sched = Schedule(name=data_retention.SCHEDULE_NAME, target_type="dpa_retention", target_id=uuid4())
        s.add(sched)
        await s.commit()
        res = await schedule_service.execute_schedule(s, sched.id)
        assert res["status"] == "ok" and res["dry_run"] is True and res["projects"] >= 1
        assert await _count(s, InboundMessage, old.id) == 1
