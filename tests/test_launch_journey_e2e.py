"""Launch journey end to end:
landing -> CEO consult -> plan -> CRM lead -> portal project -> hosted card invoice ->
mocked Moyasar verification -> activation, CRM conversion and staffing exactly once."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import AcquisitionLead, ClientAgent, ClientProject, Payment
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


@pytest.mark.usefixtures("founding_full")
async def test_full_launch_journey_activates_exactly_once(maker, monkeypatch):
    from src.config.settings import get_settings
    from src.core.agent_registry import AgentRegistry
    from src.core.portal_auth import make_lead_token
    from src.main import app
    from src.services import payments as pm

    settings = get_settings()
    monkeypatch.setattr(settings, "moyasar_api_secret", "sk_" + "live_journey")
    monkeypatch.setattr(settings, "moyasar_publishable_key", "pk_" + "live_journey")

    async def _initiate(session, payment, source, **kwargs):
        payment.gateway = "moyasar"
        payment.gateway_payment_id = "inv_journey"
        payment.gateway_source = "invoice"
        await session.commit()
        return {"id": "inv_journey", "checkout_url": "https://checkout.moyasar.com/invoices/inv_journey?lang=ar"}

    monkeypatch.setattr(pm, "initiate_moyasar", _initiate)
    monkeypatch.setattr("src.main._lead_side_effects", AsyncMock())

    app.state.session_factory = maker
    registry = AgentRegistry(maker)
    await registry.sync_base_agents()
    app.state.agent_registry = registry
    consult_limiter.reset()
    transport = httpx.ASGITransport(app=app)

    async def call(method, path, body=None):
        req = (
            httpx.Request(method, f"http://test{path}", json=body)
            if body is not None
            else httpx.Request(method, f"http://test{path}")
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
    code, raw = await call("POST", "/api/leads", {"name": "عميل تجريبي", "phone": "0555123456"})
    assert code == 200, raw
    lead_id = json.loads(raw)["lead_id"]
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
            "method": "mada",
            "customer_name": "عميل تجريبي",
            "customer_phone": "0555123456",
            "project_id": proj["project_id"],
            "lead_token": make_lead_token(UUID(lead_id)),
            "addons": 0,
        },
    )
    assert code == 200, raw
    pay = json.loads(raw)
    # 6. The invoice callback only locates the order. The API confirms the charge.
    gateway_get = AsyncMock(return_value=httpx.Response(200, json={
        "id": "inv_journey", "status": "paid", "amount": pay["total"], "currency": "SAR",
    }))
    monkeypatch.setattr(httpx.AsyncClient, "get", gateway_get)
    for already in (False, True):
        code, raw = await call(
            "POST",
            "/webhooks/moyasar/invoice",
            {"id": "inv_journey", "metadata": {"order_id": pay["payment_id"]}},
        )
        assert code == 200, raw
        assert json.loads(raw)["already"] is already
    gateway_get.assert_awaited_once()
    assert gateway_get.await_args.args[0] == f"{pm.MOYASAR_INVOICES_URL}/inv_journey"

    async with maker() as s:
        project = (await s.execute(select(ClientProject))).scalar_one()
        agents = (
            (await s.execute(select(ClientAgent).where(ClientAgent.project_id == project.id)))
            .scalars()
            .all()
        )
        payments = (await s.execute(select(Payment))).scalars().all()
        lead = await s.get(AcquisitionLead, UUID(lead_id))
        events = [e.event for e in (await s.execute(select(FunnelEvent))).scalars()]
    assert project.status == "active"
    assert lead.lead_status == "WON"
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
