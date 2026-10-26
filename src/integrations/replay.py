"""Webhook timestamp window.

Salla retries a delivery a few times, about five minutes apart, so the default
window is 15 minutes (``STORE_WEBHOOK_MAX_AGE_SECONDS``). A missing, stale, or
far-future timestamp is rejected.

Salla's ``created_at`` sits inside the HMAC, so the window is bound to the
signed body. Zid's signed mode uses the same body field and ignores an unsigned
timestamp header. Zid's unsigned mode (Basic or static header) checks only
``X-Zid-Timestamp`` when present (body ``created_at`` is the order date there);
with no header it relies on the raw-body dedupe. An authenticated Zid uninstall
skips the window so tokens are always cleared.
"""

from __future__ import annotations

import re
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


_FRACTION = re.compile(r"([Tt ]\d{2}:\d{2}:\d{2})\.\d+")


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
    # Drop fractional seconds only; keep the zone offset whatever its sign
    # (the old split kept "+hh:mm" but silently lost "-hh:mm").
    text = _FRACTION.sub(r"\1", text, count=1)
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
    # Basic-auth deliveries: the body's created_at is the order/product date,
    # not the delivery time, so it is never used here. A missing timestamp is
    # allowed; exact replays are dropped by the raw-body dedupe (claim_event).
    raw_header = (headers.get("x-zid-timestamp") if headers else None) or ""
    if not str(raw_header).strip():
        return True
    return within_window(parse_timestamp(raw_header), now=now)
