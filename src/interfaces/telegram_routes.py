"""Public Telegram Bot API webhook endpoints.

Telegram calls these. Trust comes from the ``secret_token`` supplied to
``setWebhook`` — Telegram echoes it back in the ``X-Telegram-Bot-Api-Secret-Token``
header on every call. Both endpoints are deliberately public:

- POST : constant-time header comparison before any payload is parsed.
- GET  : a secret-free health/configuration probe for the War Room.

No secret value is ever echoed in responses or logs, and no raw inbound
payload is persisted (only a payload hash for audits).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func as sa_func
from sqlalchemy import select as sa_select

from src.models import InboundMessage
from src.services.telegram_sender import inbound_summary
from src.services.telegram_webhook import (
    SIGNATURE_HEADER,
    process_inbound_update,
    secret_source,
    verify_secret,
    webhook_disabled_reason,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["telegram-webhook"])

# Process-local (scraped, no secrets) diagnostics for rejected calls.
_rx: dict = {"rejected_total": 0, "last_reject": None}


def _record_reject(reason: str, body_len: int) -> None:
    _rx["rejected_total"] += 1
    _rx["last_reject"] = {
        "at": datetime.now(UTC).isoformat(),
        "reason": reason,
        "body_len": body_len,
    }


@router.post("/telegram")
async def telegram_webhook(request: Request):
    """Receive inbound Telegram updates.

    Verifies the secret header before touching any payload. A valid payload is
    processed transactionally inside one session and always answers quickly with
    a 200 so Telegram does not retry a well-formed delivery.
    """
    raw = await request.body()

    if webhook_disabled_reason():
        log.warning("Telegram webhook disabled: %s", webhook_disabled_reason())
        return JSONResponse({"status": "disabled"}, status_code=200)

    header = request.headers.get(SIGNATURE_HEADER)
    if not verify_secret(header):
        _record_reject("missing_header" if not header else "secret_mismatch", len(raw))
        return JSONResponse({"status": "invalid_secret"}, status_code=403)

    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return JSONResponse({"status": "bad_json"}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"status": "bad_payload"}, status_code=400)

    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        try:
            summary = await process_inbound_update(session, payload)
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("Telegram webhook processing failed")
            return JSONResponse({"status": "error"}, status_code=200)

    return JSONResponse({"status": "ok", "summary": summary})


@router.get("/telegram/health")
async def telegram_webhook_health(request: Request):
    """Secret-free health/configuration probe used by the War Room."""
    result: dict = {
        "configured": webhook_disabled_reason() is None,
        "disabled_reason": webhook_disabled_reason(),
        "secret_source": secret_source(),
    }
    try:
        since = datetime.now(UTC) - timedelta(hours=24)
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
            telegram_stats = await inbound_summary(session)
        result["inbound"] = {
            "total": total,
            "recent_24h": recent,
            "last_received_at": last.created_at.isoformat() if last and last.created_at else None,
            "last_processing_status": last.processing_status if last else None,
        }
        result["telegram"] = telegram_stats
    except Exception:
        log.exception("Telegram webhook health stats unavailable")
        result["inbound"] = {"error": "unavailable"}
    result["webhook_rx"] = {
        "rejected_total": _rx["rejected_total"],
        "last_reject": _rx["last_reject"],
    }
    return result
