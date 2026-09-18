"""Tests for the Autonomous Company Operating System (Phase C).

Covers: the observatory (real data, never fabricated), opportunity
deduplication, policy/autonomy gating, the CEO loop's idempotent work creation,
and the owner-gated company API surface.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from src.automation.ceo_engine import CompanyBrain
from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.services import company_observatory
from src.services.governance import PolicyService
from src.services.opportunity_engine import OpportunityEngine


async def _make_engine():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def db():
    """One shared in-memory DB: yields (session, session_factory)."""
    engine, maker = await _make_engine()
    async with maker() as session:
        yield session, maker
    await engine.dispose()


@pytest.fixture
async def maker():
    engine, maker = await _make_engine()
    yield maker
    await engine.dispose()


# ---------------------------------------------------------------------------
# Observatory
# ---------------------------------------------------------------------------


async def test_observatory_reports_real_metrics_and_unknown(maker) -> None:
    obs = company_observatory.CompanyObservatory(maker)
    snap = await obs.snapshot()

    assert snap["company"]["name"] == "Al-Narjis AI"
    assert snap["company"]["agents_total"] == 0  # no rows in an empty DB
    assert snap["acquisition"]["total_leads"] == 0
    assert snap["revenue"]["paid_total_sar"] == 0.0
    # Metrics with no source table must stay UNKNOWN — never invented.
    assert snap["revenue"]["mrr_sar"] == company_observatory.UNKNOWN
    assert snap["revenue"]["cac_sar"] == company_observatory.UNKNOWN
    for section in company_observatory.OBSERVATORY_SECTIONS:
        assert section in snap


async def test_observatory_aggregates_real_lead_data(db) -> None:
    from src.models import AcquisitionLead

    session, maker = db
    session.add(AcquisitionLead(company_name="شركة التجربة", lead_status="NEW", priority="HIGH", priority_score=90))
    await session.commit()

    obs = company_observatory.CompanyObservatory(maker)
    snap = await obs.snapshot()

    assert snap["acquisition"]["total_leads"] == 1
    assert snap["acquisition"]["by_status"].get("NEW") == 1
    assert snap["acquisition"]["high_priority_active"] == 1


# ---------------------------------------------------------------------------
# Opportunity engine (dedup + promotion)
# ---------------------------------------------------------------------------


async def test_opportunity_dedup(maker) -> None:
    engine = OpportunityEngine(maker)
    first = await engine.create(
        title="عملية متابعة العملاء بسبب التأخير والمتابعة المجدولة",
        owner_agent="customer_manager",
        area="acquisition",
        source="ceo_loop",
        confidence=0.9,
        priority=200,
    )
    second = await engine.create(
        title="عملية متابعة العملاء بسبب التأخير والمتابعة المجدولة",
        owner_agent="customer_manager",
        area="acquisition",
        source="ceo_loop",
        confidence=0.9,
        priority=200,
    )

    assert first["deduplicated"] is False
    assert second["deduplicated"] is True

    async with maker() as session:
        from src.models import Opportunity

        count = (await session.execute(select(func.count()).select_from(Opportunity))).scalar_one()
    assert count == 1


async def test_opportunity_promote_to_task_is_idempotent(maker) -> None:
    engine = OpportunityEngine(maker)
    opp = await engine.create(
        title="تأهيل العملاء الجدد المحتملين",
        owner_agent="sales_closer",
        area="acquisition",
        source="ceo_loop",
        confidence=0.85,
        priority=180,
    )
    task1 = await engine.promote_to_task(opp["key"], department="acquisition")
    task2 = await engine.promote_to_task(opp["key"], department="acquisition")

    assert task1 is not None
    assert task1["owner_agent"] == "sales_closer"
    assert task2 == task1  # no duplicate tasks

    async with maker() as session:
        from src.models import Task

        count = (await session.execute(select(func.count()).select_from(Task))).scalar_one()
    assert count == 1


# ---------------------------------------------------------------------------
# Governance / autonomy levels
# ---------------------------------------------------------------------------


async def test_governance_default_internal_allowed_external_escalated(maker) -> None:
    gov = PolicyService(maker)

    internal = await gov.authorize("marketing_agent", "internal")
    assert internal["allowed"] is True
    assert internal["outcome"] == "allowed"

    external = await gov.authorize("marketing_agent", "external")
    assert external["allowed"] is False
    assert external["outcome"] == "escalated"

    destructive = await gov.authorize("marketing_agent", "destructive")
    assert destructive["allowed"] is False
    assert destructive["level_required"] == 3


async def test_governance_level2_can_do_external(maker) -> None:
    gov = PolicyService(maker)
    await gov.upsert_policy(
        "sales_closer",
        autonomy_level=2,
        allowed_actions=["read", "internal", "external"],
        requires_approval=["owner_approval", "budget_spend"],
        budget_usd=250.0,
    )

    result = await gov.authorize("sales_closer", "external")
    assert result["allowed"] is True
    assert result["level_label"] == "pre_authorized_external"


# ---------------------------------------------------------------------------
# CEO brain / daily loop
# ---------------------------------------------------------------------------


async def test_ceo_loop_creates_and_deduplicates_work(db) -> None:
    from src.models import AcquisitionLead, Decision

    session, maker = db
    brain = CompanyBrain(maker)

    session.add(AcquisitionLead(
        company_name="عميل جديد",
        lead_status="NEW",
        priority="HIGH",
        priority_score=90,
        email="lead@example.com",
    ))
    session.add(AcquisitionLead(
        company_name="عميل متابعة",
        lead_status="REPLIED",
        priority="HIGH",
        priority_score=85,
        next_followup_at=None,
    ))
    await session.commit()

    first = await brain.run_once()
    second = await brain.run_once()

    assert len(first["priorities"]) > 0

    # Opportunities deduplicated across runs.
    keys1 = {o["key"] for o in first["priorities"]}
    keys2 = {o["key"] for o in second["priorities"]}
    assert keys1 == keys2

    # Promoted tasks are never duplicated.
    promoted1 = {p["task_key"] for p in first["promoted"]}
    promoted2 = {p["task_key"] for p in second["promoted"]}
    assert promoted1 == promoted2

    async with maker() as session:
        decision_count = (
            await session.execute(select(func.count()).select_from(Decision))
        ).scalar_one()
    assert decision_count == 2  # one per run


# ---------------------------------------------------------------------------
# Owner API surface
# ---------------------------------------------------------------------------


@pytest.fixture
async def api(maker):
    """Real app with DB + company brain swapped for the in-memory test ones."""
    from src.main import app

    app.state.session_factory = maker
    app.state.company_brain = CompanyBrain(maker)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"narjis_owner": make_session_token()},
    ) as client:
        yield client
    app.state.company_brain = None


async def test_company_api_endpoints(api) -> None:
    resp = await api.get("/api/company/state")
    assert resp.status_code == 200
    body = resp.json()
    for section in company_observatory.OBSERVATORY_SECTIONS:
        assert section in body

    resp = await api.post("/api/ceo/run")
    assert resp.status_code == 200
    assert "priorities" in resp.json()

    resp = await api.get("/api/opportunities")
    assert resp.status_code == 200
    assert "opportunities" in resp.json()

    resp = await api.get("/api/governance/policies")
    assert resp.status_code == 200
    assert "policies" in resp.json()

    resp = await api.get("/api/decisions")
    assert resp.status_code == 200
    assert "decisions" in resp.json()

    resp = await api.get("/api/experiments")
    assert resp.status_code == 200
    assert "experiments" in resp.json()


async def test_company_api_requires_owner(maker) -> None:
    from src.main import app

    app.state.session_factory = maker
    app.state.company_brain = CompanyBrain(maker)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/company/state")
        assert resp.status_code in (302, 303, 401, 403)
        resp = await client.post("/api/ceo/run")
        assert resp.status_code in (302, 303, 401, 403)
    app.state.company_brain = None
