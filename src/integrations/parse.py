"""Pull non-PII fields out of platform payloads. Email, phone and address are ignored."""

from __future__ import annotations

from typing import Optional


def text(value: object) -> str:
    if isinstance(value, dict):
        for key in ("ar", "en"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item.strip()
        return ""
    if isinstance(value, str):
        return value.strip()
    return ""


def ident(value: object) -> Optional[str]:
    if value is None or isinstance(value, bool):
        return None
    raw = str(value).strip()
    if not raw or raw.lower() == "none":
        return None
    return raw[:64]


def amount(value: object) -> Optional[str]:
    if isinstance(value, dict):
        value = value.get("amount")
    if value is None or value == "":
        return None
    return str(value)[:32]


def number(value: object) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
