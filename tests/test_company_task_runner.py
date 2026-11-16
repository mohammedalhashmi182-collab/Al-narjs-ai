"""Queued company tasks actually finish, and acknowledged email is recorded.

The CEO brain used to insert ``company_tasks`` and leave them ``queued``.
These tests pin the drain: no sends, no lead-status writes, a visible blocker
when there is no safe handler, and a draft cap for inbound enquiries only.
"""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.automation.ceo_engine import CompanyBrain
from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.services.company_task_runner import run_queued_tasks
from src.services.governance import PolicyService


async def _engine():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def maker():
    engine, factory = await _engine()
    yield factory
    await engine.dispose()


def _lead(**kwargs):
    from src.models import AcquisitionLead

    data = {
        "company_name": "منشأة",
        "lead_status": "NEW",
        "outreach_status": "NOT_STARTED",
        "priority": "HIGH",
        "priority_score": 80,
        "source": "excel_import",
        "opt_out": False,
    }
    data.update(kwargs)
    return AcquisitionLead(**data)


def _task(**kwargs):
    from src.models import Task

    data = {
        "key": uuid4().hex[:24],
        "title": "Qualify 3 new/ready leads",
        "owner_agent": "sales_closer",
        "status": "queued",
        "priority": 180,
        "evidence": {"new_or_ready": 3},
    }
    data.update(kwargs)
    return Task(**data)


async def test_qualify_does_not_touch_cold_leads_or_send(maker, monkeypatch) -> None:
    from src.models import AcquisitionLead, Campaign, Task
    from src.services import email_service

    def _boom(*_a, **_k):
        raise AssertionError("qualify must not send email")

    monkeypatch.setattr(email_service, "send_email", _boom)
    monkeypatch.setattr(email_service, "send_followup", _boom)

    async with maker() as session:
        cold = _lead(company_name="مستورد", email="cold@example.com", phone="+966500000001")
        opted = _lead(
            company_name="وارد ملغى",
            email="in@example.com",
            source="website",
            opt_out=True,
            priority_score=99,
        )
        session.add_all([cold, opted, _task()])
        await session.commit()
        cold_id, opted_id = cold.id, opted.id

    report = await run_queued_tasks(maker, governance=PolicyService(maker))
    assert report["claimed"] == 1
    assert report["completed"] == 1
    assert report["tasks"][0]["blocker_code"] == "no_consented_outreach"

    async with maker() as session:
        task = (await session.execute(select(Task))).scalar_one()
        assert task.status == "completed"
        assert task.result["sent"] == 0
        assert task.result["lead_status_changed"] == 0
        assert task.result["drafts_prepared"] == 0
        assert task.result["counts"]["cold"] == 1
        assert task.result["counts"]["opt_out"] == 1
        dumped = str(task.result)
        assert "cold@example.com" not in dumped
        assert "500000001" not in dumped
        assert (await session.execute(select(func.count()).select_from(Campaign))).scalar_one() == 0
        for lead_id in (cold_id, opted_id):
            lead = await session.get(AcquisitionLead, lead_id)
            assert lead.lead_status == "NEW"
            assert lead.outreach_status == "NOT_STARTED"
            assert lead.last_contacted_at is None


async def test_qualify_drafts_at_most_five_inbound_and_is_idempotent(maker) -> None:
    from src.models import AcquisitionLead, CampaignLead, Task

    async with maker() as session:
        for i in range(6):
            session.add(_lead(
                company_name=f"وارد {i}",
                email=f"in{i}@example.com",
                source="website",
                priority_score=50 + i,
            ))
        session.add(_lead(
            company_name="استشارة",
            email="consult@example.com",
            source="consult_assistant",
            priority_score=10,
        ))
        session.add(_task(title="Qualify 7 new/ready leads"))
        await session.commit()

    first = await run_queued_tasks(maker, governance=PolicyService(maker))
    second = await run_queued_tasks(maker, governance=PolicyService(maker))
    assert first["completed"] == 1
    assert second["claimed"] == 0

    async with maker() as session:
        task = (await session.execute(select(Task))).scalar_one()
        assert task.result["drafts_prepared"] == 5
        assert task.result["counts"]["eligible_inbound"] == 7
        drafts = (await session.execute(select(CampaignLead))).scalars().all()
        assert len(drafts) == 5
        assert {row.status for row in drafts} == {"DRAFT"}
        leads = (await session.execute(select(AcquisitionLead))).scalars().all()
        assert {lead.lead_status for lead in leads} == {"NEW"}
        assert {lead.outreach_status for lead in leads} == {"NOT_STARTED"}
        bodies = " ".join(row.message_text or "" for row in drafts)
        assert "example.com" not in str(task.result)
        assert bodies  # the draft lives on the campaign row, not in the task report


async def test_unknown_task_is_escalated_with_a_blocker(maker) -> None:
    from src.models import Task

    async with maker() as session:
        session.add(_task(title="Contact the next cold wave", key="cold-wave"))
        await session.commit()

    report = await run_queued_tasks(maker, governance=PolicyService(maker))
    assert report["escalated"] == 1
    assert report["tasks"][0]["blocker_code"] == "no_executor"

    async with maker() as session:
        task = (await session.execute(select(Task))).scalar_one()
        assert task.status == "escalated"
        assert task.result["sent"] == 0
        assert "لم يُرسَل" in (task.learning or "")


async def test_policy_denial_does_not_draft(maker) -> None:
    from src.models import Campaign, Task

    gov = PolicyService(maker)
    await gov.upsert_policy(
        "sales_closer",
        autonomy_level=0,
        allowed_actions=["read"],
        denied_actions=["internal"],
        requires_approval=["internal"],
    )
    async with maker() as session:
        session.add(_lead(email="in@example.com", source="website"))
        session.add(_task())
        await session.commit()

    report = await run_queued_tasks(maker, governance=gov)
    assert report["escalated"] == 1
    assert report["tasks"][0]["blocker_code"] == "policy_denied"
    async with maker() as session:
        task = (await session.execute(select(Task))).scalar_one()
        assert task.status == "escalated"
        assert (await session.execute(select(func.count()).select_from(Campaign))).scalar_one() == 0


async def test_ceo_loop_drains_the_qualify_task(maker) -> None:
    from src.models import AcquisitionLead, Task

    async with maker() as session:
        session.add(_lead(company_name="عميل جديد", email="lead@example.com"))
        await session.commit()

    brain = CompanyBrain(maker)
    result = await brain.run_once()
    assert result["task_runs"]["completed"] >= 1

    async with maker() as session:
        task = (await session.execute(select(Task))).scalar_one()
        assert task.status == "completed"
        lead = (await session.execute(select(AcquisitionLead))).scalar_one()
        assert lead.lead_status == "NEW"
        assert lead.outreach_status == "NOT_STARTED"


async def test_create_task_route_no_longer_raises_and_run_is_owner_gated(maker) -> None:
    from src.main import app

    app.state.session_factory = maker
    app.state.company_brain = CompanyBrain(maker)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as anon:
        denied = await anon.post("/api/tasks/run")
        assert denied.status_code in (302, 303, 401, 403)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"narjis_owner": make_session_token()},
    ) as client:
        created = await client.post("/api/tasks", json={
            "title": "Qualify 1 new/ready leads",
            "owner_agent": "sales_closer",
        })
        assert created.status_code == 200
        assert created.json()["status"] == "queued"
        page = await client.get("/company")
        assert page.status_code == 200
        assert "runQueuedTasks" in page.text
        assert "تنفيذ المهام المنتظرة" in page.text
        ran = await client.post("/api/tasks/run")
        assert ran.status_code == 200
        body = ran.json()
        assert body["claimed"] == 1
        assert body["completed"] == 1
    app.state.company_brain = None


async def test_acknowledged_followup_stamps_contact_without_status_change(maker, monkeypatch) -> None:
    from src.models import AcquisitionLead, LeadEvent, Schedule
    from src.services import email_service
    from src.services.schedule_service import execute_schedule

    async def _sent(*_a, **_k):
        return True

    monkeypatch.setattr(email_service, "send_followup", _sent)
    async with maker() as session:
        lead = _lead(email="buyer@example.com", source="website")
        session.add(lead)
        await session.flush()
        sched = Schedule(
            name="Lead follow-up test",
            target_type="lead_email",
            target_id=lead.id,
            payload={"step": 1, "email": "buyer@example.com", "name": "عميل", "lead_id": str(lead.id)},
            run_once_at=None,
            timezone="Asia/Riyadh",
        )
        session.add(sched)
        await session.commit()
        schedule_id = sched.id
        lead_id = lead.id

    async with maker() as session:
        out = await execute_schedule(session, schedule_id)
    assert out["status"] == "sent"
    assert out["contact_recorded"] is True
    assert "buyer@example.com" not in str(out)

    async with maker() as session:
        lead = await session.get(AcquisitionLead, lead_id)
        sched = await session.get(Schedule, schedule_id)
        event = (await session.execute(select(LeadEvent))).scalar_one()
        assert lead.lead_status == "NEW"
        assert lead.outreach_status == "NOT_STARTED"
        assert lead.last_contacted_at is not None
        assert event.event_type == "email_acknowledged"
        assert event.status_before == event.status_after == "NEW"
        assert sched.run_count == 1
        assert sched.last_run_at is not None


async def test_unacknowledged_followup_does_not_stamp_contact(maker, monkeypatch) -> None:
    from src.models import AcquisitionLead, Schedule
    from src.services import email_service
    from src.services.schedule_service import execute_schedule

    async def _failed(*_a, **_k):
        return False

    monkeypatch.setattr(email_service, "send_followup", _failed)
    async with maker() as session:
        lead = _lead(email="buyer@example.com", source="website")
        session.add(lead)
        await session.flush()
        sched = Schedule(
            name="Lead follow-up miss",
            target_type="lead_email",
            target_id=lead.id,
            payload={"step": 2, "email": "buyer@example.com", "name": "عميل", "lead_id": str(lead.id)},
            timezone="Asia/Riyadh",
        )
        session.add(sched)
        await session.commit()
        schedule_id, lead_id = sched.id, lead.id

    async with maker() as session:
        out = await execute_schedule(session, schedule_id)
    assert out["status"] == "failed"
    assert out["contact_recorded"] is False
    async with maker() as session:
        lead = await session.get(AcquisitionLead, lead_id)
        assert lead.last_contacted_at is None
        assert lead.lead_status == "NEW"


async def test_social_publish_requires_approval_and_does_not_call_the_network(maker, monkeypatch) -> None:
    from src.models.automation import SocialPostDraft
    from src.services import social_publisher

    calls = []

    async def _fake_linkedin(text, link=None):
        calls.append(("linkedin", text, link))
        return {"success": True, "url": "https://www.linkedin.com/feed/update/1", "error": ""}

    async def _fake_x(text):
        calls.append(("x", text))
        return {"success": False, "url": "", "error": "missing credentials"}

    monkeypatch.setattr(social_publisher, "publish_to_linkedin", _fake_linkedin)
    monkeypatch.setattr(social_publisher, "publish_to_twitter", _fake_x)

    async with maker() as session:
        linkedin = SocialPostDraft(platform="linkedin", text="منشور معتمد", status="draft")
        instagram = SocialPostDraft(platform="instagram", text="انسخه يدوياً", status="draft")
        session.add_all([linkedin, instagram])
        await session.commit()
        linkedin_id, instagram_id = linkedin.id, instagram.id

    from src.main import app

    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"narjis_owner": make_session_token()},
    ) as client:
        early = await client.post(f"/api/owner/automation/social/{linkedin_id}/publish")
        assert early.status_code == 200
        assert early.json()["published"] is False
        assert early.json()["blocker_code"] == "approval_required"
        assert calls == []
        approved = await client.post(f"/api/owner/automation/social/{linkedin_id}/approve")
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert calls == []
        published = await client.post(f"/api/owner/automation/social/{linkedin_id}/publish")
        assert published.status_code == 200
        assert published.json()["published"] is True
        assert published.json()["status"] == "published"
        await client.post(f"/api/owner/automation/social/{instagram_id}/approve")
        blocked = await client.post(f"/api/owner/automation/social/{instagram_id}/publish")
        assert blocked.json()["published"] is False
        assert blocked.json()["blocker_code"] == "no_publisher"
        page = await client.get("/owner/automation")
        assert "نشر الآن" in page.text
        assert "الاعتماد لا ينشر" in page.text
    assert len(calls) == 1
    assert calls[0][0] == "linkedin"


def test_whatsapp_disabled_reason_is_readable_arabic() -> None:
    from src.services.whatsapp_sender import DISABLED_REASON

    assert "Ù" not in DISABLED_REASON
    assert "غير" in DISABLED_REASON
    assert "WHATSAPP_TOKEN" in DISABLED_REASON


async def test_queue_worker_uses_configured_retry_limit() -> None:
    from src.automation.queue_worker import QueueWorker
    from src.config.settings import settings

    previous = settings.queue_max_retries
    object.__setattr__(settings, "queue_max_retries", 7)
    try:
        worker = QueueWorker(None, None, None)
        await worker.enqueue_agent("sales_closer", {"locale": "ar"})
        _priority, _seq, task = worker._queue.get_nowait()
        assert task.max_retries == 7
        await worker.enqueue_agent("sales_closer", {}, max_retries=1)
        _priority, _seq, explicit = worker._queue.get_nowait()
        assert explicit.max_retries == 1
    finally:
        object.__setattr__(settings, "queue_max_retries", previous)
