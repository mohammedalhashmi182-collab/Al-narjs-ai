"""Synthetic fail-closed tests for encrypted workflow checkpoint recovery.

No network, payment, production database, or customer data is used.
"""
from __future__ import annotations

from cryptography.fernet import Fernet
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import ClientProject
from src.models.service_delivery import ServiceStepCheckpoint
from src.services.service_fulfillment_journal import InternalServiceJournal, JournalError


@pytest.fixture
async def checkpoint_db(monkeypatch):
    monkeypatch.setenv("NARJIS_ARTIFACT_FERNET_KEY", Fernet.generate_key().decode())
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        project = ClientProject(
            client_name="Synthetic", phone="00001", package="bidaya", status="active"
        )
        session.add(project)
        await session.commit()
        project_id = project.id
    try:
        yield factory, project_id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_tampered_ciphertext_blocks_checkpoint_restore(checkpoint_db):
    factory, project_id = checkpoint_db
    journal = InternalServiceJournal(factory)
    job = await journal.create_preview(
        project_id, request_key="tamper-checkpoint-001",
        brief="Synthetic checkpoint integrity test", formats=["xlsx"],
    )
    lease = await journal.claim(project_id, job)
    assert lease is not None
    await journal.save_step_checkpoint(
        lease, step_id="analysis", agent_slug="data_analyst",
        output_data={"content": "Synthetic output", "tokens_used": 1},
    )
    async with factory() as session:
        checkpoint = (await session.execute(
            select(ServiceStepCheckpoint).where(ServiceStepCheckpoint.job_id == job)
        )).scalar_one()
        checkpoint.encrypted_output = b"invalid-authenticated-token"
        await session.commit()

    with pytest.raises(JournalError, match="Cannot authenticate saved workflow checkpoint"):
        await InternalServiceJournal(factory).load_step_checkpoints(lease)


@pytest.mark.asyncio
async def test_tampered_checksum_blocks_checkpoint_restore(checkpoint_db):
    factory, project_id = checkpoint_db
    journal = InternalServiceJournal(factory)
    job = await journal.create_preview(
        project_id, request_key="tamper-checksum-002",
        brief="Synthetic checkpoint checksum test", formats=["xlsx"],
    )
    lease = await journal.claim(project_id, job)
    assert lease is not None
    await journal.save_step_checkpoint(
        lease, step_id="analysis", agent_slug="data_analyst",
        output_data={"content": "Synthetic output", "tokens_used": 1},
    )
    async with factory() as session:
        checkpoint = (await session.execute(
            select(ServiceStepCheckpoint).where(ServiceStepCheckpoint.job_id == job)
        )).scalar_one()
        checkpoint.content_sha256 = "0" * 64
        await session.commit()

    with pytest.raises(JournalError, match="Cannot authenticate saved workflow checkpoint"):
        await InternalServiceJournal(factory).load_step_checkpoints(lease)
