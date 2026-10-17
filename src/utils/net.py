"""Client address shared by rate limits.

``CF-Connecting-IP`` is the visitor only when the address that connected to
us sits in Cloudflare's published ranges. That address is the immediate peer
(``request.client.host``), or the right-most ``X-Forwarded-For`` hop when
``TRUSTED_PROXY_HOPS`` says a proxy appended one (Render is 1). Anyone can
send the header, so a peer outside those ranges is ignored and the hop rule
is used instead. A hop count of 0, or a header shorter than the hop count,
uses the direct peer. The left-most forwarded value is never trusted.

Ranges are the snapshot below.
Source: https://www.cloudflare.com/ips-v4 and https://www.cloudflare.com/ips-v6
(fetched 2026-10-17; also listed at
https://developers.cloudflare.com/fundamentals/concepts/cloudflare-ip-addresses/).
``CLOUDFLARE_IP_RANGES``, a comma-separated CIDR list, replaces the snapshot
when it is set.
"""

from __future__ import annotations

import ipaddress
import os

# Snapshot of Cloudflare's published edges, 2026-10-17.
# https://www.cloudflare.com/ips-v4
# https://www.cloudflare.com/ips-v6
_CLOUDFLARE_CIDRS: tuple[str, ...] = (
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
)


def trusted_hops() -> int:
    raw = os.getenv("TRUSTED_PROXY_HOPS")
    if raw is None or raw.strip() == "":
        return 1
    try:
        return int(raw.strip())
    except ValueError:
        return 1


def cloudflare_networks() -> list[ipaddress._BaseNetwork]:
    """Bundled Cloudflare ranges, or ``CLOUDFLARE_IP_RANGES`` when that env is set."""
    raw = os.getenv("CLOUDFLARE_IP_RANGES")
    if raw is not None and raw.strip():
        cidrs = [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]
    else:
        cidrs = list(_CLOUDFLARE_CIDRS)
    networks: list[ipaddress._BaseNetwork] = []
    for cidr in cidrs:
        try:
            networks.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            continue
    if not networks:
        for cidr in _CLOUDFLARE_CIDRS:
            networks.append(ipaddress.ip_network(cidr, strict=False))
    return networks


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


def _in_cloudflare(ip: str) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(address in network for network in cloudflare_networks())


def client_ip(request) -> str:
    direct = request.client.host if request is not None and request.client else ""
    direct = direct or "unknown"
    hops = trusted_hops()
    headers = getattr(request, "headers", None)
    forwarded = _header(headers, "x-forwarded-for")
    peer = direct
    if hops > 0 and forwarded:
        parts = [part.strip() for part in forwarded.split(",") if part.strip()]
        if len(parts) >= hops:
            peer = parts[-hops]
    cf = _header(headers, "cf-connecting-ip")
    if cf and _in_cloudflare(peer):
        return cf
    return peer
