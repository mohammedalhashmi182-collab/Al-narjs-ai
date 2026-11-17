"""A switched-off agent is skipped by every runner, without a crash."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.automation.queue_worker import QueueTask, QueueWorker, TaskStatus
from src.automation.workflow_engine import WorkflowDefinition, WorkflowEngine, WorkflowStep
from src.core.state_manager import StateManager, StepStatus
from src.db.session import Base
from src.services.owner_chat import log_disabled_skip


def _disabled_for(*slugs: str):
    blocked = set(slugs)

    async def check(slug: str | None) -> bool:
        return str(slug or "") in blocked

    return check


def _runtime():
    calls: list[str] = []

    async def execute(provider, agent, **kwargs):
        calls.append(getattr(agent, "slug", ""))
        return SimpleNamespace(
            content="ok",
            structured_output=None,
            tokens_used=1,
            quality={},
            model="stub",
            latency_ms=1,
        )

    return calls, execute


async def test_scheduled_agent_is_skipped_and_recorded(monkeypatch, caplog):
    from src.models import Schedule, WorkflowExecution
    from src.services.schedule_service import execute_schedule

    monkeypatch.setattr("src.services.owner_chat.agent_is_disabled", _disabled_for("ad_writer"))
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            sched = Schedule(
                name="agent tick",
                target_type="agent",
                target_id=uuid4(),
                payload={"agent_slug": "ad_writer"},
            )
            session.add(sched)
            await session.commit()
            schedule_id = sched.id
        with caplog.at_level(logging.INFO, logger="src.services.owner_chat"):
            async with factory() as session:
                out = await execute_schedule(session, schedule_id)
        assert out["status"] == "skipped"
        assert out["reason"] == "disabled"
        assert "disabled agent skipped" in caplog.text
        assert "ad_writer" in caplog.text
        async with factory() as session:
            row = (
                await session.execute(select(WorkflowExecution).where(WorkflowExecution.status == "skipped"))
            ).scalar_one()
        assert row.error == "disabled"
        assert row.workflow_id == "ad_writer"
        assert row.trigger_type == "schedule"
    finally:
        await engine.dispose()


async def test_workflow_step_skips_and_the_next_agent_still_runs(monkeypatch):
    calls, execute = _runtime()
    monkeypatch.setattr("src.services.owner_chat.agent_is_disabled", _disabled_for("ad_writer"))
    monkeypatch.setattr("src.services.agent_runtime.execute", execute)

    class Registry:
        async def get_agent(self, slug):
            return SimpleNamespace(
                slug=slug,
                prompt_templates={"default": SimpleNamespace(template_text="اعمل العمل")},
                default_parameters={},
            )

    engine = WorkflowEngine(Registry(), SimpleNamespace(), StateManager(), None)
    definition = WorkflowDefinition(
        steps=[
            WorkflowStep(id="first", agent_slug="ad_writer"),
            WorkflowStep(id="second", agent_slug="text_improver", depends_on=["first"]),
        ]
    )
    result = await engine.execute(definition, {})
    state = engine.state_manager.get_workflow(result.workflow_id)
    assert state.steps["first"].status == StepStatus.SKIPPED
    assert state.steps["first"].error == "disabled"
    assert state.steps["second"].status == StepStatus.COMPLETED
    assert calls == ["text_improver"]
    assert result.success


async def test_queue_worker_skips_without_calling_the_model(monkeypatch):
    monkeypatch.setattr("src.services.owner_chat.agent_is_disabled", _disabled_for("cv_writer"))

    class Registry:
        async def get_agent(self, slug):
            raise AssertionError("registry should not load a disabled agent")

    worker = QueueWorker(Registry(), SimpleNamespace(), StateManager(), concurrency=1)
    task = QueueTask(agent_slug="cv_writer", prompt_template="default")
    await worker.enqueue(task)
    await worker._queue.get()
    await worker._execute_task(task)
    assert task.status == TaskStatus.SKIPPED
    assert task.error == "disabled"
    assert task.result["reason"] == "disabled"
    assert task in worker._completed_tasks


async def test_agent_handoff_returns_a_skip(monkeypatch):
    from src.core.agent_registry import AgentRegistry
    from src.services import execute_agent

    monkeypatch.setattr("src.services.owner_chat.agent_is_disabled", _disabled_for("marketing_agent"))

    async def boom(*args, **kwargs):
        raise AssertionError("handoff must not call the model")

    monkeypatch.setattr("src.services.agent_runtime.execute", boom)

    async def fake_get(self, slug):
        return SimpleNamespace(slug="marketing_agent", prompt_templates={}, default_parameters={})

    monkeypatch.setattr(AgentRegistry, "get_agent", fake_get)
    result = await execute_agent(None, uuid4(), {"topic": "عرض"})
    assert result["skipped"] is True
    assert result["reason"] == "disabled"
    assert result["slug"] == "marketing_agent"


async def test_trigger_handoff_does_not_crash_when_the_agent_is_disabled(monkeypatch):
    from src.automation.trigger_engine import TriggerEngine

    seen: list[str] = []

    async def fake_execute(session, target_id, payload):
        seen.append("called")
        return {"skipped": True, "reason": "disabled", "slug": "ad_writer"}

    monkeypatch.setattr("src.services.execute_agent", fake_execute)

    class Session:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *args):
            return False

    engine = TriggerEngine.__new__(TriggerEngine)
    engine.session_factory = lambda: Session()
    await engine._execute_target("agent", uuid4(), {"note": "سلّم العمل"})
    assert seen == ["called"]


async def test_router_handoff_does_not_call_the_model(monkeypatch):
    from src.core.architecture.router.dynamic_router import DynamicRouter

    monkeypatch.setattr("src.services.owner_chat.agent_is_disabled", _disabled_for("content_ideas", "customer_service"))

    class Provider:
        async def complete(self, *args, **kwargs):
            raise AssertionError("router must not call the model")

        async def complete_with_fallback(self, *args, **kwargs):
            raise AssertionError("router must not call the model")

    result = await DynamicRouter(model_provider=Provider()).execute("فكرة منشور", agent_slug="content_ideas")
    assert result.error == "disabled"
    assert result.agent_slug
    assert result.content == ""


async def test_cron_evaluation_skips_a_disabled_agent(monkeypatch):
    from src.models import ClientAgent, ClientProject
    from src.services.capabilities.cron_jobs import evaluate_recent

    monkeypatch.setattr("src.services.owner_chat.agent_is_disabled", _disabled_for("social_media"))
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            project = ClientProject(client_name="عميل", phone="0555000011", package="bidaya", status="active")
            session.add(project)
            await session.flush()
            session.add(ClientAgent(project_id=project.id, slug="social_media", status="done", result="مسودة قديمة"))
            await session.commit()
        async with factory() as session:
            report = await evaluate_recent(session)
        assert report["skipped_disabled"] == 1
        assert report["scanned"] == 0
    finally:
        await engine.dispose()


async def test_company_task_runner_skips_a_disabled_owner(monkeypatch):
    from src.models import Task
    from src.services.company_task_runner import run_queued_tasks

    monkeypatch.setattr("src.services.owner_chat.agent_is_disabled", _disabled_for("sales_closer"))
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            session.add(
                Task(
                    key=uuid4().hex[:24],
                    title="Qualify 1 new/ready leads",
                    owner_agent="sales_closer",
                    status="queued",
                    priority=10,
                    evidence={"new_or_ready": 1},
                )
            )
            await session.commit()
        report = await run_queued_tasks(factory)
        assert report["skipped"] == 1
        assert report["completed"] == 0
        assert report["failed"] == 0
        assert report["tasks"][0]["blocker_code"] == "agent_disabled"
        async with factory() as session:
            task = (await session.execute(select(Task))).scalar_one()
        assert task.status == "cancelled"
        assert task.result["blocker_code"] == "agent_disabled"
    finally:
        await engine.dispose()


def test_skip_log_line_names_the_agent_and_the_path(caplog):
    with caplog.at_level(logging.INFO, logger="src.services.owner_chat"):
        log_disabled_skip("orchestrator", "workflow")
    assert "disabled agent skipped slug=orchestrator path=workflow" in caplog.text
