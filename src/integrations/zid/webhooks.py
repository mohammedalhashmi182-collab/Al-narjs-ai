"""Zid webhook authentication and uninstall cleanup.

Zid does not document an HMAC body signature. Store webhooks use HTTP Basic
(username + password) and app-event webhooks use a secret header configured in
the Partner Dashboard.

* https://docs.zid.sa/create-a-webhook
* https://docs.zid.sa/doc-878234
* https://zid.sa/en/partners/developers/blog/app-security/

This app accepts either:
* ``Authorization: Basic`` for user ``narjis`` and password ``ZID_WEBHOOK_SECRET``
* header ``X-Zid-Webhook-Token`` equal to ``ZID_WEBHOOK_SECRET``
* header ``X-Zid-Signature`` equal to HMAC-SHA256 hex of the raw body (optional)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging

from sqlalchemy import or_, select

from src.integrations.config import ZID_WEBHOOK_USER, env
from src.integrations.parse import ident
from src.integrations.tokens import wipe

log = logging.getLogger(__name__)

UNINSTALL = "app.market.application.uninstall"


def _eq(left: str, right: str) -> bool:
    if not left or not right or len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def signature_ok(raw: bytes, headers) -> bool:
    secret = env("ZID_WEBHOOK_SECRET")
    if not secret:
        return False
    basic = headers.get("authorization") or ""
    scheme, _, token = basic.partition(" ")
    if scheme.lower() == "basic" and token:
        try:
            decoded = base64.b64decode(token.strip(), validate=True).decode()
        except Exception:
            decoded = ""
        user, sep, password = decoded.partition(":")
        if sep and _eq(user, ZID_WEBHOOK_USER) and _eq(password, secret):
            return True
    static = headers.get("x-zid-webhook-token") or ""
    if _eq(static.strip(), secret):
        return True
    signed = (headers.get("x-zid-signature") or "").strip().lower()
    digest = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return _eq(signed, digest)


def event_name(payload: dict) -> str:
    value = payload.get("event_name") or payload.get("event")
    return value.strip()[:80] if isinstance(value, str) else ""


def merchant_ids(payload: dict) -> set[str]:
    found: set[str] = set()
    for key in ("store_id", "store_uuid"):
        mid = ident(payload.get(key))
        if mid:
            found.add(mid)
    return found


async def apply(session, payload: dict) -> str:
    if event_name(payload) != UNINSTALL and str(payload.get("status") or "") != "uninstall":
        return "ignored"
    ids = merchant_ids(payload)
    if not ids:
        return "ignored"
    from src.models.store_integration import StoreConnection

    rows = list((await session.execute(select(StoreConnection).where(
        StoreConnection.platform == "zid",
        StoreConnection.status == "active",
        or_(StoreConnection.merchant_id.in_(ids), StoreConnection.store_ref.in_(ids)),
    ))).scalars())
    for row in rows:
        wipe(row)
    log.info("zid uninstall stores=%s rows=%s", ",".join(sorted(ids)), len(rows))
    return "uninstalled"
