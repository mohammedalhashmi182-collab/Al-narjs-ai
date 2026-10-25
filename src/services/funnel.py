"""First-party, privacy-conscious conversion-funnel events.

Stored: event name (allow-listed), timestamp, an anonymous session hash and a
few allow-listed properties (plan, lang, page, method). Never stored: message
text, names, phones, emails, raw IPs, user agents, tokens or payment data.

The session hash is HMAC(SECRET_KEY, ip|user-agent|UTC day), truncated, so it
rotates daily and cannot be reversed to an address. Do-Not-Track / Sec-GPC and
a refused cookie banner (``narjs_consent=denied``) disable tracking entirely.

``track`` never raises and never blocks the journey for long: any failure is
logged as one line without the payload.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

log = logging.getLogger(__name__)

FUNNEL_STEPS: tuple[str, ...] = (
    "landing_view",
    "ceo_consult_open",
    "ceo_problem_submitted",
    "ceo_plan_recommended",
    "portal_opened",
    "checkout_started",
    "payment_attempted",
    "payment_succeeded",
    "project_activated",
)
EVENTS = frozenset(FUNNEL_STEPS)
# Only these may arrive from the browser beacon; the rest are server-side.
CLIENT_EVENTS = frozenset({"landing_view", "ceo_consult_open"})

_SLUG = re.compile(r"^[a-z0-9_-]{1,32}$")
_PAGE = re.compile(r"^/[A-Za-z0-9/_-]{0,79}$")
_PROP_RULES: dict[str, re.Pattern] = {
    "plan": _SLUG,
    "method": _SLUG,
    "lang": re.compile(r"^(ar|en)$"),
    "page": _PAGE,
}
TRACK_TIMEOUT_SECONDS = 2.0


def clean_props(props: dict | None) -> dict[str, str]:
    """Keep only allow-listed keys whose values match their pattern."""
    out: dict[str, str] = {}
    if not isinstance(props, dict):
        return out
    for key, rule in _PROP_RULES.items():
        value = props.get(key)
        if isinstance(value, str):
            value = value.strip().lower() if key != "page" else value.strip()
            if rule.fullmatch(value):
                out[key] = value
    return out


def tracking_allowed(request: Any) -> bool:
    if request is None:
        return True
    try:
        headers = request.headers
        if headers.get("dnt") == "1" or headers.get("sec-gpc") == "1":
            return False
        if request.cookies.get("narjs_consent") == "denied":
            return False
    except Exception:  # noqa: BLE001
        return False
    return True


def session_hash(request: Any) -> str | None:
    """Salted, daily-rotating anonymous id. The IP itself is never returned or stored."""
    if request is None:
        return None
    try:
        from src.config.settings import settings
        from src.utils.net import client_ip

        ua = (request.headers.get("user-agent") or "")[:200]
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        material = f"{client_ip(request)}|{ua}|{day}".encode()
        key = f"funnel:{settings.secret_key}".encode()
        return hmac.new(key, material, hashlib.sha256).hexdigest()[:24]
    except Exception:  # noqa: BLE001
        return None


# Tests point this at an isolated engine; production uses the app database.
session_factory: Any = None


async def _store(event: str, sid: str | None, props: dict) -> None:
    from src.db.session import async_session_factory
    from src.models.ops import FunnelEvent

    async with (session_factory or async_session_factory)() as session:
        session.add(FunnelEvent(event=event, session_hash=sid, props=props))
        await session.commit()


async def track(event: str, request: Any = None, props: dict | None = None) -> bool:
    """Record one funnel event. Returns True when stored. Never raises."""
    try:
        if event not in EVENTS or not tracking_allowed(request):
            return False
        await asyncio.wait_for(
            _store(event, session_hash(request), clean_props(props)), TRACK_TIMEOUT_SECONDS
        )
        return True
    except Exception as exc:  # noqa: BLE001 - analytics must never break the journey
        log.warning("funnel event %s not stored (%s)", event, type(exc).__name__)
        return False


async def funnel_report(session, days: int = 30) -> dict:
    """Counts per step (events and distinct sessions) and step-to-step conversion."""
    from sqlalchemy import func, select

    from src.models.ops import FunnelEvent

    days = max(1, min(int(days), 365))
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        await session.execute(
            select(
                FunnelEvent.event,
                func.count(FunnelEvent.id),
                func.count(func.distinct(FunnelEvent.session_hash)),
            )
            .where(FunnelEvent.created_at >= since)
            .group_by(FunnelEvent.event)
        )
    ).all()
    by_event = {r[0]: (int(r[1]), int(r[2])) for r in rows}
    steps = []
    prev = None
    for name in FUNNEL_STEPS:
        count, sessions = by_event.get(name, (0, 0))
        conv = None
        if prev is not None and prev > 0:
            conv = round(100.0 * count / prev, 1)
        steps.append(
            {
                "event": name,
                "count": count,
                "sessions": sessions,
                "conversion_from_previous_pct": conv,
            }
        )
        prev = count
    first = by_event.get(FUNNEL_STEPS[0], (0, 0))[0]
    last = by_event.get(FUNNEL_STEPS[-1], (0, 0))[0]
    return {
        "days": days,
        "steps": steps,
        "overall_pct": round(100.0 * last / first, 1) if first else None,
    }
