"""Launch journey end to end (sandbox/mock gateway only):
landing -> CEO consult (HTTP) -> plan -> portal project -> checkout ->
paid webhook -> activation exactly once (duplicate webhook is idempotent) ->
agents assigned. Real Moyasar is never called; the release hold is lifted only
inside this test via the existing ``moyasar_release`` fixture."""

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

SECRET = "whsec-test"  # pragma: allowlist secret


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
def fake_gateway(monkeypatch, moyasar_release):
    from src.config import settings as st

    monkeypatch.setattr(
        st, "moyasar_api_secret", "sk_" + "live_" + "FAKE-VALUE-FOR-TESTS-ONLY-NOT-A-REAL-KEY"
    )
    monkeypatch.setattr(
        st, "moyasar_publishable_key", "pk_" + "live_" + "FAKE-VALUE-FOR-TESTS-ONLY-NOT-A-REAL-KEY"
    )
    monkeypatch.setattr(st, "moyasar_webhook_secret", SECRET)
    state = {"amount": 0, "n": 0}

    class _R:
        def __init__(self, code, body):
            self.status_code, self._b, self.text = code, body, ""

        def json(self):
            return self._b

    async def _post(self, url, *a, **k):
        state["n"] += 1
        state["amount"] = (k.get("json") or {}).get("amount", 0)
        return _R(
            201, {"id": f"inv_{state['n']}", "url": "https://checkout.moyasar.com/invoices/x"}
        )

    async def _get(self, url, *a, **k):
        return _R(
            200,
            {
                "id": url.rsplit("/", 1)[-1],
                "status": "paid",
                "amount": state["amount"],
                "currency": "SAR",
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", _post)
    monkeypatch.setattr(httpx.AsyncClient, "get", _get)
    return state


@pytest.mark.usefixtures("founding_full")
async def test_full_launch_journey_activates_exactly_once(maker, fake_gateway):
    from src.core.agent_registry import AgentRegistry
    from src.main import app

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
            "method": "creditcard",
            "customer_name": "عميل تجريبي",
            "customer_phone": "0555123456",
            "project_id": proj["project_id"],
            "addons": 0,
        },
    )
    assert code == 200, raw
    pay = json.loads(raw)
    hook = {
        "type": "payment_paid",
        "secret_token": SECRET,
        "data": {"metadata": {"order_id": pay["payment_id"]}},
    }
    # 6. paid webhook, then the same webhook delivered again
    for _ in range(2):
        code, raw = await call("POST", "/webhooks/moyasar", hook)
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
