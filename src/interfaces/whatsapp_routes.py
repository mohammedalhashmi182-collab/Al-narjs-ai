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

import json
import logging

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from src.config.settings import settings
from src.services.whatsapp_webhook import process_inbound_payload, verify_webhook_signature, webhook_disabled_reason

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["whatsapp-webhook"])

_VERIFY_RESPONSE = "نلتزم بذلك ✓"


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
    if not signature or not verify_webhook_signature(signature, raw):
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
async def whatsapp_webhook_health():
    """Secret-free health/configuration probe used by the War Room."""
    return {
        "configured": webhook_disabled_reason() is None,
        "disabled_reason": webhook_disabled_reason(),
    }