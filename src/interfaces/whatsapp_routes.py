"""Public WhatsApp Business webhook endpoints.

The Meta / WhatsApp Cloud API calls these. Both endpoints are deliberately
public (Meta cannot authenticate as the site owner) — trust comes from:

- GET  : ``hub.verify_token`` equality with ``WHATSAPP_WEBHOOK_VERIFY_TOKEN``.
- POST : HMAC-SHA256 signature over the raw body in ``X-Hub-Signature-256``
         using ``WHATSAPP_APP_SECRET``.

No secret value is ever echoed in responses or logs, and no raw inbound
payload is persisted (only a payload hash for audits).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func as sa_func, select as sa_select

from src.config.settings import settings
from src.models import InboundMessage
from src.services.whatsapp_webhook import process_inbound_payload, verify_webhook_signature, webhook_disabled_reason

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["whatsapp-webhook"])

_VERIFY_RESPONSE = "نلتزم بذلك ✓"

# Process-local (scraped, no secrets) diagnostics for signature rejections.
# A short prefix of the received/expected digest is kept so a human can compare
# them offline; the full signature is never stored and secrets are never shown.
_rx: dict = {"rejected_total": 0, "last_reject": None}


def _signature_prefix(signature: str) -> str:
    """First 28 chars of a signature value (safe for diagnostics)."""
    return (signature or "")[:28]


def _record_reject(reason: str, received: str, expected_prefix: str, body_len: int) -> None:
    _rx["rejected_total"] += 1
    _rx["last_reject"] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "received_prefix": _signature_prefix(received),
        "expected_prefix": expected_prefix,
        "body_len": body_len,
    }


@router.get("/whatsapp")
async def whatsapp_webhook_verification(request: Request):
    """Meta subscription verification handshake (GET).

    Replies with the challenge only when the verify token matches; otherwise a
    plain 403. All values come from query parameters — nothing is logged.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token and settings.whatsapp_webhook_verify_token:
        if token == settings.whatsapp_webhook_verify_token:
            return Response(content=challenge or _VERIFY_RESPONSE, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """Receive inbound messages and delivery statuses.

    Verifies the signature before touching any payload. A valid payload is
    processed transactionally inside one session. Always answers quickly with
    a 200 so Meta does not retry a well-formed delivery.
    """
    raw = await request.body()

    if webhook_disabled_reason():
        log.warning("WhatsApp webhook disabled: %s", webhook_disabled_reason())
        return JSONResponse({"status": "disabled"}, status_code=200)

    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        _record_reject("missing_header", "", "", len(raw))
        return JSONResponse({"status": "invalid_signature"}, status_code=403)
    if not verify_webhook_signature(signature, raw):
        secret = settings.whatsapp_app_secret or ""
        expected_hex = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        _record_reject("signature_mismatch", signature, expected_hex[:28], len(raw))
        return JSONResponse({"status": "invalid_signature"}, status_code=403)

    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return JSONResponse({"status": "bad_json"}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"status": "bad_payload"}, status_code=400)

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        try:
            summary = await process_inbound_payload(session, payload)
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("WhatsApp webhook processing failed")
            return JSONResponse({"status": "error"}, status_code=200)

    return JSONResponse({"status": "ok", "summary": summary})


@router.get("/whatsapp/health")
async def whatsapp_webhook_health(request: Request):
    """Secret-free health/configuration probe used by the War Room."""
    result = {
        "configured": webhook_disabled_reason() is None,
        "disabled_reason": webhook_disabled_reason(),
    }
    try:
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            total = (
                await session.execute(sa_select(sa_func.count()).select_from(InboundMessage))
            ).scalar_one()
            recent = (
                await session.execute(
                    sa_select(sa_func.count())
                    .select_from(InboundMessage)
                    .where(InboundMessage.created_at >= since)
                )
            ).scalar_one()
            last = (
                await session.execute(
                    sa_select(InboundMessage)
                    .order_by(InboundMessage.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        result["inbound"] = {
            "total": total,
            "recent_24h": recent,
            "last_received_at": last.created_at.isoformat() if last and last.created_at else None,
            "last_processing_status": last.processing_status if last else None,
        }
    except Exception:
        log.exception("WhatsApp webhook health stats unavailable")
        result["inbound"] = {"error": "unavailable"}
    result["webhook_rx"] = {
        "rejected_total": _rx["rejected_total"],
        "last_reject": _rx["last_reject"],
    }
    return result