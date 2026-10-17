"""Zid webhook authentication and uninstall cleanup.

Zid does not document an HMAC body signature. Store webhooks use HTTP Basic
(username + password) and app-event webhooks use a secret header configured in
the Partner Dashboard.

* https://docs.zid.sa/create-a-webhook
* https://docs.zid.sa/doc-878234
* https://zid.sa/en/partners/developers/blog/app-security/

When ``X-Zid-Signature`` is present it must be HMAC-SHA256 hex of the raw body.
A static header is not accepted on that request. Otherwise the secret is
compared in constant time via Basic (user ``narjis``, password
``ZID_WEBHOOK_SECRET``) or ``X-Zid-Webhook-Token``. Either way the timestamp
must fall inside the replay window (``replay.zid_fresh``).
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


def _basic_or_static(headers, secret: str) -> bool:
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
    static = (headers.get("x-zid-webhook-token") or "").strip()
    return _eq(static, secret)


def signature_ok(raw: bytes, headers) -> bool:
    """Authenticate the delivery. Does not check the timestamp window."""
    secret = env("ZID_WEBHOOK_SECRET")
    if not secret:
        return False
    signed = (headers.get("x-zid-signature") or "").strip().lower()
    if signed:
        digest = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        return _eq(signed, digest)
    return _basic_or_static(headers, secret)


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
