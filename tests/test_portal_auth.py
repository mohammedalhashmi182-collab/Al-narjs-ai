"""Portal login: the project UUID alone is no longer a credential."""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core import portal_auth
from src.core.owner_auth import make_session_token as owner_token
from src.db.session import Base
from src.models import ClientProject
from src.models.tenant import PortalLoginCode


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def otps(monkeypatch):
    from src.interfaces import portal_routes

    sent: list[str] = []

    async def _deliver(factory, project, kind, code):
        sent.append(code)

    monkeypatch.setattr(portal_routes, "_deliver_otp", _deliver)
    return sent


def _client(maker, cookies=None):
    from src.main import app

    app.state.session_factory = maker
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", cookies=cookies or {})


async def _project(maker, status="active", **kw):
    async with maker() as s:
        p = ClientProject(client_name="عميل", phone="0555123456", email="Owner@Shop.sa", package="radd", status=status, **kw)
        s.add(p)
        await s.commit()
        return p


PROTECTED = [
    ("GET", "/api/portal/projects/{pid}"),
    ("POST", "/api/portal/projects/{pid}/agents/customer_service/wake"),
    ("POST", "/api/portal/projects/{pid}/agents/customer_service/run"),
    ("GET", "/api/portal/projects/{pid}/files"),
    ("GET", "/api/portal/projects/{pid}/knowledge"),
    ("DELETE", "/api/portal/projects/{pid}/knowledge/00000000-0000-0000-0000-000000000000"),
    ("GET", "/api/portal/projects/{pid}/replies"),
    ("GET", "/api/portal/projects/{pid}/contacts"),
    ("GET", "/api/portal/projects/{pid}/reply-settings"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
async def test_every_portal_project_endpoint_requires_a_session(maker, method, path):
    p = await _project(maker)
    async with _client(maker) as c:
        r = await c.request(method, path.format(pid=p.id), json={"answers": {}})
    assert r.status_code == 401


async def test_a_session_for_one_project_does_not_open_another(maker):
    a = await _project(maker)
    b = await _project(maker)
    async with _client(maker, {portal_auth.COOKIE_NAME: portal_auth.make_session_token(a)}) as c:
        assert (await c.get(f"/api/portal/projects/{a.id}/knowledge")).status_code == 200
        assert (await c.get(f"/api/portal/projects/{b.id}/knowledge")).status_code == 401


async def test_forged_or_revoked_sessions_are_rejected(maker):
    a = await _project(maker)
    tok = portal_auth.make_session_token(a)
    raw, sig = tok.split(".")
    async with _client(maker, {portal_auth.COOKIE_NAME: raw + "." + "0" * len(sig)}) as c:
        assert (await c.get(f"/api/portal/projects/{a.id}/knowledge")).status_code == 401
    async with _client(maker, {"narjis_owner": owner_token()}) as c:
        assert (await c.post(f"/api/owner/projects/{a.id}/portal-revoke")).json()["portal_token_version"] == 1
        # the owner keeps support access
        assert (await c.get(f"/api/portal/projects/{a.id}/knowledge")).status_code == 200
    async with _client(maker, {portal_auth.COOKIE_NAME: tok}) as c:
        assert (await c.get(f"/api/portal/projects/{a.id}/knowledge")).status_code == 401


async def test_creating_a_project_grants_its_session(maker):
    from src.core.agent_registry import AgentRegistry
    from src.main import app

    registry = AgentRegistry(maker)
    await registry.sync_base_agents()
    app.state.agent_registry = registry
    async with _client(maker) as c:
        r = await c.post("/api/portal/projects", json={"client_name": "x", "phone": "0555000000", "package": "radd"})
        assert r.status_code == 200 and portal_auth.COOKIE_NAME in r.cookies
        pid = r.json()["project_id"]
        assert (await c.get(f"/api/portal/projects/{pid}")).status_code == 200


async def test_otp_login_by_email_and_phone(maker, otps):
    p = await _project(maker)
    async with _client(maker) as c:
        # unknown identifiers get the same answer and no code
        assert (await c.post("/api/portal/login/request", json={"identifier": "nobody@x.sa"})).json()["sent"] is True
        assert otps == []
        await c.post("/api/portal/login/request", json={"identifier": "owner@shop.sa"})
        assert len(otps) == 1 and len(otps[0]) == 6
        bad = await c.post("/api/portal/login/verify", json={"identifier": "owner@shop.sa", "code": "000000" if otps[0] != "000000" else "111111"})
        assert bad.status_code == 401
        ok = await c.post("/api/portal/login/verify", json={"identifier": "owner@shop.sa", "code": otps[0]})
        assert ok.status_code == 200 and ok.json()["project_id"] == str(p.id)
        c.cookies.set(portal_auth.COOKIE_NAME, ok.cookies[portal_auth.COOKIE_NAME])
        assert (await c.get(f"/api/portal/projects/{p.id}/knowledge")).status_code == 200
        # single use
        assert (await c.post("/api/portal/login/verify", json={"identifier": "owner@shop.sa", "code": otps[0]})).status_code == 401
        await c.post("/api/portal/login/request", json={"identifier": "+966 55 512 3456"})
        r = await c.post("/api/portal/login/verify", json={"identifier": "0555123456", "code": otps[-1]})
        assert r.status_code == 200


async def test_otp_attempts_are_limited(maker, otps):
    await _project(maker)
    async with _client(maker) as c:
        await c.post("/api/portal/login/request", json={"identifier": "owner@shop.sa"})
        wrong = "000000" if otps[0] != "000000" else "111111"
        for _ in range(portal_auth.OTP_MAX_ATTEMPTS):
            await c.post("/api/portal/login/verify", json={"identifier": "owner@shop.sa", "code": wrong})
        r = await c.post("/api/portal/login/verify", json={"identifier": "owner@shop.sa", "code": otps[0]})
        assert r.status_code == 401
        for _ in range(5):
            await c.post("/api/portal/login/request", json={"identifier": "owner@shop.sa"})
        assert len(otps) == 3  # rate limited per 15 minutes


async def test_owner_magic_link_is_single_use(maker):
    p = await _project(maker)
    async with _client(maker, {"narjis_owner": owner_token()}) as c:
        url = (await c.post(f"/api/owner/projects/{p.id}/portal-link")).json()["url"]
    path = url.split("://", 1)[1].split("/", 1)[1]
    async with _client(maker) as c:
        r = await c.get("/" + path, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/portal"
        cookie = r.cookies[portal_auth.COOKIE_NAME]
        r2 = await c.get("/" + path, follow_redirects=False)
        assert r2.headers["location"].startswith("/portal?login=expired")
    async with _client(maker, {portal_auth.COOKIE_NAME: cookie}) as c:
        assert (await c.get(f"/api/portal/projects/{p.id}/knowledge")).status_code == 200


async def test_legacy_uuid_exchange_only_for_unpaid_projects(maker):
    active = await _project(maker)
    pending = await _project(maker, status="pending")
    async with _client(maker) as c:
        assert (await c.post("/api/portal/session/legacy", json={"project_id": str(active.id)})).status_code == 401
        r = await c.post("/api/portal/session/legacy", json={"project_id": str(pending.id)})
        assert r.status_code == 200 and r.json()["limited"] is True
        limited = r.cookies[portal_auth.COOKIE_NAME]
    async with _client(maker, {portal_auth.COOKIE_NAME: limited}) as c:
        # authenticated (past the 401), still gated by payment
        assert (await c.get(f"/api/portal/projects/{pending.id}/knowledge")).status_code == 402
        assert (await c.get(f"/api/portal/session")).status_code == 200
    # once paid, the limited session stops working: sign in with OTP / magic link
    async with maker() as s:
        row = await s.get(ClientProject, pending.id)
        row.status = "active"
        await s.commit()
    async with _client(maker, {portal_auth.COOKIE_NAME: limited}) as c:
        assert (await c.get(f"/api/portal/projects/{pending.id}/knowledge")).status_code == 401


async def test_codes_are_stored_hashed(maker, otps):
    await _project(maker)
    async with _client(maker) as c:
        await c.post("/api/portal/login/request", json={"identifier": "owner@shop.sa"})
    async with maker() as s:
        row = (await s.execute(select(PortalLoginCode))).scalar_one()
        assert otps[0] not in row.code_hash


@pytest.mark.parametrize("status", ["expired", "demo", "cancelled", "active"])
async def test_legacy_exchange_refuses_projects_that_were_ever_live(maker, status):
    """Regression (audit C3): an expired project opened by UUID alone leaked
    contacts and reply drafts. Only never-paid projects may use the exchange."""
    from datetime import datetime, timedelta, timezone

    p = await _project(maker, status=status, current_period_end=datetime.now(timezone.utc) - timedelta(days=3))
    async with _client(maker) as c:
        r = await c.post("/api/portal/session/legacy", json={"project_id": str(p.id)})
        assert r.status_code == 401
        assert (await c.get(f"/api/portal/projects/{p.id}/contacts")).status_code == 401
        assert (await c.get(f"/api/portal/projects/{p.id}/replies")).status_code == 401


async def test_legacy_exchange_refuses_a_pending_project_that_was_paid_before(maker):
    from uuid import uuid4

    p = await _project(maker, status="pending", last_payment_id=uuid4())
    async with _client(maker) as c:
        assert (await c.post("/api/portal/session/legacy", json={"project_id": str(p.id)})).status_code == 401


async def test_a_limited_session_dies_when_the_project_expires(maker):
    p = await _project(maker, status="pending")
    async with _client(maker) as c:
        r = await c.post("/api/portal/session/legacy", json={"project_id": str(p.id)})
        limited = r.cookies[portal_auth.COOKIE_NAME]
    async with maker() as s:
        row = await s.get(ClientProject, p.id)
        row.status = "expired"
        await s.commit()
    async with _client(maker, {portal_auth.COOKIE_NAME: limited}) as c:
        assert (await c.get(f"/api/portal/projects/{p.id}/contacts")).status_code == 401
        assert (await c.get(f"/api/portal/projects/{p.id}")).status_code == 401


async def test_session_probe_anonymous_is_200_not_console_error(maker):
    # checkout (/portal) probes the session on every load; anonymous must not be a 401
    async with _client(maker) as c:
        r = await c.get("/api/portal/session?probe=1")
        assert r.status_code == 200 and r.json() == {"authenticated": False}
        assert (await c.get("/api/portal/session")).status_code == 401
