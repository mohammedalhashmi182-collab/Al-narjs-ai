"""Scheduler job registration off the boot path (Postgres) and safe on SQLite."""
from __future__ import annotations

import asyncio
import inspect
import threading

import pytest

from src.automation import scheduler as sched_mod
from src.automation.scheduler import AgentScheduler


class _FakeAPS:
    def __init__(self):
        self.jobs: dict[str, object] = {}
        self.threads: list[str] = []

    def start(self):
        pass

    def shutdown(self, wait=True):
        pass

    def add_job(self, fn, trigger=None, id=None, replace_existing=False, **kw):
        self.threads.append(threading.current_thread().name)
        if id in self.jobs and not replace_existing:
            raise RuntimeError("duplicate")
        self.jobs[id] = trigger

    def remove_job(self, job_id):
        self.threads.append(threading.current_thread().name)
        del self.jobs[job_id]

    def get_jobs(self):
        return list(self.jobs)


class _Sched:
    id = "s1"
    cron_expression = "*/5 * * * *"
    interval_seconds = None
    run_once_at = None
    timezone = "UTC"


def _make(offload: bool) -> AgentScheduler:
    s = AgentScheduler.__new__(AgentScheduler)
    s.scheduler = _FakeAPS()
    s._job_callbacks = {}
    s._running = False
    s.offload_jobstore = offload
    s.session_factory = None
    return s


async def test_offloaded_jobstore_writes_run_off_the_event_loop():
    s = _make(offload=True)
    await s._jobstore(s._add_schedule_job, _Sched())
    await s._jobstore(s._remove_job_quiet, "s1")
    assert s.scheduler.threads and all(t != "MainThread" for t in s.scheduler.threads)


async def test_blocking_mode_stays_inline():
    s = _make(offload=False)
    await s._jobstore(s._add_schedule_job, _Sched())
    assert s.scheduler.threads == [threading.current_thread().name]


async def test_re_registration_never_duplicates():
    s = _make(offload=True)
    for _ in range(3):
        await s._jobstore(s._add_schedule_job, _Sched())
    assert s.job_count() == 1


async def test_remove_missing_job_is_quiet():
    s = _make(offload=True)
    await s._jobstore(s._remove_job_quiet, "nope")


async def test_start_can_skip_loading_schedules(monkeypatch):
    s = _make(offload=True)
    called = []

    async def fake_load(threaded=False):
        called.append(threaded)

    monkeypatch.setattr(s, "_load_schedules_from_db", fake_load)
    await s.start(load_schedules=False)
    assert s._running and called == []


def test_lifespan_registers_jobs_in_background_and_cancels_on_shutdown():
    from src import main

    src = inspect.getsource(main.lifespan)
    assert "scheduler.offload_jobstore = background_sync" in src
    assert "load_schedules=not background_sync" in src
    assert 'create_task(_register_scheduler_jobs(threaded=True)' in src
    assert "scheduler_task.cancel()" in src
    # SQLite / tests keep the blocking path
    assert "await _register_scheduler_jobs(threaded=False)" in src


def test_sqlite_boot_registers_jobs_before_serving():
    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
        assert app.state.scheduler.offload_jobstore is False
        assert app.state.scheduler.job_count() >= 1
