"""Zid webhook authentication and uninstall cleanup.

Documented checks (no body HMAC in Zid's docs):

* Store webhooks: ``Authorization: Basic`` for the username and password set
  when the webhook was created.
  https://docs.zid.sa/create-a-webhook
  https://zid.sa/en/partners/developers/blog/app-security/
* App events (``app.market.application.uninstall``): a secret header configured
  in the Partner Dashboard. This app reads ``X-Zid-Webhook-Token``.
  https://docs.zid.sa/doc-878234

When ``X-Zid-Signature`` is present it must be HMAC-SHA256 hex of the raw body.
That binds the body. The documented Basic header and the dashboard static
header do not. Basic auth (username ``narjis``, password
``ZID_WEBHOOK_SECRET``) is always accepted when the secret is set; the
dashboard static header still needs ``ZID_WEBHOOK_ALLOW_UNSIGNED``. A signature header is
never downgraded to those fallbacks. The timestamp window still applies.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging

from sqlalchemy import or_, select

from src.integrations.config import ZID_WEBHOOK_USER, env, zid_unsigned_fallback
from src.integrations.parse import ident
from src.integrations.tokens import wipe

log = logging.getLogger(__name__)

UNINSTALL = "app.market.application.uninstall"


def _eq(left: str, right: str) -> bool:
    if not left or not right or len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def _basic_header(secret: str) -> str:
    token = base64.b64encode(f"{ZID_WEBHOOK_USER}:{secret}".encode()).decode()
    return f"Basic {token}"


def _basic_ok(headers, secret: str) -> bool:
    """Constant-time check of ``Authorization: Basic narjis:<ZID_WEBHOOK_SECRET>``.

    This is Zid's documented webhook auth. It does not bind the body; replays
    of the same body are dropped by the raw-body dedupe in ``claim_event``.
    """
    return bool(secret) and _eq(headers.get("authorization") or "", _basic_header(secret))


def _static_header_ok(headers, secret: str) -> bool:
    """Partner Dashboard static header. Only with ``ZID_WEBHOOK_ALLOW_UNSIGNED``."""
    if not secret or not zid_unsigned_fallback():
        return False
    return _eq((headers.get("x-zid-webhook-token") or "").strip(), secret)


def signature_ok(raw: bytes, headers) -> bool:
    """Authenticate the delivery. Does not check the timestamp window.

    An empty ``ZID_WEBHOOK_SECRET`` never authenticates. A present
    ``X-Zid-Signature`` is HMAC-only and is never downgraded.
    """
    secret = env("ZID_WEBHOOK_SECRET")
    if not secret:
        return False
    signed = (headers.get("x-zid-signature") or "").strip().lower()
    if signed:
        digest = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        return _eq(signed, digest)
    return _basic_ok(headers, secret) or _static_header_ok(headers, secret)


def _store_id(payload: dict) -> str:
    direct = ident(payload.get("store_id"))
    if direct:
        return direct
    envelope = payload.get("envelope")
    if isinstance(envelope, dict):
        nested = ident(envelope.get("store_id"))
        if nested:
            return nested
    return ident(payload.get("store_uuid")) or "-"


def warn_unsigned(headers, payload: dict) -> None:
    """WARNING when a delivery was accepted without a body signature.

    Logs the store id only. No secret, header, email, or phone.
    """
    if (headers.get("x-zid-signature") or "").strip():
        return
    log.warning("zid webhook accepted unsigned store_id=%s", _store_id(payload))


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
