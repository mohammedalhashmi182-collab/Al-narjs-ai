"""Public status snapshot for /status and /api/status.

Lightweight and cached. The payload names four components and a roll-up.
It never includes credentials, exception text, hostnames, or row data.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from src.version import __version__

TTL_SECONDS = 30.0
STATUS_HOST = "status.karmaai.online"

_RANK = {"operational": 0, "degraded": 1, "outage": 2}


def status_host_home(host: str, path: str) -> str | None:
    """Root of the status hostname opens the status page. Other paths stay put."""
    if (host or "").rstrip(".").lower() != STATUS_HOST:
        return None
    if path in ("", "/"):
        return "/ar/status"
    if path in ("/ar", "/ar/"):
        return "/ar/status"
    if path in ("/en", "/en/"):
        return "/en/status"
    return None


def _overall(components: dict[str, dict[str, Any]]) -> str:
    worst = "operational"
    for row in components.values():
        status = str(row.get("status") or "degraded")
        if _RANK.get(status, 1) > _RANK[worst]:
            worst = status if status in _RANK else "degraded"
    return worst


async def _portal(app: Any) -> dict[str, str]:
    factory = getattr(app.state, "session_factory", None)
    if factory is None:
        return {"status": "outage"}
    try:
        async with factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - the public body stays a status word
        return {"status": "outage"}
    return {"status": "operational"}


async def _agents(app: Any) -> dict[str, Any]:
    from src.services import catalog

    registry = getattr(app.state, "agent_registry", None)
    if registry is None:
        return {"status": "degraded", "count": catalog.AGENT_COUNT}
    try:
        listed = await registry.list_agents()
        ready = len(listed) > 0
    except Exception:  # noqa: BLE001 - no exception text on the public payload
        ready = False
    return {
        "status": "operational" if ready else "degraded",
        "count": catalog.AGENT_COUNT,
    }


async def build(app: Any) -> dict[str, Any]:
    """One uncached read. Callers should use :func:`snapshot`."""
    components = {
        "site": {"status": "operational"},
        "health": {"status": "operational"},
        "portal": await _portal(app),
        "agents": await _agents(app),
    }
    return {
        "status": _overall(components),
        "version": __version__,
        "checked_at": datetime.now(UTC).isoformat(),
        "components": components,
    }


async def snapshot(app: Any) -> dict[str, Any]:
    """Cached public status. A failed read is not cached."""
    now = time.monotonic()
    cached = getattr(app.state, "public_status_cache", None)
    if isinstance(cached, dict) and cached.get("at", 0) > now - TTL_SECONDS:
        payload = cached.get("payload")
        if isinstance(payload, dict):
            return payload
    payload = await build(app)
    if payload.get("status") != "outage":
        app.state.public_status_cache = {"at": now, "payload": payload}
    return payload
