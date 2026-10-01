"""Owner login hardening.

``POST /login`` reads a JSON body. A non-JSON body (form post, empty payload,
wrong content type) used to raise inside ``request.json()`` and answer 500,
which tells the caller nothing and floods the error log. It must answer 400
with the same error shape the login page already renders.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.config.settings import settings
from src.core.owner_auth import make_session_token
from src.db.session import Base

BAD_BODIES = [
    ({"data": "password=nope", "headers": {"Content-Type": "application/x-www-form-urlencoded"}},
     "form encoded"),
    ({"data": "", "headers": {"Content-Type": "application/json"}}, "empty body"),
    ({"json": ["not", "a", "dict"], "headers": {"Content-Type": "application/json"}}, "json array"),
]


async def _make_engine():
    from src import models  # noqa: F401  (registers every table on Base.metadata)

    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def client():
    from src.main import app

    engine, maker = await _make_engine()
    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


@pytest.mark.parametrize("payload,_label", BAD_BODIES)
async def test_malformed_login_body_returns_400(client, payload, _label):
    r = await client.post("/login", **payload)
    assert r.status_code == 400, r.text
    assert r.json()["error"] == "wrong_password"


async def test_wrong_password_returns_error_shape(client):
    r = await client.post("/login", json={"password": "definitely-not-the-owner-password"})
    assert r.status_code == 200
    assert r.json() == {"error": "wrong_password"}


async def test_correct_password_sets_owner_cookie_and_redirects(client):
    r = await client.post("/login", json={"password": settings.owner_password}, follow_redirects=False)
    assert r.status_code == 303
    cookies = r.headers.get_list("set-cookie")
    assert any(c.startswith("narjis_owner=") for c in cookies)
    assert any("HttpOnly" in c for c in cookies)


async def test_session_cookie_authorizes_owner_endpoints(client):
    token = make_session_token()
    r = await client.get("/api/company/queue", cookies={"narjis_owner": token})
    assert r.status_code == 200
    r2 = await client.get("/api/company/queue")
    assert r2.status_code in (401, 403)