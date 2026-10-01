"""Regression guards for the outreach wave contract and channel endpoints.

``/api/company/radar`` used to read ``wave["whatsapp"]`` while ``build_wave``
returns ``"telegram"``, so the endpoint raised KeyError and 500'd in production
with no test covering it. The wave contract is now asserted statically (every
key the router subscripts must exist in ``build_wave``'s return value) and
functionally (the owner endpoints must answer 200).
"""

from __future__ import annotations

import ast
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base

REPO_ROOT = Path(__file__).resolve().parents[1]


async def _make_engine():
    from src import models  # noqa: F401  (registers every table on Base.metadata)

    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def maker():
    engine, maker = await _make_engine()
    yield maker
    await engine.dispose()


@pytest.fixture
async def api(maker):
    from src.main import app

    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"narjis_owner": make_session_token()},
    ) as client:
        yield client


def _wave_keys_subscripted() -> set[str]:
    """Wave keys company_routes subscripts, read from the source AST."""
    tree = ast.parse((REPO_ROOT / "src" / "interfaces" / "company_routes.py").read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "wave"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            keys.add(node.slice.value)
    return keys


def _build_wave_return_keys() -> set[str]:
    """Keys ``build_wave`` actually returns, read from the source AST."""
    tree = ast.parse((REPO_ROOT / "src" / "services" / "revenue_radar.py").read_text(encoding="utf-8"))
    fn = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "build_wave"
    )
    keys: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            for k in node.value.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.add(k.value)
    return keys


class TestWaveContract:
    def test_contract_probe_is_not_vacuous(self):
        read = _wave_keys_subscripted()
        returned = _build_wave_return_keys()
        assert {"metrics", "wave_size"} <= returned
        assert "telegram" in read, "no channel key read — the AST probe needs updating"

    def test_radar_reads_only_keys_build_wave_returns(self):
        missing = _wave_keys_subscripted() - _build_wave_return_keys()
        assert not missing, f"/api/company/radar reads keys build_wave never returns: {sorted(missing)}"


class TestOwnerChannelEndpoints:
    async def test_radar_returns_200(self, api):
        r = await api.get("/api/company/radar")
        assert r.status_code == 200
        body = r.json()
        for key in ("metrics", "wave_size", "telegram", "conversation"):
            assert key in body, key

    async def test_queue_returns_200(self, api):
        r = await api.get("/api/company/queue")
        assert r.status_code == 200
        body = r.json()
        assert "sender" in body
        assert isinstance(body["outbox"], list)

    async def test_endpoints_require_owner(self, maker):
        from src.main import app

        app.state.session_factory = maker
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for path in ("/api/company/radar", "/api/company/queue"):
                r = await client.get(path)
                assert r.status_code in (401, 403), path


class TestWhatsappChannelEndpoints:
    async def test_health_is_public_and_secret_free(self, api):
        r = await api.get("/webhooks/whatsapp/health")
        assert r.status_code == 200
        assert "Authorization" not in r.text
        assert "Bearer" not in r.text

    async def test_post_without_signature_is_rejected(self, api):
        r = await api.post("/webhooks/whatsapp", json={"entry": []})
        assert r.status_code == 403

    def test_sender_reports_meta_cloud_only(self):
        from src.services import whatsapp_sender as ws

        status = ws.send_status()
        assert status["gateway"] == "meta_cloud"
        assert "dialog" not in status
        assert status["token_configured"] in (True, False)