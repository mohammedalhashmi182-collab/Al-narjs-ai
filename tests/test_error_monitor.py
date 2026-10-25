"""B: central exception tracking: scrubbed, deduplicated, throttled, never crashes."""

import logging

import httpx
import pytest
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models.ops import ErrorEvent
from src.services import error_monitor, ops_monitor

FAKE = {
    "bearer": "Bearer sk-live-FAKE0123456789abcdefSECRET",
    "wa": "EAAFAKEwhatsappTOKEN0123456789abcdefghij",  # pragma: allowlist secret
    "tg": "123456789:AAFAKEtelegramTOKEN_0123456789abcdef",
    "card": "4111 1111 1111 1111",
    "cvc": "cvc=737",
    "phone": "+966500000001",
    "email": "customer@example.com",
    "msg": "رسالة العميل السرية",
    "gemini": "AIzaFAKEgeminiKEY0123456789abcdefgh",  # pragma: allowlist secret
}


def _leaks(text: str) -> list[str]:
    needles = [
        "sk-live-FAKE",
        "EAAFAKE",
        "AAFAKEtelegram",
        "4111",
        "737",
        "966500000001",
        "customer@example.com",
        "رسالة",
        "AIzaFAKE",
        "hunter2",
    ]
    return [n for n in needles if n in text]


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
    monkeypatch.setattr(error_monitor, "session_factory", maker)
    error_monitor._reset()
    ops_monitor._reset_throttle()
    alerts = []

    async def fake_alert(key, message, **kw):
        alerts.append(message)
        return True

    monkeypatch.setattr(ops_monitor, "alert_owner", fake_alert)

    async def boom(request: Request):
        await request.body()
        raise RuntimeError(
            f"upstream failed {FAKE['bearer']} token={FAKE['wa']} {FAKE['tg']} "
            f"card {FAKE['card']} {FAKE['cvc']} {FAKE['phone']} {FAKE['email']} "
            f"{FAKE['msg']} {FAKE['gemini']} password=hunter2"
        )

    app.add_api_route("/__test/boom", boom, methods=["POST"])
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, maker, make_session_token(), alerts
    app.router.routes[:] = [
        r for r in app.router.routes if getattr(r, "path", "") != "/__test/boom"
    ]
    await engine.dispose()


async def _rows(maker):
    await error_monitor.drain()
    async with maker() as s:
        return list((await s.execute(select(ErrorEvent))).scalars())


def test_scrub_removes_secrets_and_customer_text():
    raw = " ".join(FAKE.values()) + " password=hunter2 Authorization: Basic Zm9vOmJhcg=="
    out = error_monitor.scrub(raw)
    assert _leaks(out) == [], out
    assert "Zm9vOmJhcg" not in out
    assert len(error_monitor.scrub("x" * 5000)) <= error_monitor.MESSAGE_MAX


async def test_uncaught_exception_is_captured_scrubbed_with_request_id(api, caplog):
    client, maker, token, alerts = api
    caplog.set_level(logging.DEBUG)
    r = await client.post(
        "/__test/boom",
        headers={
            "Authorization": FAKE["bearer"],
            "X-Request-ID": "req-abc123",
            "Cookie": f"narjis_owner=FAKECOOKIE; s={FAKE['wa']}",
        },
        json={"card": FAKE["card"], "message": FAKE["msg"], "token": FAKE["tg"]},
    )
    assert r.status_code == 500
    assert _leaks(r.text) == []
    rows = await _rows(maker)
    assert len(rows) == 1
    row = rows[0]
    assert row.source == "server" and row.error_type == "RuntimeError"
    assert row.route == "/__test/boom" and row.last_request_id == "req-abc123"
    stored = " ".join(
        str(getattr(row, c)) for c in ("message", "route", "error_type", "environment")
    )
    assert _leaks(stored) == [] and "FAKECOOKIE" not in stored
    assert _leaks(caplog.text) == [] and "FAKECOOKIE" not in caplog.text
    assert all(_leaks(a) == [] for a in alerts)
    # Owner summary: auth required, scrubbed content only.
    assert (await client.get("/api/owner/errors")).status_code in (401, 403, 303, 307)
    s = await client.get("/api/owner/errors", cookies={"narjis_owner": token})
    assert s.status_code == 200 and s.json()["by_source"] == {"server": 1}
    assert _leaks(s.text) == []


async def test_dedupe_and_throttle(api, monkeypatch):
    client, maker, _, _ = api
    for _ in range(20):
        await client.post("/__test/boom", json={})
    rows = await _rows(maker)
    assert len(rows) == 1 and rows[0].count == 1  # throttled within the window
    monkeypatch.setattr(error_monitor, "THROTTLE_SECONDS", 0)
    error_monitor._reset()
    for _ in range(3):
        await client.post("/__test/boom", json={})
        await error_monitor.drain()
    rows = await _rows(maker)
    assert len(rows) == 1 and rows[0].count == 4
    monkeypatch.setattr(error_monitor, "GLOBAL_WRITES_PER_MINUTE", 2)
    error_monitor._reset()
    assert [error_monitor.report("salla", error_type=f"t{i}") for i in range(5)].count(True) == 2


async def test_monitoring_failure_never_crashes(api, monkeypatch):
    client, maker, _, _ = api

    def broken(*a, **k):
        raise RuntimeError("monitor down")

    monkeypatch.setattr(error_monitor, "build_record", broken)
    assert error_monitor.report("server") is False
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-request-id")

    async def db_down(rec):
        raise RuntimeError("db")

    monkeypatch.undo()
    monkeypatch.setattr(error_monitor, "session_factory", None)
    monkeypatch.setattr(
        "src.db.session.async_session_factory", lambda: (_ for _ in ()).throw(RuntimeError("x"))
    )
    error_monitor._reset()
    assert error_monitor.report("zid", error_type="x") is True
    await error_monitor.drain()  # swallowed


async def test_integration_failures_are_captured(api):
    client, maker, _, _ = api
    from src.integrations.salla import client as salla
    from src.integrations.zid import client as zid

    class R:
        status_code = 401
        text = FAKE["bearer"]

        def json(self):
            return {}

    for mod in (salla, zid):
        with pytest.raises(Exception):
            mod._json(R(), "orders")
    rows = await _rows(maker)
    assert {r.source for r in rows} == {"salla", "zid"}
    assert all(r.error_type == "http_401" and _leaks(str(r.message)) == [] for r in rows)
