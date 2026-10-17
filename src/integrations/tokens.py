"""Encrypted token storage and refresh. Reuses the tenant Fernet helper."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Optional

from src.integrations.provider import StoreApiError

log = logging.getLogger(__name__)

_locks: dict[str, asyncio.Lock] = {}
_REFRESH_SKEW = timedelta(minutes=2)


def _lock(key: str) -> asyncio.Lock:
    lock = _locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _locks[key] = lock
    return lock


def seal(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    from src.services.tenant_reply import encrypt_token

    return encrypt_token(value)


def open_secret(blob: Optional[str]) -> Optional[str]:
    if not blob:
        return None
    from src.services.tenant_reply import decrypt_token

    return decrypt_token(blob)


def expires_at(value: object, *, now: Optional[datetime] = None) -> Optional[datetime]:
    """Salla sends seconds on the token endpoint and a unix timestamp on app.store.authorize."""
    if value is None or value == "":
        return None
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    now = now or datetime.now(UTC)
    if n > 1_000_000_000:
        return datetime.fromtimestamp(n, UTC)
    if n <= 0:
        return None
    return now + timedelta(seconds=n)


def wipe(row) -> None:
    row.access_token_enc = None
    row.refresh_token_enc = None
    row.authorization_enc = None
    row.status = "uninstalled"
    row.uninstalled_at = datetime.now(UTC)


def apply_token_response(row, body: dict, *, now: Optional[datetime] = None) -> None:
    access = str(body.get("access_token") or "")
    if not access:
        raise StoreApiError("token_response", 200)
    row.access_token_enc = seal(access)
    refresh = body.get("refresh_token")
    if refresh:
        row.refresh_token_enc = seal(str(refresh))
    authorization = body.get("authorization") or body.get("Authorization")
    if authorization:
        row.authorization_enc = seal(str(authorization))
    row.expires_at = expires_at(body.get("expires_in", body.get("expires")), now=now)
    scope = body.get("scope")
    if isinstance(scope, str) and scope:
        row.scopes = scope[:500]
    row.status = "active"
    row.uninstalled_at = None


def needs_refresh(row, *, now: Optional[datetime] = None) -> bool:
    exp = row.expires_at
    if exp is None:
        return False
    now = now or datetime.now(UTC)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    return exp <= now + _REFRESH_SKEW


async def ensure_fresh(session, row) -> tuple[str, Optional[str]]:
    """Return (access_token, authorization). Refresh once under a per-connection lock.

    The new refresh token is committed immediately: Salla refresh tokens are
    single-use, and a later rollback must not put the spent token back.
    """
    async with _lock(str(row.id)):
        await session.refresh(row)
        if row.status != "active":
            raise StoreApiError("not_active", 401)
        if needs_refresh(row):
            await _refresh(session, row)
        access = open_secret(row.access_token_enc)
        if not access:
            raise StoreApiError("missing_token", 401)
        return access, open_secret(row.authorization_enc)


async def force_refresh(session, row) -> tuple[str, Optional[str]]:
    async with _lock(str(row.id)):
        await session.refresh(row)
        await _refresh(session, row)
        access = open_secret(row.access_token_enc)
        if not access:
            raise StoreApiError("missing_token", 401)
        return access, open_secret(row.authorization_enc)


async def _refresh(session, row) -> None:
    refresh = open_secret(row.refresh_token_enc)
    if not refresh:
        raise StoreApiError("missing_refresh", 401)
    if row.platform == "salla":
        from src.integrations.salla.client import refresh_tokens
    elif row.platform == "zid":
        from src.integrations.zid.client import refresh_tokens
    else:
        raise StoreApiError("platform", 400)
    body = await refresh_tokens(refresh)
    apply_token_response(row, body)
    await session.commit()
    log.info("store token refreshed platform=%s project=%s", row.platform, row.project_id)
