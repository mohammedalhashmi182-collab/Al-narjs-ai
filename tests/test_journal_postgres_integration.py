"""Real PostgreSQL lease/race/restart tests on synthetic CI-only records.

Only runs when TEST_POSTGRES_DSN is explicitly set. GitHub Actions provides a
disposable postgres:17 container. Never point this test at Neon or production.
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.db.session import Base
from src.models import ClientProject
from src.models.service_delivery import (
    ServiceArtifact, ServiceJob, ServiceJournalEvent, ServiceOffer, ServiceStepCheckpoint,
)
from src.services.service_fulfillment_journal import (
    InternalServiceJournal, JournalError, LEASE_SECONDS,
)

def _is_disposable_local_pg(dsn: str) -> bool:
    """Reject production URLs even if 127.0.0.1 appears in a query string."""
    try:
        url = make_url(dsn)
    except Exception:
        return False
    return (
        url.drivername == "postgresql+asyncpg"
        and url.host == "127.0.0.1"
        and url.database == "narjis_ci"
        and url.username == "narjis_ci"
        and url.port == 5432
    )


@pytest.fixture
async def pg_fixture(monkeypatch):
    dsn = os.getenv("TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Synthetic PostgreSQL container is not configured")
    if not _is_disposable_local_pg(dsn):
        pytest.skip("Only disposable localhost narjis_ci PostgreSQL is allowed")
    db = create_async_engine(dsn, pool_size=5, max_overflow=15)
    tables = [
        ClientProject.__table__, ServiceOffer.__table__, ServiceJob.__table__,
        ServiceArtifact.__table__, ServiceJournalEvent.__table__,
        ServiceStepCheckpoint.__table__,
    ]
    async with db.begin() as conn:
        await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=tables))
    maker = async_sessionmaker(db, expire_on_commit=False)
    async with maker() as session:
        p = ClientProject(
            client_name="Synthetic PG tester", phone="000000", package="bidaya",
            status="active",
        )
        session.add(p)
        await session.commit()
        project_id = p.id
    monkeypatch.setenv(
        "NARJIS_ARTIFACT_FERNET_KEY",
        os.environ.get("NARJIS_ARTIFACT_FERNET_KEY") or Fernet.generate_key().decode(),
    )
    yield maker, project_id
    await db.dispose()


@pytest.mark.asyncio
async def test_postgres_parallel_claim_has_one_owner_and_no_duplicate_execution(pg_fixture):
    maker, project_id = pg_fixture
    journal = InternalServiceJournal(maker)
    job = await journal.create_preview(
        project_id, request_key="pg-atomic-claim-001",
        brief="Test atomic claim for concurrent executors", formats=["xlsx"],
    )
    claims = await asyncio.gather(*(
        InternalServiceJournal(maker).claim(project_id, job) for _ in range(16)
    ))
    owners = [lease for lease in claims if lease is not None]
    assert len(owners) == 1
    assert owners[0].attempt == 1
    async with maker() as session:
        current = await session.get(ServiceJob, job)
        assert current.status == "running" and current.attempts == 1
        events = (await session.execute(select(ServiceJournalEvent).where(
            ServiceJournalEvent.job_id == job
        ))).scalars().all()
        assert sum(e.event_name == "claimed" for e in events) == 1


@pytest.mark.asyncio
async def test_postgres_restart_keeps_checkpoints_and_fences_stale_writer(pg_fixture):
    maker, project_id = pg_fixture
    journal = InternalServiceJournal(maker)
    job = await journal.create_preview(
        project_id, request_key="pg-restart-fence-001",
        brief="Synthetic report", formats=["pdf"],
    )
    t0 = datetime.now(UTC) - timedelta(seconds=LEASE_SECONDS + 10)
    previous = await journal.claim(project_id, job, now=t0)
    await journal.save_step_checkpoint(
        previous, step_id="analysis", agent_slug="data_analyst",
        output_data={"content": "Verified synthetic analysis"},
        now=t0 + timedelta(seconds=1),
    )
    restarted = InternalServiceJournal(maker)
    new_lease = await restarted.claim(project_id, job)
    assert new_lease is not None and new_lease.token != previous.token
    restored = await restarted.load_step_checkpoints(new_lease)
    assert restored["analysis"]["output_data"]["content"] == "Verified synthetic analysis"
    with pytest.raises(JournalError, match="Active lease"):
        await journal.save_step_checkpoint(
            previous, step_id="plan", agent_slug="project_manager",
            output_data={"content": "Stale write"},
        )
    await restarted.save_step_checkpoint(
        new_lease, step_id="plan", agent_slug="project_manager",
        output_data={"content": "New owner plan"},
    )
    data = await restarted.load_step_checkpoints(new_lease)
    assert set(data) == {"analysis", "plan"}
    async with maker() as session:
        rows = (await session.execute(select(ServiceStepCheckpoint).where(
            ServiceStepCheckpoint.job_id == job
        ))).scalars().all()
        assert len(rows) == 2
        assert all(b"Synthetic" not in c.encrypted_output for c in rows)



@pytest.mark.asyncio
async def test_postgres_encrypted_artifact_roundtrip_in_synthetic_database(pg_fixture):
    """Leave a genuinely encrypted file for the disposable backup/restore check."""
    from src.services.docgen.pipeline import build_docpack
    from src.services.docgen.release_gate import ReleaseApproval, pack_digest
    from src.services.docgen.sample import load_sample_bytes

    maker, project_id = pg_fixture
    brief = "Synthetic quarterly report for backup recovery test"
    journal = InternalServiceJournal(maker)
    job = await journal.create_preview(
        project_id, request_key="pg-encrypted-artifact-001",
        brief=brief, formats=["xlsx"],
    )
    lease = await journal.claim(project_id, job)
    assert lease
    pack = await build_docpack(
        brief=brief, file_bytes=load_sample_bytes(), filename="sample.xlsx",
        agent_key="data_analyst", agent_name_ar="محلل البيانات",
        agent_name_en="Data Analyst", formats=["xlsx"],
        model_provider=None, client_name="Synthetic data only",
    )
    files = await journal.approve(
        lease, pack, ReleaseApproval(pack_digest(pack), "synthetic-independent-review"),
    )
    assert len(files) == 1
    recovered = await journal.read_reviewed_artifact(project_id, job, files[0])
    assert recovered == pack.files[0].content
    async with maker() as session:
        items = (await session.execute(select(ServiceArtifact).where(
            ServiceArtifact.job_id == job
        ))).scalars().all()
        assert len(items) == 1
        assert items[0].encrypted_bytes != recovered
        assert b"synthetic" not in items[0].encrypted_bytes.lower()


def test_postgres_sandbox_connection_gate_rejects_remote_and_misleading_dsn():
    assert _is_disposable_local_pg(
        "postgresql+asyncpg://narjis_ci:local-ci-only@127.0.0.1:5432/narjis_ci"
    )
    assert not _is_disposable_local_pg(
        "postgresql+asyncpg://user:pass@production.example:5432/neondb?host_hint=127.0.0.1"
    )
    assert not _is_disposable_local_pg(
        "postgresql+asyncpg://narjis_ci:pass@127.0.0.1:5432/production"
    )
    assert not _is_disposable_local_pg(
        "postgresql+asyncpg://narjis_ci:pass@localhost:5432/narjis_ci"
    )
    assert not _is_disposable_local_pg("sqlite://")
