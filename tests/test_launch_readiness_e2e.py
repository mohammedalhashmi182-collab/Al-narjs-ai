"""Launch readiness: diagnosis -> portal project -> checkout -> mocked Moyasar
paid webhook -> activation -> staffed team, for every tier (+ add-ons)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import ClientAgent, ClientProject, Payment
from src.services import catalog, ceo_advisor, renewals
from src.services import payments as pm

SECRET = "whsec-test"


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def mock_moyasar(monkeypatch):
    """Fake Moyasar: invoice creation + a GET that reports the exact paid total."""
    from src.config import settings as st

    monkeypatch.setattr(st, "moyasar_api_secret", "sk_" + "live_" + "FAKE-VALUE-FOR-TESTS-ONLY-NOT-A-REAL-KEY")
    monkeypatch.setattr(st, "moyasar_publishable_key", "pk_" + "live_" + "FAKE-VALUE-FOR-TESTS-ONLY-NOT-A-REAL-KEY")
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
        iid = f"inv_{state['n']}"
        return _R(201, {"id": iid, "url": f"https://checkout.moyasar.com/invoices/{iid}"})

    async def _get(self, url, *a, **k):
        return _R(200, {"id": url.rsplit("/", 1)[-1], "status": "paid",
                        "amount": state["amount"], "currency": "SAR"})

    monkeypatch.setattr(httpx.AsyncClient, "post", _post)
    monkeypatch.setattr(httpx.AsyncClient, "get", _get)
    return state


CASES = [
    # problem, expected tier, addons on top of the diagnosis
    ("عندي محل عطور في الرياض وأحتاج تسويق", "bidaya", 0),
    ("صالون نسائي في الرياض: السوشيال ضعيف والإعلانات ما تجيب نتائج", "bidaya", 0),
    ("مطعم في جدة: سوشيال ضعيف، إعلانات بلا نتائج، ضغط ردود واتساب، ومتجر إلكتروني", "numuw", 0),
    ("أبي شركة كاملة تغطي كل شي", "sharikat", 0),
    ("عيادة أسنان في الدمام تحتاج تسويق", "bidaya", 2),
    ("شركة مقاولات: أبي شركة كاملة", "sharikat", 3),
]


@pytest.mark.parametrize("problem,tier,extra", CASES)
@pytest.mark.usefixtures("founding_full")
async def test_every_tier_end_to_end(maker, mock_moyasar, problem, tier, extra):
    from src.main import app

    diag = ceo_advisor.build_result(ceo_advisor.diagnose_rules(problem))
    assert diag["plan"]["key"] == tier
    addons = diag["plan"]["addons"] + extra
    recommended = [a["slug"] for a in diag["agents"]]
    assert "&agents=" in diag["cta"]["subscribe"] or not recommended

    from src.core.agent_registry import AgentRegistry

    app.state.session_factory = maker
    registry = AgentRegistry(maker)
    await registry.sync_base_agents()
    app.state.agent_registry = registry
    transport = httpx.ASGITransport(app=app)
    # httpx.AsyncClient.post is mocked for Moyasar; drive the app through the transport directly.
    async def call(method, path, json):
        req = httpx.Request(method, f"http://test{path}", json=json)
        resp = await transport.handle_async_request(req)
        await resp.aread()
        return resp.status_code, __import__("json").loads(resp.content)

    code, proj = await call("POST", "/api/portal/projects", {
        "client_name": "عميل تجريبي", "phone": "0555123456", "package": tier,
        "agents": recommended, "addons": addons})
    assert code == 200, proj
    allowance = catalog.plan_agent_count(tier) + addons
    expected_team = catalog.staff_team(tier, addons, preferred=recommended)
    # Add-ons cannot invent specialists past the roster (الشركات is already the full team).
    assert len(proj["team"]) == len(expected_team)
    staffed = {t["slug"] for t in proj["team"]}
    for slug in recommended[:allowance]:
        if slug in {t for t in expected_team}:
            assert slug in staffed, f"diagnosed agent {slug} not staffed"

    code, pay = await call("POST", "/api/payments", {
        "refund_consent": True, "package": tier, "method": "creditcard", "customer_name": "عميل تجريبي",
        "customer_phone": "0555123456", "project_id": proj["project_id"], "addons": addons})
    assert code == 200, pay
    # a first monthly order carries the tier's one-time setup fee
    assert pay["total"] == pm.total_with_vat(catalog.plan_amount(tier, "monthly", addons) + catalog.setup_fee(tier))

    code, hook = await call("POST", "/webhooks/moyasar", {
        "type": "payment_paid", "secret_token": SECRET,
        "data": {"metadata": {"order_id": pay["payment_id"]}}})
    assert code == 200 and hook["status"] == "paid", hook

    async with maker() as s:
        project = (await s.execute(select(ClientProject))).scalar_one()
        agents = (await s.execute(select(ClientAgent).where(ClientAgent.project_id == project.id))).scalars().all()
    assert project.status == "active" and project.current_period_end is not None
    assert project.addon_agents == addons
    assert len(agents) == len(expected_team)
    assert sum(a.slug == catalog.CEO_SLUG for a in agents) == 1


async def test_addons_bought_at_checkout_are_staffed_on_activation(maker):
    """Add-ons chosen at signup (on the project) are charged and staffed on activation."""
    async with maker() as s:
        proj = ClientProject(client_name="c", phone="0555000009", package="bidaya", status="pending",
                             addon_agents=2)
        s.add(proj)
        await s.flush()
        for slug in catalog.get_team("bidaya"):
            s.add(ClientAgent(project_id=proj.id, slug=slug, status="dormant"))
        await s.commit()
        pay = await pm.create_payment(s, "bidaya", "c", "0555000009", None, project_id=proj.id, addons=2)
        pay.status = "paid"
        await s.commit()
        out = await pm.activate_subscription(s, pay)
        rows = (await s.execute(select(ClientAgent).where(ClientAgent.project_id == proj.id))).scalars().all()
    assert len(out["staffed"]) == 2
    assert len(rows) == 1 + catalog.plan_agent_count("bidaya") + 2


def test_staff_team_sizes():
    specialists = len(catalog.EMPLOYEES) - 1
    for key in catalog.PACKAGES:
        for addons in (0, 1, 5):
            team = catalog.staff_team(key, addons)
            allowance = catalog.plan_agent_count(key) + addons
            assert team[0] == catalog.CEO_SLUG
            assert len(team) == 1 + min(allowance, specialists)
            assert len(set(team)) == len(team)
    assert catalog.staff_team("radd", 0, ["sales_closer"]) == [catalog.CEO_SLUG, "sales_closer", "customer_service"]
    assert catalog.staff_team("radd", 0, ["nope"])[1] == "customer_service"


async def test_backfill_puts_legacy_subscribers_on_the_cycle(maker):
    now = datetime(2026, 10, 13, tzinfo=timezone.utc)
    async with maker() as s:
        old = ClientProject(client_name="a", phone="1", package="bay", status="active", addon_agents=1)
        s.add(old)
        await s.commit()
        dry = await renewals.backfill_legacy_subscriptions(s, now=now)
        assert dry["count"] == 1 and old.current_period_end is None
        res = await renewals.backfill_legacy_subscriptions(s, now=now, dry_run=False)
        rows = (await s.execute(select(ClientAgent).where(ClientAgent.project_id == old.id))).scalars().all()
    end = old.current_period_end if old.current_period_end.tzinfo else old.current_period_end.replace(tzinfo=timezone.utc)
    assert end > now
    assert len(rows) == 1 + 6 + 1
    assert res["projects"][0]["staffed"]
