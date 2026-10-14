"""Fast startup: agents are served from YAML immediately; DB sync runs in background."""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.agent_registry import AgentRegistry
from src.db.session import Base
from src.models import Agent


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_prime_cache_serves_agents_without_db(maker):
    reg = AgentRegistry(maker)
    n = await reg.prime_cache_from_yaml()
    assert n >= 30
    assert await reg.get_agent("customer_service") is not None
    async with maker() as s:
        assert (await s.execute(select(func.count(Agent.id)))).scalar() == 0  # nothing written yet


async def test_background_sync_does_not_block_and_completes(maker, monkeypatch):
    reg = AgentRegistry(maker)
    await reg.prime_cache_from_yaml()
    gate = asyncio.Event()
    real = reg.upsert_agent

    async def slow_upsert(defn):
        await gate.wait()
        return await real(defn)

    monkeypatch.setattr(reg, "upsert_agent", slow_upsert)
    task = reg.start_background_sync()
    await asyncio.sleep(0)
    assert not task.done()  # startup continues while the sync is pending
    gate.set()
    await asyncio.wait_for(task, timeout=30)
    async with maker() as s:
        assert (await s.execute(select(func.count(Agent.id)))).scalar() >= 30


async def test_background_sync_errors_never_raise(maker, monkeypatch):
    reg = AgentRegistry(maker)

    async def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(reg, "sync_base_agents", boom)
    await asyncio.wait_for(reg.start_background_sync(), timeout=5)  # swallowed + logged


async def test_stop_background_sync_cancels_cleanly(maker, monkeypatch):
    reg = AgentRegistry(maker)

    async def forever():
        await asyncio.sleep(3600)

    monkeypatch.setattr(reg, "sync_base_agents", forever)
    task = reg.start_background_sync()
    await reg.stop_background_sync()
    assert task.done()


def test_app_starts_with_agents_primed_from_yaml(monkeypatch):
    from fastapi.testclient import TestClient

    from src.main import app

    monkeypatch.delenv("SYNC_AGENTS_BLOCKING", raising=False)
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
        assert app.state.agent_registry._cache  # primed from YAML at startup


def test_lifespan_runs_agent_sync_in_background_on_postgres():
    import inspect

    from src import main

    src = inspect.getsource(main.lifespan)
    assert "prime_cache_from_yaml" in src and "start_background_sync" in src
    # the background start comes after the rest of startup (just before yield)
    assert src.index("start_background_sync") > src.index("seed_owner_faq")
    assert "stop_background_sync" in src
