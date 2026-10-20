"""Salla webhook signature and event handling.

Signature: HMAC-SHA256 of the raw body, hex, header ``X-Salla-Signature``.
https://docs.salla.dev/webhooks

Uninstall event ``app.uninstalled`` and authorize event ``app.store.authorize``:
https://docs.salla.dev/partner-apis/app-events
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from sqlalchemy import or_, select

from src.integrations.config import env
from src.integrations.parse import ident
from src.integrations.tokens import apply_token_response, wipe

log = logging.getLogger(__name__)

UNINSTALL = "app.uninstalled"
AUTHORIZE = "app.store.authorize"


def signature_ok(raw: bytes, header: str | None) -> bool:
    secret = env("SALLA_WEBHOOK_SECRET")
    if not secret or not header:
        return False
    digest = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    given = header.strip().lower()
    if len(given) != len(digest):
        return False
    return hmac.compare_digest(given, digest)


def event_name(payload: dict) -> str:
    value = payload.get("event")
    return value.strip()[:80] if isinstance(value, str) else ""


def merchant_ids(payload: dict) -> set[str]:
    found: set[str] = set()
    merchant = payload.get("merchant")
    if isinstance(merchant, dict):
        mid = ident(merchant.get("id"))
    else:
        mid = ident(merchant)
    if mid:
        found.add(mid)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    store = data.get("store") if isinstance(data.get("store"), dict) else {}
    sid = ident(store.get("id"))
    if sid:
        found.add(sid)
    return found


async def _rows(session, ids: set[str]):
    if not ids:
        return []
    from src.models.store_integration import StoreConnection

    stmt = select(StoreConnection).where(
        StoreConnection.platform == "salla",
        or_(StoreConnection.merchant_id.in_(ids), StoreConnection.store_ref.in_(ids)),
    )
    return list((await session.execute(stmt)).scalars())


async def apply(session, payload: dict) -> str:
    name = event_name(payload)
    ids = merchant_ids(payload)
    if name == UNINSTALL:
        rows = await _rows(session, ids)
        for row in rows:
            if row.status == "active":
                wipe(row)
        log.info("salla uninstall merchants=%s rows=%s", ",".join(sorted(ids)), len(rows))
        return "uninstalled"
    if name == AUTHORIZE:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        if not data.get("access_token"):
            return "ignored"
        rows = [row for row in await _rows(session, ids) if row.status == "active"]
        for row in rows:
            apply_token_response(row, data)
        log.info("salla authorize merchants=%s rows=%s", ",".join(sorted(ids)), len(rows))
        return "authorized" if rows else "ignored"
    return "ignored"
