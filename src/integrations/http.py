"""Outbound HTTP. Tests inject a transport; nothing here logs URLs or bodies."""

from __future__ import annotations

import logging

import httpx

from src.integrations.provider import StoreApiError

log = logging.getLogger(__name__)

TIMEOUT = 12.0
_transport: httpx.BaseTransport | None = None


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = transport


async def request(method: str, url: str, **kwargs) -> httpx.Response:
    try:
        async with httpx.AsyncClient(transport=_transport, timeout=TIMEOUT) as client:
            return await client.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        log.warning("store http error kind=%s", type(exc).__name__)
        raise StoreApiError("network", 0) from exc
