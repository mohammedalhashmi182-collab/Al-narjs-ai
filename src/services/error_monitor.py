"""Central exception tracking: one deduplicated, scrubbed row per failure kind.

Captures uncaught server exceptions (via OpsAlertMiddleware) and important
integration failures (Salla, Zid, Moyasar, WhatsApp, Telegram, Gemini/LLM).
Stored per row: source, route template, error type, a scrubbed and truncated
message, the last request id, environment, count, first/last seen.
Never stored: request bodies, headers, tokens, card data, customer messages.

Dedupe: one row per fingerprint (source|route|type), its counter bumped.
Throttle: at most one DB write per fingerprint per THROTTLE_SECONDS, and a
global cap per minute, so an outage cannot flood the database.
``report`` never raises and never awaits the database in the caller's path.
"""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import logging
import re
import time
from datetime import UTC, datetime
from typing import Any

log = logging.getLogger(__name__)

THROTTLE_SECONDS = 60
GLOBAL_WRITES_PER_MINUTE = 60
MESSAGE_MAX = 300
SOURCES = frozenset(
    {
        "server",
        "webhook",
        "salla",
        "zid",
        "moyasar",
        "paypal",
        "whatsapp",
        "telegram",
        "gemini",
        "llm",
    }
)

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "narjs_request_id", default=None
)

# Tests point this at an isolated engine; production uses the app database.
session_factory: Any = None

_REDACT: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"(?i)\b(bearer|basic|token)\s+[A-Za-z0-9._~+/=-]{6,}"), r"\1 [REDACTED]"),
    (
        re.compile(
            r"(?i)((?:api[_-]?key|secret|password|passwd|token|authorization|access[_-]?token|"
            r"refresh[_-]?token|client[_-]?secret|cookie|session|signature|cvc|cvv)\s*[\"']?\s*[:=]\s*)"
            r"[\"']?[^\s\"',;&}]+"
        ),
        r"\1[REDACTED]",
    ),
    (re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"), "[JWT]"),
    (re.compile(r"\b(?:sk|pk|rk)[-_](?:live|test|proj)?[-_]?[A-Za-z0-9_-]{8,}"), "[KEY]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"), "[KEY]"),
    (re.compile(r"\bEA[A-Za-z0-9]{20,}"), "[KEY]"),
    (re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{20,}"), "[KEY]"),  # Telegram bot token
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[NUMBER]"),  # card-like
    (re.compile(r"\+?\d[\d ()-]{6,}\d"), "[NUMBER]"),  # phones / long ids
    (re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"), "[TOKEN]"),  # long opaque strings
)


def scrub(text: Any, limit: int = MESSAGE_MAX) -> str:
    """Redact secrets, contacts and numbers; drop non-ASCII prose (customer text); truncate."""
    try:
        s = str(text or "")
    except Exception:  # noqa: BLE001
        return ""
    s = s[: limit * 4]
    for pattern, repl in _REDACT:
        s = pattern.sub(repl, s)
    # Arabic (or any non-ASCII) runs are almost always customer content: drop them.
    s = re.sub(r"[^\x20-\x7E]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


_last_write: dict[str, float] = {}
_window: list[float] = []
_pending: set[asyncio.Task] = set()


def _reset() -> None:
    _last_write.clear()
    _window.clear()


def _allow(fp: str) -> bool:
    now = time.monotonic()
    last = _last_write.get(fp)
    if last is not None and now - last < THROTTLE_SECONDS:
        return False
    while _window and now - _window[0] > 60:
        _window.pop(0)
    if len(_window) >= GLOBAL_WRITES_PER_MINUTE:
        return False
    _last_write[fp] = now
    _window.append(now)
    if len(_last_write) > 2000:
        _last_write.clear()
    return True


async def _persist(rec: dict) -> None:
    try:
        from sqlalchemy import update
        from sqlalchemy.exc import IntegrityError

        from src.db.session import async_session_factory
        from src.models.ops import ErrorEvent

        bump = (
            update(ErrorEvent)
            .where(ErrorEvent.fingerprint == rec["fingerprint"])
            .values(
                count=ErrorEvent.count + 1,
                last_seen=datetime.now(UTC),
                message=rec["message"],
                last_request_id=rec["last_request_id"],
            )
        )
        async with (session_factory or async_session_factory)() as session:
            # Atomic counter bump; insert on first sight (a racing insert falls back to bump).
            if (await session.execute(bump)).rowcount == 0:
                try:
                    session.add(ErrorEvent(**rec))
                    await session.commit()
                    return
                except IntegrityError:
                    await session.rollback()
                    await session.execute(bump)
            await session.commit()
    except Exception as exc:  # noqa: BLE001 - monitoring must never crash anything
        log.warning("error event not stored (%s)", type(exc).__name__)


def build_record(
    source: str,
    exc: BaseException | None = None,
    *,
    error_type: str | None = None,
    message: Any = None,
    route: str | None = None,
    request_id: str | None = None,
) -> dict:
    from src.config.settings import settings

    src_name = source if source in SOURCES else "server"
    etype = (error_type or (type(exc).__name__ if exc is not None else "error"))[:80]
    etype = re.sub(r"[^A-Za-z0-9_.:-]", "_", etype)
    route_s = (route or "")[:160]
    fp = hashlib.sha256(f"{src_name}|{route_s}|{etype}".encode()).hexdigest()
    raw = message if message is not None else (exc if exc is not None else "")
    rid = request_id or request_id_var.get()
    return {
        "fingerprint": fp,
        "source": src_name,
        "route": route_s or None,
        "error_type": etype,
        "message": scrub(raw) or None,
        "last_request_id": rid if rid and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", rid) else None,
        "environment": re.sub(
            r"[^a-z0-9_-]", "", str(getattr(settings, "environment", "") or "").lower()
        )[:20]
        or None,
    }


def report(source: str, exc: BaseException | None = None, **kw: Any) -> bool:
    """Record one failure in the background. Safe from sync or async code. Never raises."""
    try:
        rec = build_record(source, exc, **kw)
        if not _allow(rec["fingerprint"]):
            return False
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False  # no loop (sync script): the log line is enough
        task = loop.create_task(_persist(rec))
        _pending.add(task)
        task.add_done_callback(_pending.discard)
        log.warning(
            "error captured source=%s type=%s route=%s",
            rec["source"],
            rec["error_type"],
            rec["route"],
        )
        return True
    except Exception:  # noqa: BLE001
        return False


async def drain() -> None:
    """Wait for queued writes (tests and shutdown)."""
    if _pending:
        await asyncio.gather(*list(_pending), return_exceptions=True)


async def summary(session, limit: int = 50) -> dict:
    from sqlalchemy import func, select

    from src.models.ops import ErrorEvent

    limit = max(1, min(int(limit), 200))
    rows = (
        (
            await session.execute(
                select(ErrorEvent).order_by(ErrorEvent.last_seen.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    by_source = dict(
        (
            await session.execute(
                select(ErrorEvent.source, func.sum(ErrorEvent.count)).group_by(ErrorEvent.source)
            )
        ).all()
    )
    return {
        "by_source": {k: int(v or 0) for k, v in by_source.items()},
        "errors": [
            {
                "source": r.source,
                "route": r.route,
                "error_type": r.error_type,
                "message": r.message,
                "count": r.count,
                "last_request_id": r.last_request_id,
                "environment": r.environment,
                "first_seen": r.first_seen.isoformat() if r.first_seen else None,
                "last_seen": r.last_seen.isoformat() if r.last_seen else None,
            }
            for r in rows
        ],
    }
