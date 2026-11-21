"""A connected store becomes a CRM lead with an owner follow-up. No live store calls."""

from __future__ import annotations

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.integrations.pipeline import record_connection
from src.integrations.provider import StoreInfo
from src.integrations.service import save_install
from src.models import AcquisitionLead, ClientProject, LeadEvent, Task


async def _maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def test_record_connection_is_idempotent_and_assigns_the_owner(monkeypatch) -> None:
    monkeypatch.setenv("STORE_TOKEN_ENC_KEY", Fernet.generate_key().decode())
    engine, maker = await _maker()
    try:
        async with maker() as session:
            project = ClientProject(client_name="متجر التجربة", phone="0555000091", email="store@example.com", package="numuw", status="active")
            session.add(project)
            await session.commit()
            await session.refresh(project)
            await record_connection(session, project.id, "salla", "تين وزيتون", "847769313")
            await record_connection(session, project.id, "salla", "تين وزيتون", "847769313")
            await session.commit()
        async with maker() as session:
            lead = (await session.execute(select(AcquisitionLead))).scalar_one()
            assert lead.source == "salla"
            assert lead.lead_status == "NEW"
            assert lead.sales_representative == "owner"
            assert lead.segment == "ecommerce"
            assert lead.company_name == "تين وزيتون"
            assert (lead.raw_data or {})["store"]["merchant_id"] == "847769313"
            events = (await session.execute(select(LeadEvent))).scalars().all()
            assert len(events) == 2
            task = (await session.execute(select(Task))).scalar_one()
            assert task.owner_agent == "store_manager"
            assert task.evidence["human_owner"] == "owner"
            assert task.status == "escalated"
    finally:
        await engine.dispose()


async def test_save_install_records_the_pipeline(monkeypatch) -> None:
    monkeypatch.setenv("STORE_TOKEN_ENC_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("STORE_TOKEN_ENC_KEY_ID", "1")
    engine, maker = await _maker()
    try:
        async with maker() as session:
            project = ClientProject(client_name="متجر زد", phone="0555000092", package="numuw", status="active")
            session.add(project)
            await session.commit()
            await session.refresh(project)
            info = StoreInfo(merchant_id="55", store_ref=None, name="متجر الاختبار", platform="zid")
            await save_install(session, project.id, "zid", {"access_token": "test-access", "refresh_token": "test-refresh", "expires": 3600}, info)
        async with maker() as session:
            lead = (await session.execute(select(AcquisitionLead))).scalar_one()
            assert lead.source == "zid"
            assert lead.dedup_key == "store:zid:55"
            assert "test-access" not in str(lead.raw_data)
    finally:
        await engine.dispose()
