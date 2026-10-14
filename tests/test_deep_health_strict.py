"""Deep health: 400/404 from a dependency is unhealthy; a scheduler with missing
job registrations is degraded and alerts the owner. No network: probes are mocked."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import Schedule
from src.services import ops_monitor


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def alerts(monkeypatch):
    sent = []

    async def _fake(text):
        sent.append(text)
        return {"ok": True}

    from src.services import telegram_sender

    monkeypatch.setattr(telegram_sender, "send_owner_alert", _fake)
    ops_monitor._reset_throttle()
    yield sent
    ops_monitor._reset_throttle()


@pytest.fixture(autouse=True)
def _no_app_scheduler(monkeypatch):
    monkeypatch.setattr(ops_monitor, "_app_scheduler", lambda: None)


class _Sched:
    def __init__(self, jobs, running=True):
        self._jobs, self._running = jobs, running

    def job_count(self):
        return self._jobs


@pytest.mark.parametrize("code", [400, 401, 403, 404])
async def test_4xx_from_dependency_is_unhealthy(maker, monkeypatch, code):
    calls = []

    async def fake(url, headers=None):
        calls.append(url)
        return {"ok": True, "status_code": code}  # old semantics said ok for <500

    monkeypatch.setattr(ops_monitor, "_probe", fake)
    monkeypatch.setattr(ops_monitor, "configured_externals",
                        lambda: {"telegram": False, "whatsapp": True, "moyasar": False, "gemini": True})
    r = await ops_monitor.deep_health(maker)
    assert r["status"] == "degraded"
    assert set(r["degraded"]) == {"whatsapp", "gemini"}
    assert r["external"]["whatsapp"]["ok"] is False
    assert "token" not in str(r).lower() and "bearer" not in str(r).lower()


def test_status_ok_rule():
    assert ops_monitor._status_ok(200) and ops_monitor._status_ok(302)
    assert not any(ops_monitor._status_ok(c) for c in (400, 404, 500, 503))


async def test_custom_probe_404_is_degraded(maker, monkeypatch):
    async def p404(url):
        return {"ok": True, "status_code": 404}

    monkeypatch.setattr(ops_monitor, "configured_externals", lambda: {"gemini": True})
    r = await ops_monitor.deep_health(maker, p404)
    assert r["degraded"] == ["gemini"]


async def test_scheduler_missing_jobs_is_degraded_and_alerts(maker, monkeypatch, alerts):
    monkeypatch.setattr(ops_monitor, "configured_externals", lambda: {})
    r = await ops_monitor.run_uptime_check(maker, base_url="", scheduler=_Sched(jobs=0))
    assert r["status"] == "degraded" and "scheduler" in r["degraded"]
    assert r["scheduler"]["missing"] and len(alerts) == 1 and "المجدول" in alerts[0]


async def test_scheduler_all_registered_is_healthy(maker, monkeypatch):
    monkeypatch.setattr(ops_monitor, "configured_externals", lambda: {})
    names = ops_monitor.expected_schedules()
    async with maker() as s:
        for n in names:
            s.add(Schedule(name=n, target_type="x", target_id=uuid4()))
        await s.commit()
    r = await ops_monitor.deep_health(maker, scheduler=_Sched(jobs=len(names) + 3))
    assert r["status"] == "healthy" and r["scheduler"]["ok"] is True
    r = await ops_monitor.deep_health(maker, scheduler=_Sched(jobs=len(names), running=False))
    assert r["status"] == "degraded"
