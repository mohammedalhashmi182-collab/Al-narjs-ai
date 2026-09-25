"""Telegram Bot API outbound adapter — gated behind a real credential.

Rules (mirroring ``whatsapp_sender``):
- Without ``TELEGRAM_TOKEN`` the sender is fully disabled: nothing leaves the
  local system and nothing is marked sent.
- Every send requires a real Bot API ack (``ok: true`` + ``message_id``) before
  it is recorded. A failed call is recorded as a failure — never silently sent.
- The owner gets a ``t.me`` fallback link for manual outreach.
- Secrets (tokens, auth headers) are never written to the database, logs, or
  response payloads — the bot token lives only inside the request URL and is
  never echoed.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.models import AcquisitionLead, InboundMessage, LeadEvent, OutboundMessage

log = logging.getLogger(__name__)

API_URL = "https://api.telegram.org"
CHANNEL = "telegram"
DISABLED_REASON = "TELEGRAM_TOKEN غير مُعدّ في ملف .env"
FALLBACK = "t.me"


def is_enabled() -> bool:
    return bool(settings.telegram_token)


def send_status() -> dict:
    """Secret-free connection status for the CEO / War Room."""
    token = bool(settings.telegram_token)
    owner = bool(settings.telegram_owner_chat_id)
    return {
        "enabled": is_enabled(),
        "connected": token and owner,
        "token_configured": token,
        "owner_chat_configured": owner,
        "disabled_reason": None if token else DISABLED_REASON,
        "fallback": FALLBACK,
        "env_required": ["TELEGRAM_TOKEN"],
        "env_optional": ["TELEGRAM_OWNER_CHAT_ID", "TELEGRAM_WEBHOOK_SECRET"],
    }


async def _post(method: str, payload: dict) -> dict:
    """POST one Bot API call (overridable seam for tests/offline runs).

    The token is part of the URL and is never logged or returned.
    """
    import httpx

    url = f"{API_URL}/bot{settings.telegram_token or ''}/{method}"
    timeout = httpx.Timeout(30.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                return {
                    "ok": False,
                    "status_code": resp.status_code,
                    "error": (resp.text or "")[:500],
                    "error_code": "http",
                }
            data = resp.json()
            if not data.get("ok"):
                return {
                    "ok": False,
                    "status_code": resp.status_code,
                    "error": str(data.get("description") or "")[:500],
                    "error_code": str(data.get("error_code") or "api"),
                }
            return {"ok": True, "status_code": resp.status_code, "provider_message_id": data.get("result")}
    except Exception as exc:  # network/timeout — record the failure, never a send
        return {"ok": False, "status_code": None, "error": str(exc)[:500], "error_code": "network"}


async def send_text(chat_id: Any, text: str) -> dict:
    """Send one text message and report the ack (or a structured failure)."""
    if not is_enabled() or chat_id is None:
        return {
            "ok": False,
            "enabled": is_enabled(),
            "disabled_reason": DISABLED_REASON,
            "error": "not_configured",
            "error_code": "missing_credential",
        }
    payload = {"chat_id": str(chat_id), "text": str(text)[:4096]}
    result = await _post("sendMessage", payload)
    result["chat_id"] = str(chat_id)
    return result


async def send_owner_alert(text: str) -> dict:
    """Best-effort push to the owner's War Room chat (no-op without a chat id)."""
    chat_id = settings.telegram_owner_chat_id
    if not chat_id:
        return {"ok": False, "error": "owner chat id not configured", "error_code": "missing_chat"}
    return await send_text(chat_id, text)


# --- Lead-aware outbound (reuses the WhatsApp queue governance) ---------------

def _wa_me_link(phone: Any) -> str | None:
    from .lead_normalize import wa_me_number

    return wa_me_number(phone)


async def _lead_for(session: AsyncSession, record: OutboundMessage) -> AcquisitionLead | None:
    if not record.lead_id:
        return None
    return (
        await session.execute(sa_select(AcquisitionLead).where(AcquisitionLead.id == record.lead_id))
    ).scalar_one_or_none()


async def _outreach_block_reason(session: AsyncSession, record: OutboundMessage) -> str | None:
    lead = await _lead_for(session, record)
    if lead is None:
        return None
    if lead.opt_out or (lead.lead_status or "") == "DO_NOT_CONTACT":
        return "opted_out"
    return None


async def enqueue(
    session: AsyncSession,
    *,
    lead_id: Any,
    message: str,
    chat_id: Any = None,
    message_type: str = "text",
) -> OutboundMessage:
    record = OutboundMessage(
        id=uuid4(),
        lead_id=lead_id if lead_id else None,
        channel=CHANNEL,
        phone=str(chat_id)[:32] if chat_id is not None else None,
        text=str(message),
        status="queued" if is_enabled() else "awaiting_credential",
        message_type=message_type or "text",
        wa_me_link=_wa_me_link(chat_id),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(record)
    await session.flush()
    return record


async def _record_event(session: AsyncSession, record: OutboundMessage, *, sent: bool, detail: str) -> None:
    if not record.lead_id:
        return
    lead = await _lead_for(session, record)
    if lead is None:
        return
    now = datetime.now(UTC)
    if sent:
        lead.last_contacted_at = now
    session.add(
        LeadEvent(
            lead_id=lead.id,
            event_type="message_sent" if sent else "send_failed",
            status_before=getattr(lead, "lead_status", "NEW") or "NEW",
            status_after=getattr(lead, "lead_status", "NEW") or "NEW",
            channel=CHANNEL,
            message=record.text[:2000],
            note=detail,
            created_at=now,
        )
    )


async def _send_with_ack(session: AsyncSession, record: OutboundMessage) -> dict:
    """Send one queued message. Never marks sent without a real ack."""
    now = datetime.now(UTC)

    if not is_enabled():
        record.status = "awaiting_credential"
        record.error = None
        record.updated_at = now
        return {
            "id": str(record.id),
            "lead_id": str(record.lead_id) if record.lead_id else None,
            "status": record.status,
            "fallback": FALLBACK,
        }

    blocked = await _outreach_block_reason(session, record)
    if blocked:
        record.status = "blocked"
        record.error = "opt-out honored; message not sent"
        record.updated_at = now
        await _record_event(session, record, sent=False, detail=f"blocked: {blocked}")
        return {"id": str(record.id), "status": record.status, "reason": blocked}

    result = await _post("sendMessage", {"chat_id": str(record.phone or ""), "text": str(record.text)[:4096]})
    if result.get("ok"):
        record.status = "sent"
        record.provider = "telegram_bot"
        record.provider_message_id = str(result.get("provider_message_id") or "") or None
        record.provider_status = "sent"
        record.acknowledged = True
        record.acknowledged_at = now
        record.error = None
        record.error_code = None
        record.sent_at = now
        record.updated_at = now
        await _record_event(session, record, sent=True, detail="provider=sent")
    else:
        record.status = "failed"
        record.provider = "telegram_bot"
        record.provider_status = "failed"
        record.error = (result.get("error") or "")[:500]
        record.error_code = result.get("error_code")
        record.sent_at = None
        record.updated_at = now
        record.retry_count += 1
        await _record_event(session, record, sent=False, detail="provider=request_failed")

    return {
        "id": str(record.id),
        "lead_id": str(record.lead_id) if record.lead_id else None,
        "status": record.status,
        "provider": record.provider,
        "provider_message_id": record.provider_message_id,
        "acknowledged": record.acknowledged,
        "error_code": record.error_code,
        "sent_at": record.sent_at.isoformat() if record.sent_at else None,
    }


async def send_now(session: AsyncSession, *, lead_id: Any, chat_id: Any, text: str) -> dict:
    """Enqueue and immediately attempt delivery (gated by credentials)."""
    record = await enqueue(session, lead_id=lead_id, message=text, chat_id=chat_id)
    return await _send_with_ack(session, record)


async def flush_queue(session: AsyncSession, *, limit: int = 20) -> list[dict]:
    rows = (
        await session.execute(
            sa_select(OutboundMessage)
            .where(OutboundMessage.channel == CHANNEL, OutboundMessage.status.in_(["queued", "awaiting_credential", "held"]))
            .order_by(OutboundMessage.created_at)
            .limit(limit)
        )
    ).scalars().all()
    return [await _send_with_ack(session, record) for record in rows]


async def inbound_summary(session: AsyncSession) -> dict:
    """Secret-free Telegram inbound metrics for the health probe."""
    from sqlalchemy import func as sa_func

    total = (await session.execute(
        sa_select(sa_func.count()).select_from(InboundMessage).where(InboundMessage.provider_message_id.like("tg:%"))
    )).scalar_one()
    mapped = (await session.execute(
        sa_select(sa_func.count()).select_from(InboundMessage).where(
            InboundMessage.provider_message_id.like("tg:%"), InboundMessage.lead_id.is_not(None)
        )
    )).scalar_one()
    return {"total": int(total), "mapped": int(mapped)}
