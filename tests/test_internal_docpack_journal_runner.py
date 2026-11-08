"""Prove the durable journal actually drives the internal multi-agent DocPack."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.automation.workflow_engine import WorkflowEngine
from src.core.state_manager import StateManager
from src.db.session import Base
from src.models import ClientProject
from src.services.docgen.journal_runner import run_internal_docpack
from src.services.service_fulfillment_journal import InternalServiceJournal


@pytest.fixture
async def live_fixture(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        project = ClientProject(
            client_name="Demo", phone="00001", package="bidaya", status="active",
        )
        session.add(project)
        await session.commit()
        project_id = project.id
    monkeypatch.setenv("NARJIS_ARTIFACT_FERNET_KEY", Fernet.generate_key().decode())
    from src.services import agent_runtime

    registry = AsyncMock()
    registry.get_agent.side_effect = lambda slug: SimpleNamespace(
        slug=slug, category="general", default_parameters={},
        prompt_templates={"default": SimpleNamespace(template_text="Do this task.")},
    )

    async def fake_execute(provider, selected_agent, **kwargs):
        content = (
            "Verdict: PASS\nEvidence reviewed."
            if selected_agent.slug == "quality_gate"
            else "Completed internal synthetic task"
        )
        return SimpleNamespace(
            content=content, structured_output=None, tokens_used=1,
            model="fixture", quality={"passed": True},
        )
    monkeypatch.setattr(agent_runtime, "execute", fake_execute)
    flow = WorkflowEngine(registry, AsyncMock(), StateManager(), None, max_concurrent_steps=2)

    class Reviewer:
        async def complete_with_fallback(self, provider, request):
            return SimpleNamespace(content='{"verdict":"PASS","issues":[]}')
    yield maker, project_id, flow, Reviewer()
    await engine.dispose()


@pytest.mark.asyncio
async def test_brief_to_coordinated_agents_to_qa_to_encrypted_storage(live_fixture):
    maker, project_id, flow, reviewer = live_fixture
    journal = InternalServiceJournal(maker)
    job_id = await journal.create_preview(
        project_id, request_key="team-delivery-synthetic-1",
        brief="حلّل مبيعات 100 و150 وحدة بشكل مهني", formats=["xlsx"],
    )
    result = await run_internal_docpack(
        journal, flow, reviewer, project_id, job_id,
    )
    assert result["status"] == "reviewed", result
    assert result["files_stored"] == 1
    statuses = await InternalServiceJournal(maker).project_status(project_id)
    assert statuses[0]["status"] == "reviewed"
    assert await run_internal_docpack(
        journal, flow, reviewer, project_id, job_id,
    ) == {"job_id": str(job_id), "status": "not_claimed"}
    from src.models.service_delivery import ServiceArtifact
    from sqlalchemy import select
    async with maker() as session:
        file = (await session.execute(
            select(ServiceArtifact).where(ServiceArtifact.job_id == job_id)
        )).scalar_one()
    data = await journal.read_reviewed_artifact(project_id, job_id, file.filename)
    assert load_workbook(BytesIO(data)).sheetnames


@pytest.mark.asyncio
async def test_no_independent_reviewer_never_marks_customer_work_delivered(live_fixture):
    maker, project_id, flow, _ = live_fixture
    journal = InternalServiceJournal(maker)
    job_id = await journal.create_preview(
        project_id, request_key="team-review-denied-1",
        brief="تقرير داخلي من رقم 100", formats=["xlsx"],
    )
    result = await run_internal_docpack(journal, flow, None, project_id, job_id)
    assert result["status"] == "review_required", result
    statuses = await journal.project_status(project_id)
    assert statuses[0]["status"] == "failed_final"
    assert await journal.read_reviewed_artifact(
        project_id, job_id, "nonexistent.xlsx"
    ) is None



@pytest.mark.asyncio
async def test_process_restart_skips_completed_encrypted_specialists(live_fixture, monkeypatch):
    """Reclaim expired lease and execute QA only; never repeat saved specialists."""
    from datetime import UTC, datetime, timedelta
    from sqlalchemy import select

    from src.models.service_delivery import ServiceStepCheckpoint
    from src.services import agent_runtime
    from src.services.service_fulfillment_journal import JournalError, LEASE_SECONDS

    maker, project_id, flow, reviewer = live_fixture
    journal = InternalServiceJournal(maker)
    brief = "Prepare a clean synthetic quarterly report"
    job = await journal.create_preview(
        project_id, request_key="restart-step-checkpoints-001",
        brief=brief, formats=["xlsx"],
    )
    before_crash = datetime.now(UTC) - timedelta(seconds=LEASE_SECONDS + 10)
    old_lease = await journal.claim(project_id, job, now=before_crash)
    assert old_lease is not None
    for step, role, content in (
        ("analysis", "data_analyst", "Analysis checkpoint"),
        ("plan", "project_manager", "Plan checkpoint"),
    ):
        await journal.save_step_checkpoint(
            old_lease, step_id=step, agent_slug=role,
            output_data={"content": content, "tokens_used": 2, "quality": {"passed": True}},
            now=before_crash + timedelta(seconds=1),
        )
    with pytest.raises(JournalError, match="Active lease"):
        await journal.save_step_checkpoint(
            old_lease, step_id="extra", agent_slug="content_writer",
            output_data={"content": "Not allowed"},
        )
    async with maker() as session:
        rows = (await session.execute(select(ServiceStepCheckpoint).where(
            ServiceStepCheckpoint.job_id == job
        ))).scalars().all()
        assert len(rows) == 2
        assert all(b"checkpoint" not in row.encrypted_output for row in rows)

    invoked = []

    async def fake_execute(provider, selected_agent, **kwargs):
        invoked.append(selected_agent.slug)
        assert selected_agent.slug == "quality_gate"
        assert "Analysis checkpoint" in kwargs["tool_context"]
        assert "Plan checkpoint" in kwargs["tool_context"]
        return SimpleNamespace(
            content="Verdict: PASS\nReview is complete", structured_output=None,
            tokens_used=1, model="fixture", quality={"passed": True}
        )

    monkeypatch.setattr(agent_runtime, "execute", fake_execute)
    restarted = InternalServiceJournal(maker)
    result = await run_internal_docpack(
        restarted, flow, reviewer, project_id, job,
    )
    assert result["status"] == "reviewed", result
    assert invoked == ["quality_gate"], "Restored specialists must not be executed twice"
    from src.models.service_delivery import ServiceArtifact
    async with maker() as session:
        artifacts = (await session.execute(select(ServiceArtifact).where(
            ServiceArtifact.job_id == job
        ))).scalars().all()
        assert len(artifacts) == 1
    downloaded = await restarted.read_reviewed_artifact(project_id, job, artifacts[0].filename)
    assert load_workbook(BytesIO(downloaded)).sheetnames
