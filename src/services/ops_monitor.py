"""Production monitoring: deep health checks, the uptime self-check job and
owner alerts (Telegram War Room) for errors and webhook failures.

Every check reports booleans, latencies and short reason strings only. No
credential value, token or header is ever placed in a result or an alert.
Alerts are throttled per key so a flapping dependency cannot flood the owner.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text

from src.config.settings import settings

log = logging.getLogger(__name__)

UPTIME_SCHEDULE_NAME = "ops-uptime-self-check"
UPTIME_INTERVAL_SECONDS = 300
ALERT_COOLDOWN_SECONDS = 1800
EXTERNAL_TIMEOUT = 6.0

_last_alert: dict[str, float] = {}


def _reset_throttle() -> None:
    _last_alert.clear()


async def alert_owner(key: str, message: str, *, cooldown: int = ALERT_COOLDOWN_SECONDS) -> bool:
    """Push one alert to the owner's Telegram chat, at most once per ``cooldown`` per key.

    Returns True when an alert was attempted. Never raises.
    """
    now = time.monotonic()
    last = _last_alert.get(key)
    if last is not None and now - last < cooldown:
        return False
    _last_alert[key] = now
    try:
        from src.services import telegram_sender

        await telegram_sender.send_owner_alert(message[:3500])
    except Exception:  # noqa: BLE001 - alerting must never break the caller
        log.warning("owner alert %s could not be delivered", key)
    return True


# --------------------------------------------------------------------------- checks

async def check_db(session_factory) -> dict:
    started = time.perf_counter()
    try:
        async with session_factory() as s:
            await s.execute(text("SELECT 1"))
        return {"ok": True, "latency_ms": round((time.perf_counter() - started) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}


async def _probe(url: str) -> dict:
    """GET a public endpoint (no credentials) and report reachability."""
    import httpx

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=EXTERNAL_TIMEOUT) as c:
            r = await c.get(url)
        return {"ok": r.status_code < 500, "status_code": r.status_code,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__}


def configured_externals() -> dict[str, bool]:
    """Which external services are configured (booleans only)."""
    return {
        "telegram": bool(getattr(settings, "telegram_token", None)),
        "whatsapp": bool(settings.whatsapp_token and settings.whatsapp_phone_number_id),
        "moyasar": bool(getattr(settings, "moyasar_api_secret", None)),
        "gemini": bool(getattr(settings, "gemini_api_key", None)),
    }


EXTERNAL_PROBES = {
    "telegram": "https://api.telegram.org",
    "whatsapp": "https://graph.facebook.com",
    "moyasar": "https://api.moyasar.com",
    "gemini": "https://generativelanguage.googleapis.com",
}


async def check_external(probe=None) -> dict:
    """Reachability of each configured provider's public API host."""
    probe = probe or _probe
    out = {}
    for name, configured in configured_externals().items():
        if not configured:
            out[name] = {"ok": None, "configured": False}
            continue
        out[name] = {"configured": True, **(await probe(EXTERNAL_PROBES[name]))}
    return out


async def deep_health(session_factory, probe=None) -> dict:
    db = await check_db(session_factory)
    external = await check_external(probe)
    degraded = [k for k, v in external.items() if v.get("ok") is False]
    status = "unhealthy" if not db["ok"] else ("degraded" if degraded else "healthy")
    return {
        "status": status,
        "checked_at": datetime.now(UTC).isoformat(),
        "db": db,
        "external": external,
        "degraded": degraded,
    }


# --------------------------------------------------------------------------- uptime job

async def run_uptime_check(session_factory, *, base_url: str | None = None, probe=None) -> dict:
    """Self-check: deep health + the public site answering. Alerts the owner on failure."""
    probe = probe or _probe
    result = await deep_health(session_factory, probe)
    base = (base_url or settings.public_base_url or "").rstrip("/")
    if base:
        result["site"] = await probe(f"{base}/health")
        if not result["site"].get("ok"):
            result["status"] = "unhealthy"
    if result["status"] != "healthy":
        parts = []
        if not result["db"]["ok"]:
            parts.append("قاعدة البيانات لا تستجيب")
        if result.get("site") and not result["site"].get("ok"):
            parts.append("الموقع لا يرد على /health")
        if result["degraded"]:
            parts.append("خدمات خارجية: " + "، ".join(result["degraded"]))
        await alert_owner(f"uptime:{result['status']}",
                          "🚨 فحص التشغيل: " + " · ".join(parts or [result["status"]])
                          + "\nراجع docs/runbooks.md")
    return result


async def ensure_uptime_schedule(scheduler) -> None:
    """Register the 5-minute uptime self-check with the app scheduler (once)."""
    from src.automation.scheduler import ScheduleConfig
    from src.models import Schedule

    try:
        async with scheduler.session_factory() as session:
            exists = (await session.execute(
                select(Schedule).where(Schedule.name == UPTIME_SCHEDULE_NAME))).scalar_one_or_none()
        if exists is not None:
            return
        await scheduler.add_schedule(ScheduleConfig(
            name=UPTIME_SCHEDULE_NAME, target_type="ops_uptime", target_id=uuid4(),
            interval_seconds=UPTIME_INTERVAL_SECONDS, timezone="Asia/Riyadh",
        ))
    except Exception as e:  # pragma: no cover - defensive on startup
        log.warning("Could not register uptime schedule: %s", e)


# --------------------------------------------------------------------------- webhooks / errors

def webhook_name(path: str) -> str:
    rest = path[len("/webhooks/"):] if path.startswith("/webhooks/") else path
    return (rest.split("/", 1)[0] or "unknown")[:40]


async def on_webhook_failure(path: str, status: Any, detail: str = "") -> None:
    name = webhook_name(path)
    hint = {"moyasar": "فشل webhook الدفع (ميسّر)", "paypal": "فشل webhook الدفع (PayPal)",
            "whatsapp": "فشل webhook واتساب", "telegram": "فشل webhook تيليجرام"}.get(name, f"فشل webhook {name}")
    await alert_owner(f"webhook:{name}:{status}",
                      f"⚠️ {hint} — الحالة {status}. {detail[:200]}\nراجع docs/runbooks.md")


async def on_unhandled_error(path: str, exc: BaseException) -> None:
    await alert_owner(f"error:{path[:60]}:{type(exc).__name__}",
                      f"🔥 خطأ غير معالج في {path[:120]}: {type(exc).__name__}")


class OpsAlertMiddleware:
    """Pure ASGI middleware: alerts on 5xx/exceptions for webhooks and 5xx elsewhere.

    Does not read or alter request bodies, so webhook signature checks are unaffected.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path") or ""
        status_box: dict = {}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_box["status"] = message.get("status", 0)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            if path.startswith("/webhooks/"):
                await on_webhook_failure(path, "exception", type(exc).__name__)
            else:
                await on_unhandled_error(path, exc)
            raise
        status = status_box.get("status", 0)
        if status >= 500:
            if path.startswith("/webhooks/"):
                await on_webhook_failure(path, status)
            elif not path.startswith("/health"):
                await alert_owner(f"http5xx:{path[:60]}", f"🔥 {status} على {path[:120]}")
