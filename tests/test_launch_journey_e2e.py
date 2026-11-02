"""Launch journey end to end:
landing -> CEO consult (HTTP) -> plan -> portal project -> bank-transfer invoice ->
owner confirms receipt -> activation exactly once (a second confirm is idempotent) ->
agents assigned. No card gateway is called."""

from __future__ import annotations

import json

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import ClientAgent, ClientProject, Payment
from src.models.ops import FunnelEvent
from src.services import catalog, funnel
from src.utils.rate_limit import consult_limiter

@pytest.fixture
async def maker(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    m = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(funnel, "session_factory", m)
    yield m
    await engine.dispose()


@pytest.fixture
def bank_transfer(monkeypatch):
    monkeypatch.setenv("CUSTOMER_BANK_TRANSFER_ENABLED", "1")


@pytest.mark.usefixtures("founding_full")
async def test_full_launch_journey_activates_exactly_once(maker, bank_transfer):
    from src.core.agent_registry import AgentRegistry
    from src.main import app

    app.state.session_factory = maker
    registry = AgentRegistry(maker)
    await registry.sync_base_agents()
    app.state.agent_registry = registry
    consult_limiter.reset()
    transport = httpx.ASGITransport(app=app)

    from src.core.owner_auth import make_session_token

    owner_cookie = {"cookie": f"narjis_owner={make_session_token()}"}

    async def call(method, path, body=None, headers=None):
        req = (
            httpx.Request(method, f"http://test{path}", json=body, headers=headers)
            if body is not None
            else httpx.Request(method, f"http://test{path}", headers=headers)
        )
        resp = await transport.handle_async_request(req)
        await resp.aread()
        return resp.status_code, resp.content

    # 1. landing
    code, html = await call("GET", "/ar/home")
    assert code == 200 and b'id="ceoProblem"' in html
    # 2-3. CEO consult over HTTP recommends a plan
    code, raw = await call(
        "POST",
        "/api/ceo/consult",
        {"problem": "عندي محل عطور في الرياض وأحتاج تسويق", "lang": "ar"},
    )
    assert code == 200, raw
    diag = json.loads(raw)
    tier = diag["plan"]["key"]
    assert tier in catalog.PACKAGES
    recommended = [a["slug"] for a in diag["agents"]]
    # 4. portal
    code, _ = await call("GET", "/portal")
    assert code == 200
    code, raw = await call(
        "POST",
        "/api/portal/projects",
        {
            "client_name": "عميل تجريبي",
            "phone": "0555123456",
            "package": tier,
            "agents": recommended,
            "addons": 0,
        },
    )
    assert code == 200, raw
    proj = json.loads(raw)
    # 5. checkout (fake gateway)
    code, raw = await call(
        "POST",
        "/api/payments",
        {
            "refund_consent": True,
            "package": tier,
            "method": "invoice",
            "customer_name": "عميل تجريبي",
            "customer_phone": "0555123456",
            "project_id": proj["project_id"],
            "addons": 0,
        },
    )
    assert code == 200, raw
    pay = json.loads(raw)
    # 6. owner confirms the transfer, then the same confirm delivered again
    for _ in range(2):
        code, raw = await call(
            "POST",
            f"/api/payments/{pay['payment_id']}/confirm-received",
            {"note": "received"},
            headers=owner_cookie,
        )
        assert code == 200, raw

    async with maker() as s:
        project = (await s.execute(select(ClientProject))).scalar_one()
        agents = (
            (await s.execute(select(ClientAgent).where(ClientAgent.project_id == project.id)))
            .scalars()
            .all()
        )
        payments = (await s.execute(select(Payment))).scalars().all()
        events = [e.event for e in (await s.execute(select(FunnelEvent))).scalars()]
    assert project.status == "active"
    assert len(payments) == 1 and payments[0].status == "paid"
    # 7. agents assigned once, no duplicates after the replayed webhook
    expected = catalog.staff_team(tier, 0, preferred=recommended)
    assert len(agents) == len(expected)
    assert len({a.slug for a in agents}) == len(agents)
    assert sum(a.slug == catalog.CEO_SLUG for a in agents) == 1
    # activation and payment success recorded exactly once
    assert events.count("payment_succeeded") == 1
    assert events.count("project_activated") == 1
    for step in (
        "ceo_problem_submitted",
        "ceo_plan_recommended",
        "portal_opened",
        "checkout_started",
        "payment_attempted",
    ):
        assert step in events, step
