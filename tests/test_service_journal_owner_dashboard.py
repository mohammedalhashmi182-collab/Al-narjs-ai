"""Owner console shows safe job status, never customer inputs or anonymous visitor identity."""
import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.models import ClientProject
from src.services.service_fulfillment_journal import InternalServiceJournal


@pytest.fixture
async def owner_app(monkeypatch):
    from src.main import app

    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        p = ClientProject(
            client_name="Synthetic Private Customer",
            phone="00001", package="bidaya", status="active",
        )
        session.add(p)
        await session.commit()
        project_id = p.id
    monkeypatch.setenv("NARJIS_ARTIFACT_FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(app.state, "session_factory", maker, raising=False)
    yield app, maker, project_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_owner_dashboard_internal_work_excludes_briefs(owner_app):
    app, maker, project_id = owner_app
    journal = InternalServiceJournal(maker)
    job_id = await journal.create_preview(
        project_id,
        request_key="owner-private-preview-001",
        brief="Never show this secret synthetic business plan",
        formats=["xlsx"],
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as guest:
        unauthorized = await guest.get("/api/company/service-jobs")
        assert unauthorized.status_code in (401, 403)
        owner_page = await guest.get("/company", follow_redirects=False)
        assert owner_page.status_code in (302, 303, 307)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test",
        cookies={"narjis_owner": make_session_token()},
    ) as owner:
        result = await owner.get("/api/company/service-jobs")
        assert result.status_code == 200, result.text
        data = result.json()
        assert data["mode"] == "internal_preview_only"
        assert data["counts"]["queued"] == 1
        assert data["jobs"][0]["id"] == str(job_id)
        assert "Never show this secret" not in result.text
        assert "client_name" not in result.text
        page = await owner.get("/company")
        assert page.status_code == 200
        assert 'id="journal-overview"' in page.text
        assert 'id="funnel-overview"' in page.text
        assert "الزائر المجهول ليس عميلًا يمكن مراسلته" in page.text
