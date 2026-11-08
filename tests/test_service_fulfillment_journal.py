"""Durable internal journal proof: no payment, internet, email or real customers."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import ClientProject
from src.models.service_delivery import (
    ServiceArtifact, ServiceJob, ServiceJournalEvent, ServiceOffer,
)
from src.services.docgen.pipeline import build_docpack
from src.services.docgen.release_gate import ReleaseApproval, pack_digest
from src.services.docgen.sample import load_sample_bytes
from src.services.service_fulfillment_journal import (
    InternalServiceJournal, JournalError, LEASE_SECONDS,
)


@pytest.fixture
async def journal_db(monkeypatch):
    monkeypatch.setenv("NARJIS_ARTIFACT_FERNET_KEY", Fernet.generate_key().decode())
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        a = ClientProject(client_name="Test one", phone="00001", package="bidaya", status="active")
        b = ClientProject(client_name="Test two", phone="00002", package="bidaya", status="active")
        session.add_all([a, b])
        await session.commit()
    yield maker, a.id, b.id
    await engine.dispose()


async def _pack(brief: str):
    return await build_docpack(
        brief=brief, file_bytes=load_sample_bytes(), filename="synthetic.xlsx",
        agent_key="data_analyst", agent_name_ar="محلل البيانات",
        agent_name_en="Data Analyst", formats=["xlsx"],
        model_provider=None, client_name="Synthetic Client",
    )


@pytest.mark.asyncio
async def test_exact_request_idempotency_and_encrypted_brief(journal_db):
    maker, a, b = journal_db
    j = InternalServiceJournal(maker)
    key = "idempotent-job-001"
    one = await j.create_preview(a, request_key=key, brief="Review this sample", formats=["xlsx"])
    same = await j.create_preview(a, request_key=key, brief="Review this sample", formats=["xlsx"])
    assert one == same
    other = await j.create_preview(b, request_key=key, brief="Review this sample", formats=["xlsx"])
    assert other != one
    with pytest.raises(JournalError, match="reused"):
        await j.create_preview(a, request_key=key, brief="Different request", formats=["xlsx"])
    async with maker() as session:
        offers = (await session.execute(select(ServiceOffer))).scalars().all()
        jobs = (await session.execute(select(ServiceJob))).scalars().all()
        events = (await session.execute(select(ServiceJournalEvent))).scalars().all()
        assert len(offers) == len(jobs) == len(events) == 2
        assert all(b"Review this sample" not in o.brief_encrypted for o in offers)
        assert all(o.accepted_at is None for o in offers)
        assert all(o.scope == {"mode": "internal_preview"} for o in offers)


@pytest.mark.asyncio
async def test_reclaim_expired_lease_prevents_stale_worker_from_approving(journal_db):
    maker, a, _ = journal_db
    brief = "Review the synthetic spreadsheet"
    j = InternalServiceJournal(maker)
    job = await j.create_preview(a, request_key="resumable-preview-001", brief=brief, formats=["xlsx"])
    t0 = datetime(2026, 11, 8, 1, 0, tzinfo=UTC)
    first = await j.claim(a, job, now=t0)
    assert first is not None
    assert await j.claim(a, job, now=t0 + timedelta(seconds=2)) is None
    assert await j.brief_for_lease(first, now=t0 + timedelta(seconds=1)) == brief

    # Mimic a process restart: all state must be in SQLite, not a Python dict.
    restarted = InternalServiceJournal(maker)
    second = await restarted.claim(a, job, now=t0 + timedelta(seconds=LEASE_SECONDS + 1))
    assert second is not None and second.attempt == 2
    assert second.token != first.token
    with pytest.raises(JournalError, match="active job lease"):
        await restarted.brief_for_lease(first, now=t0 + timedelta(seconds=LEASE_SECONDS + 1))
    assert await restarted.heartbeat(second, now=t0 + timedelta(seconds=LEASE_SECONDS + 2))
    assert not await restarted.heartbeat(first, now=t0 + timedelta(seconds=LEASE_SECONDS + 2))
    pack = await _pack(brief)
    approval = ReleaseApproval(pack_digest(pack), "synthetic-independent-review")
    with pytest.raises(JournalError, match="Lease lost"):
        await restarted.approve(first, pack, approval, now=t0 + timedelta(seconds=LEASE_SECONDS + 3))
    filenames = await restarted.approve(
        second, pack, approval, now=t0 + timedelta(seconds=LEASE_SECONDS + 3)
    )
    assert len(filenames) == 1
    saved = await restarted.read_reviewed_artifact(a, job, filenames[0])
    assert saved == pack.files[0].content
    workbook = load_workbook(BytesIO(saved))
    assert workbook.sheetnames
    async with maker() as session:
        records = (await session.execute(select(ServiceArtifact))).scalars().all()
        assert len(records) == 1 and records[0].encrypted_bytes != saved
        assert (await session.get(ServiceJob, job)).status == "reviewed"


@pytest.mark.asyncio
async def test_wrong_project_and_changed_approval_never_release(journal_db):
    maker, a, b = journal_db
    journal = InternalServiceJournal(maker)
    brief = "Audit the numbers from sample"
    job = await journal.create_preview(
        a, request_key="cross-tenant-preview", brief=brief, formats=["xlsx"],
    )
    lease = await journal.claim(a, job)
    assert lease
    assert await journal.claim(b, job) is None
    pack = await _pack(brief)
    forged = ReleaseApproval(digest="x" * 64, reviewer="fake")
    with pytest.raises(Exception, match="independently reviewed approval"):
        await journal.approve(lease, pack, forged)
    approved = ReleaseApproval(digest=pack_digest(pack), reviewer="fixture")
    files = await journal.approve(lease, pack, approved)
    assert await journal.read_reviewed_artifact(b, job, files[0]) is None
    assert await journal.read_reviewed_artifact(a, job, files[0]) is not None
    assert await journal.claim(a, job) is None
    with pytest.raises(JournalError, match="Lease lost"):
        await journal.approve(lease, pack, approved)


@pytest.mark.asyncio
async def test_retries_are_bounded_sanitized_and_no_duplicate_effects(journal_db):
    maker, a, _ = journal_db
    journal = InternalServiceJournal(maker)
    job = await journal.create_preview(
        a, request_key="limited-retries-001", brief="Retry sample", formats=["pdf"],
    )
    t0 = datetime(2026, 11, 8, 2, 0, tzinfo=UTC)
    for attempt in (1, 2):
        lease = await journal.claim(a, job, now=t0)
        assert lease and lease.attempt == attempt
        status = await journal.fail(lease, code="timeout", now=t0)
        assert status == "queued"
        with pytest.raises(JournalError, match="Lease lost"):
            await journal.fail(lease, code="timeout", now=t0)
        assert await journal.claim(a, job, now=t0) is None
        t0 += timedelta(seconds=20 * (2 ** (attempt - 1)) + 1)
    lease = await journal.claim(a, job, now=t0)
    assert lease and lease.attempt == 3
    assert await journal.fail(lease, code="timeout", now=t0) == "failed_final"
    assert await journal.claim(a, job, now=t0 + timedelta(days=3)) is None
    async with maker() as session:
        row = await session.get(ServiceJob, job)
        assert row.last_error == "timeout" and row.attempts == 3
        events = (await session.execute(select(ServiceJournalEvent).where(
            ServiceJournalEvent.job_id == job
        ))).scalars().all()
        assert len(events) == 7  # queued + 3 claims + 3 failure events
        assert all("Traceback" not in str(item.evidence) for item in events)


@pytest.mark.asyncio
async def test_no_encryption_key_means_no_work_started(journal_db, monkeypatch):
    maker, a, _ = journal_db
    monkeypatch.delenv("NARJIS_ARTIFACT_FERNET_KEY")
    journal = InternalServiceJournal(maker)
    with pytest.raises(JournalError, match="not configured"):
        await journal.create_preview(
            a, request_key="key-missing-001", brief="Sensitive", formats=["pdf"]
        )
    async with maker() as session:
        assert (await session.execute(select(func.count()).select_from(ServiceJob))).scalar_one() == 0


@pytest.mark.asyncio
async def test_review_failure_does_not_store_customer_artifacts(journal_db):
    maker, a, _ = journal_db
    journal = InternalServiceJournal(maker)
    job = await journal.create_preview(
        a, request_key="review-refused-001", brief="Audit sample", formats=["xlsx"]
    )
    lease = await journal.claim(a, job)
    assert lease
    assert await journal.fail(lease, code="qa_rejected") == "failed_final"
    assert await journal.project_status(a) == [{
        "id": str(job), "status": "failed_final", "attempts": 1,
        "created_at": (await _job_time(maker, job)),
    }]
    async with maker() as session:
        assert (await session.execute(select(func.count()).select_from(ServiceArtifact))).scalar_one() == 0


async def _job_time(maker, id):
    async with maker() as session:
        job = await session.get(ServiceJob, id)
        return job.created_at.isoformat()
