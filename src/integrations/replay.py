"""Webhook timestamp window.

Salla retries a delivery a few times, about five minutes apart, so the default
window is 15 minutes (``STORE_WEBHOOK_MAX_AGE_SECONDS``). A missing, stale, or
far-future timestamp is rejected.

Salla's ``created_at`` sits inside the HMAC, so the window is bound to the
signed body. Zid's signed mode uses the same body field and ignores an unsigned
timestamp header. Zid's unsigned mode (Basic or static header) accepts
``X-Zid-Timestamp`` or a body field; that header is not bound to the body, so
the window only stops a later replay of a captured request.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from src.integrations.config import env

_SKEW_SECONDS = 60
_DEFAULT_WINDOW = 900


def max_age_seconds() -> int:
    raw = env("STORE_WEBHOOK_MAX_AGE_SECONDS")
    if not raw:
        return _DEFAULT_WINDOW
    try:
        window = int(raw)
    except ValueError:
        return _DEFAULT_WINDOW
    if window < 30 or window > 86_400:
        return _DEFAULT_WINDOW
    return window


def parse_timestamp(value: object) -> Optional[datetime]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        n = float(value)
        if n > 1_000_000_000_000:
            n /= 1000.0
        if n < 1_000_000_000:
            return None
        try:
            return datetime.fromtimestamp(n, UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.isdigit():
        return parse_timestamp(int(text))
    text = text.replace("Z", "+00:00")
    if "." in text:
        head, tail = text.split(".", 1)
        text = head + (("+" + tail.split("+", 1)[1]) if "+" in tail else "")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def within_window(moment: Optional[datetime], *, now: Optional[datetime] = None) -> bool:
    if moment is None:
        return False
    now = now or datetime.now(UTC)
    delta = (now - moment).total_seconds()
    return -_SKEW_SECONDS <= delta <= max_age_seconds()


def salla_fresh(payload: dict, *, now: Optional[datetime] = None) -> bool:
    """``created_at`` from the signed Salla body. No unsigned header is consulted."""
    return within_window(parse_timestamp(payload.get("created_at")), now=now)


def zid_fresh(headers, payload: dict, *, now: Optional[datetime] = None) -> bool:
    signed = ((headers.get("x-zid-signature") if headers else None) or "").strip()
    if signed:
        moment = parse_timestamp(payload.get("created_at")) or parse_timestamp(payload.get("timestamp"))
        return within_window(moment, now=now)
    moment = parse_timestamp(headers.get("x-zid-timestamp") if headers else None)
    if moment is None:
        moment = parse_timestamp(payload.get("created_at")) or parse_timestamp(payload.get("timestamp"))
    return within_window(moment, now=now)
