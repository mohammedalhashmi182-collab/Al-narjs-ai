"""A: first-party funnel analytics: allow-lists, privacy, never breaks the journey."""

import json

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models.ops import FunnelEvent
from src.services import funnel
from src.utils.rate_limit import beacon_limiter, consult_limiter


@pytest.fixture
async def api(monkeypatch):
    import src.models  # noqa: F401
    from src.core.owner_auth import make_session_token
    from src.main import app

    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    app.state.session_factory = maker
    monkeypatch.setattr(funnel, "session_factory", maker)
    beacon_limiter.reset()
    consult_limiter.reset()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, maker, make_session_token()
    beacon_limiter.reset()
    consult_limiter.reset()
    await engine.dispose()


async def _events(maker):
    async with maker() as s:
        return list((await s.execute(select(FunnelEvent))).scalars())


def test_props_allow_list():
    out = funnel.clean_props(
        {
            "plan": "team",
            "lang": "EN",
            "page": "/en/home",
            "message": "secret text",
            "phone": "0500000000",
            "plan2": "x",
            "method": "card; drop",
        }
    )
    assert out == {"plan": "team", "lang": "en", "page": "/en/home"}
    assert funnel.clean_props("nope") == {}


async def test_beacon_stores_only_allowed_client_events(api):
    client, maker, _ = api
    r = await client.post(
        "/api/events",
        json={
            "event": "landing_view",
            "props": {"lang": "ar", "page": "/ar/home", "message": "hi 0500000000"},
        },
    )
    assert r.status_code == 204
    # Server-only and unknown events are ignored from the browser.
    for name in ("payment_succeeded", "project_activated", "evil"):
        assert (await client.post("/api/events", json={"event": name})).status_code == 204
    # Garbage input never errors.
    assert (await client.post("/api/events", content=b"{not json")).status_code == 204
    evs = await _events(maker)
    assert [e.event for e in evs] == ["landing_view"]
    assert evs[0].props == {"lang": "ar", "page": "/ar/home"}
    assert (
        evs[0].session_hash and "127" not in evs[0].session_hash and len(evs[0].session_hash) == 24
    )


async def test_beacon_size_and_rate_limits(api):
    client, maker, _ = api
    big = json.dumps({"event": "landing_view", "props": {"page": "/" + "a" * 2000}})
    assert (await client.post("/api/events", content=big)).status_code == 413
    codes = [
        (await client.post("/api/events", json={"event": "landing_view"})).status_code
        for _ in range(35)
    ]
    assert codes.count(429) >= 5 and set(codes) <= {204, 429}


@pytest.mark.parametrize(
    "hdr", [{"DNT": "1"}, {"Sec-GPC": "1"}, {"Cookie": "narjs_consent=denied"}]
)
async def test_dnt_gpc_and_refused_banner_respected(api, hdr):
    client, maker, _ = api
    assert (
        await client.post("/api/events", json={"event": "landing_view"}, headers=hdr)
    ).status_code == 204
    assert await _events(maker) == []


async def test_db_failure_never_breaks_the_journey(api, monkeypatch):
    client, maker, _ = api

    async def boom(*a, **k):
        raise RuntimeError("db down password=hunter2")

    monkeypatch.setattr(funnel, "_store", boom)
    assert await funnel.track("landing_view") is False
    assert (await client.post("/api/events", json={"event": "landing_view"})).status_code == 204
    r = await client.post(
        "/api/ceo/consult",
        json={"problem": "متجري على سلة مبيعاته ضعيفة والعملاء يسألون كثيرا", "lang": "ar"},
    )
    assert r.status_code == 200
    assert (await client.get("/portal")).status_code == 200


async def test_server_side_consult_and_portal_events(api):
    client, maker, _ = api
    r = await client.post(
        "/api/ceo/consult",
        json={"problem": "متجري على سلة مبيعاته ضعيفة والعملاء يسألون كثيرا", "lang": "ar"},
    )
    assert r.status_code == 200
    assert (await client.get("/portal")).status_code == 200
    evs = await _events(maker)
    names = [e.event for e in evs]
    assert "ceo_problem_submitted" in names and "portal_opened" in names
    if r.json().get("plan") and r.json().get("offer", True):
        assert "ceo_plan_recommended" in names
    for e in evs:  # no problem text anywhere in stored events
        assert "سلة" not in json.dumps(e.props, ensure_ascii=False)
        assert set(e.props) <= {"plan", "lang", "page", "method"}


async def test_checkout_started_but_no_payment_attempt_while_closed(api):
    from src.services import payments as pm

    assert pm.MOYASAR_ON_HOLD is True
    client, maker, _ = api
    r = await client.post(
        "/api/payments",
        json={
            "package": "team",
            "method": "creditcard",
            "customer_name": "T",
            "customer_phone": "0500000000",
            "refund_consent": True,
        },
    )
    assert r.status_code >= 400  # payments stay closed
    names = [e.event for e in await _events(maker)]
    assert "payment_attempted" not in names and "payment_succeeded" not in names


async def test_owner_funnel_report_auth_and_conversion(api):
    client, maker, token = api
    for name, n in (("landing_view", 4), ("ceo_consult_open", 2), ("ceo_problem_submitted", 1)):
        for _ in range(n):
            await funnel.track(name)
    assert (await client.get("/api/owner/funnel")).status_code in (401, 403, 307, 303)
    r = await client.get("/api/owner/funnel", cookies={"narjis_owner": token})
    assert r.status_code == 200
    steps = {s["event"]: s for s in r.json()["steps"]}
    assert [s["event"] for s in r.json()["steps"]] == list(funnel.FUNNEL_STEPS)
    assert steps["landing_view"]["count"] == 4
    assert steps["ceo_consult_open"]["conversion_from_previous_pct"] == 50.0
    assert steps["ceo_problem_submitted"]["conversion_from_previous_pct"] == 50.0
    assert steps["payment_succeeded"]["count"] == 0


def test_payment_events_stay_wired_in_code():
    import inspect

    from src import main
    from src.services import payments

    src_main = inspect.getsource(main)
    assert 'funnel.track("payment_attempted"' in src_main
    assert 'funnel.track("payment_succeeded"' in src_main
    assert 'funnel.track("checkout_started"' in src_main
    assert 'funnel.track("project_activated"' in inspect.getsource(payments)


def test_landing_has_beacon_without_text():
    from pathlib import Path

    html = Path("src/web/templates/landing.html").read_text(encoding="utf-8")
    assert "narjsBeacon('landing_view')" in html and "narjsBeacon('ceo_consult_open')" in html
    assert "doNotTrack" in html and "narjs_consent=denied" in html
