"""Client address shared by rate limits.

Cloudflare sets ``CF-Connecting-IP`` to the visitor, and that value wins.
Otherwise ``TRUSTED_PROXY_HOPS`` is how many reverse proxies append
``X-Forwarded-For`` before the app (Render is 1). The client is that many
hops from the right. A hop count of 0, or a header shorter than the hop
count, uses the direct peer. The left-most forwarded value is never trusted.
"""

from __future__ import annotations

import os


def trusted_hops() -> int:
    raw = os.getenv("TRUSTED_PROXY_HOPS")
    if raw is None or raw.strip() == "":
        return 1
    try:
        return int(raw.strip())
    except ValueError:
        return 1


def _header(headers, name: str) -> str:
    if headers is None:
        return ""
    value = headers.get(name)
    if value:
        return str(value).strip()
    # Starlette folds header names. A plain dict does not.
    for key, item in headers.items():
        if str(key).lower() == name and item:
            return str(item).strip()
    return ""


def client_ip(request) -> str:
    direct = request.client.host if request is not None and request.client else "unknown"
    headers = getattr(request, "headers", None)
    cf = _header(headers, "cf-connecting-ip")
    if cf:
        return cf
    hops = trusted_hops()
    if hops <= 0:
        return direct or "unknown"
    forwarded = _header(headers, "x-forwarded-for")
    if not forwarded:
        return direct or "unknown"
    parts = [part.strip() for part in forwarded.split(",") if part.strip()]
    if len(parts) < hops:
        return direct or "unknown"
    return parts[-hops]
