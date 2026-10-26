"""Regression tests for the verified items of the external audit review."""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.ai import rag
from src.automation.workflow_engine import WorkflowDefinition, WorkflowEngine, WorkflowStep
from src.core.state_manager import StateManager
from src.integrations.replay import parse_timestamp
from src.models import Base


# ------------------------------------------------------------ fix 1: KB cancel
async def test_cancelled_kb_index_leaves_sqlite_writable(tmp_path):
    db = tmp_path / "kb.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        for delay in [i * 0.007 for i in range(25)]:
            task = asyncio.create_task(rag.index_with_backoff(factory))
            await asyncio.sleep(delay)
            if task.cancel():
                with pytest.raises(asyncio.CancelledError):
                    await task
            # No write lock may survive the cancel (no gc.collect() here).
            probe = sqlite3.connect(db, timeout=1)
            try:
                probe.execute("BEGIN IMMEDIATE")
                probe.rollback()
            finally:
                probe.close()
    finally:
        await engine.dispose()


async def test_kb_index_retries_with_backoff_then_succeeds(monkeypatch):
    calls, sleeps = [], []

    async def flaky(session):
        calls.append(session)
        if len(calls) < 3:
            raise RuntimeError("db down")
        return 7

    async def fake_sleep(s):
        sleeps.append(s)

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def rollback(self):
            pass

    monkeypatch.setattr(rag, "index_default", flaky)
    assert await rag.index_with_backoff(_Session, sleep=fake_sleep) == 7
    assert len(calls) == 3
    assert sleeps == [rag._INDEX_BACKOFF_S, min(rag._INDEX_BACKOFF_S * 2, rag._INDEX_BACKOFF_CAP_S)]


# ------------------------------------------------------- fix 2: CLI components
def test_cli_components_get_a_session_factory_not_a_coroutine(monkeypatch):
    from src.db.session import async_session_factory
    from src.interfaces import cli

    for name in ("agent_registry", "model_provider", "prompt_engine", "context_manager",
                 "state_manager", "workflow_engine", "queue_worker", "scheduler", "trigger_engine"):
        monkeypatch.setattr(cli, name, None)
    cli.get_components()
    assert cli.agent_registry._db_session_factory is async_session_factory


# ------------------------------------------------- fix 3: workflow cancel works
async def test_cancel_workflow_stops_a_running_workflow():
    started = asyncio.Event()

    async def slow_agent(slug):
        started.set()
        await asyncio.sleep(30)

    registry = AsyncMock()
    registry.get_agent.side_effect = slow_agent
    engine = WorkflowEngine(registry, AsyncMock(), StateManager(), None)
    run = asyncio.create_task(engine.execute(
        WorkflowDefinition(steps=[WorkflowStep(id="one", agent_slug="slow")]), {}))
    await asyncio.wait_for(started.wait(), 5)
    (wid,) = list(engine._running_workflows)
    assert await engine.cancel_workflow(wid)
    result = await asyncio.wait_for(run, 5)  # returns, does not hang 30s or raise
    assert not result.success and result.error == "cancelled"
    assert engine.get_workflow_status(wid)["status"] == "cancelled"
    assert wid not in engine._running_workflows


# ------------------------------------------------ fix 4: replay offset parsing
@pytest.mark.parametrize("raw, hour", [
    ("2026-01-01T12:00:00.123-03:00", 15),
    ("2026-01-01T12:00:00.5+03:00", 9),
    ("2026-01-01 12:00:00.250Z", 12),
])
def test_replay_timestamp_keeps_offset_after_fraction(raw, hour):
    got = parse_timestamp(raw)
    assert got.astimezone(timezone.utc) == datetime(2026, 1, 1, hour, tzinfo=timezone.utc)


# ------------------------------------------- fix 5: portal legacy package names
def test_portal_shows_public_names_for_legacy_package_slugs():
    html = (Path(__file__).resolve().parents[1] / "src/web/templates/portal.html").read_text("utf-8")
    line = next(l for l in html.splitlines() if "const pkgNames" in l)
    for slug, name in (("radd", "البداية"), ("bay", "النمو"), ("tashgheel", "الشركات")):
        assert f"{slug}: '{name}'" in line
