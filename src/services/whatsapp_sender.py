"""WhatsApp Business Cloud API adapter — safely gated behind real credentials.

Rules:
- Without ``WHATSAPP_TOKEN`` **and** ``WHATSAPP_PHONE_ID`` the sender is fully
  disabled. Messages are never marked ``SENT`` and never leave the local system.
- The owner gets a one-tap ``wa.me`` fallback link for manual outreach.
- With credentials every send requires an actual Cloud API ack before recording
  a provider-supplied message id and timestamp. A failed ack is recorded as a
  ``send_failed`` event — never silently marked as sent.
- The provider ack is persisted as ``acknowledged`` + ``provider_message_id``
  + ``sent_at``. Delivery status updates (sent/delivered/read/failed) come back
  through the webhook and are applied via :func:`acknowledge_status`.
- Governance: opt-outs and ``DO_NOT_CONTACT`` leads are always blocked, a daily
  auto-send cap and a per-lead cooldown prevent spam loops.
- Secrets (tokens, auth headers) are never written to the database, logs, or
  response payloads.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.models import AcquisitionLead, InboundMessage, LeadEvent, OutboundMessage

from .lead_normalize import wa_me_number

log = logging.getLogger(__name__)

API_URL = "https://graph.facebook.com/v20.0"
DISABLED_REASON = "WHATSAPP_TOKEN و/أو WHATSAPP_PHONE_ID غير مُعدّ في ملف .env"
CHANNEL = "whatsapp"

# Statuses that still want first outreach but must stay reachable in a wave.
_FIRST_OUTREACH = ("NEW", "READY")


def is_enabled() -> bool:
    return bool(settings.whatsapp_token and settings.whatsapp_phone_number_id)


def _webhook_configured() -> bool:
    return bool(settings.whatsapp_app_secret and settings.whatsapp_webhook_verify_token)


def send_status() -> dict:
    """Secret-free connection status for the CEO / War Room.

    Returns booleans and reason strings only — never credential values.
    """
    token = bool(settings.whatsapp_token)
    phone_id = bool(settings.whatsapp_phone_number_id)
    connected = token and phone_id
    webhook = settings.whatsapp_app_secret and settings.whatsapp_webhook_verify_token
    return {
        "enabled": is_enabled(),
        "connected": connected,
        "token_configured": token,
        "phone_id_configured": phone_id,
        "disabled_reason": None if connected else DISABLED_REASON,
        "fallback": "wa.me",
        "webhook_configured": bool(webhook),
        "webhook_healthy": bool(webhook),
        "env_required": ["WHATSAPP_TOKEN", "WHATSAPP_PHONE_ID"],
        "env_optional": ["WHATSAPP_APP_SECRET", "WHATSAPP_WEBHOOK_VERIFY_TOKEN"],
    }


def _wa_me_link(phone: Any, message: str) -> Optional[str]:
    return wa_me_number(phone)


def _build_payload(record: OutboundMessage, message_type: str = "text") -> dict:
    """Cloud API message payload. Never contains credentials."""
    payload: dict = {
        "messaging_product": "whatsapp",
        "to": str(record.phone or "").replace("+", ""),
        "type": message_type,
    }
    if message_type == "text":
        payload["text"] = {"body": record.text[:4096]}
    else:
        # Only text is supported by the engine today; anything else is rejected
        # upstream rather than guessed here.
        payload["text"] = {"body": record.text[:4096]}
    return payload


async def _post_message(record: OutboundMessage) -> dict:
    """POST a message to the Cloud API (overridable seam for tests/offline runs)."""
    import httpx

    url = f"{API_URL}/{settings.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_token or ''}",
        "Content-Type": "application/json",
    }
    body = _build_payload(record, message_type=record.message_type or "text")
    timeout = httpx.Timeout(30.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                code = None
                try:
                    code = ((resp.json() or {}).get("error") or {}).get("code")
                except Exception:
                    code = None
                return {
                    "ok": False,
                    "status_code": resp.status_code,
                    "error": (resp.text or "")[:500],
                    "error_code": str(code) if code is not None else None,
                }
            data = resp.json()
            mid = ((data.get("messages") or [{}])[0].get("id")) or None
            return {
                "ok": True,
                "status_code": resp.status_code,
                "provider_message_id": mid,
            }
    except Exception as exc:  # network/timeout — record the failure, never a send
        return {"ok": False, "status_code": None, "error": str(exc)[:500], "error_code": "network"}


async def _lead_for(session: AsyncSession, record: OutboundMessage) -> Optional[AcquisitionLead]:
    if not record.lead_id:
        return None
    return (
        await session.execute(
            sa_select(AcquisitionLead).where(AcquisitionLead.id == record.lead_id)
        )
    ).scalar_one_or_none()


async def _outreach_block_reason(session: AsyncSession, record: OutboundMessage) -> Optional[str]:
    """Governance gate. Return a reason to block/hold, or None to allow sending."""
    lead = await _lead_for(session, record)
    if lead is not None and (lead.opt_out or (lead.lead_status or "") == "DO_NOT_CONTACT"):
        return "opted_out"

    if lead is not None:
        last_sent = (
            await session.execute(
                sa_select(OutboundMessage.sent_at)
                .where(
                    OutboundMessage.lead_id == lead.id,
                    OutboundMessage.status == "sent",
                    OutboundMessage.sent_at.is_not(None),
                )
                .order_by(OutboundMessage.sent_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if last_sent is not None:
            cooldown = timedelta(hours=settings.whatsapp_lead_cooldown_hours)
            if datetime.now(timezone.utc) - last_sent < cooldown:
                return "cooldown"

    sent_today = (
        await session.execute(
            sa_select(OutboundMessage.id)
            .where(OutboundMessage.status == "sent", OutboundMessage.sent_at >= _start_of_today_utc())
        )
    ).scalars().all()
    if len(sent_today) >= settings.whatsapp_daily_auto_limit:
        return "daily_limit"
    return None


def _start_of_today_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def enqueue(
    session: AsyncSession,
    *,
    lead_id: Any,
    message: str,
    phone: Any = None,
    channel: str = CHANNEL,
    message_type: str = "text",
) -> OutboundMessage:
    phone = str(phone or "").strip()
    record = OutboundMessage(
        id=uuid4(),
        lead_id=lead_id if lead_id else None,
        channel=channel,
        phone=phone[:32] if phone else None,
        text=str(message),
        status="queued" if is_enabled() else "awaiting_credential",
        message_type=message_type or "text",
        wa_me_link=_wa_me_link(phone, message),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(record)
    await session.flush()
    return record


async def _record_lead_event(session: AsyncSession, record: OutboundMessage, *, sent: bool, detail: str) -> None:
    if not record.lead_id:
        return
    lead = await _lead_for(session, record)
    if lead is None:
        return

    now = datetime.now(timezone.utc)
    if sent:
        before = getattr(lead, "lead_status", "NEW") or "NEW"
        if before in _FIRST_OUTREACH:
            lead.lead_status = "CONTACTED"
        lead.last_contacted_at = now
        session.add(
            LeadEvent(
                lead_id=lead.id,
                event_type="message_sent",
                status_before=before,
                status_after=lead.lead_status,
                channel=CHANNEL,
                message=record.text[:2000],
                note=detail,
                created_at=now,
            )
        )
    else:
        session.add(
            LeadEvent(
                lead_id=lead.id,
                event_type="send_failed",
                status_before=getattr(lead, "lead_status", "NEW") or "NEW",
                status_after=getattr(lead, "lead_status", "NEW") or "NEW",
                channel=CHANNEL,
                message=detail[:2000],
                note="no content marked sent; ack absent",
                created_at=now,
            )
        )


async def _send_with_ack(session: AsyncSession, record: OutboundMessage) -> dict:
    """Send one queued message. Never marks sent without a real ack."""
    now = datetime.now(timezone.utc)
    if not is_enabled():
        record.status = "awaiting_credential"
        record.error = None
        record.updated_at = now
        return {
            "id": str(record.id),
            "lead_id": str(record.lead_id) if record.lead_id else None,
            "status": record.status,
            "wa_me_link": record.wa_me_link,
            "fallback": "wa.me",
        }

    blocked = await _outreach_block_reason(session, record)
    if blocked:
        if blocked == "opted_out":
            record.status = "blocked"
            record.error = "opt-out honored; message not sent"
            await _record_lead_event(
                session, record, sent=False, detail="blocked: opt-out honored — never message opted-out leads"
            )
        elif blocked == "cooldown":
            record.status = "held"
            record.error = f"cooldown within {settings.whatsapp_lead_cooldown_hours}h for this lead"
        else:
            record.status = "held"
            record.error = f"daily auto-send cap ({settings.whatsapp_daily_auto_limit}) reached"
        record.updated_at = now
        return {
            "id": str(record.id),
            "lead_id": str(record.lead_id) if record.lead_id else None,
            "status": record.status,
            "reason": blocked,
            "wa_me_link": record.wa_me_link,
        }

    result = await _post_message(record)
    if result.get("ok"):
        record.status = "sent"
        record.provider = "meta_whatsapp_cloud"
        record.provider_message_id = result.get("provider_message_id")
        record.provider_status = "pending"
        record.acknowledged = True
        record.acknowledged_at = now
        record.error = None
        record.error_code = None
        record.sent_at = now
        record.updated_at = now
        mid = result.get("provider_message_id") or "n/a"
        detail = f"provider=sent mid={mid}"
        await _record_lead_event(session, record, sent=True, detail=detail)
    else:
        # Capture a bounded, secret-free error summary.
        record.status = "failed"
        record.provider = "meta_whatsapp_cloud"
        record.provider_status = "failed"
        record.error = (result.get("error") or "")[:500]
        record.error_code = result.get("error_code")
        record.sent_at = None
        record.updated_at = now
        record.retry_count += 1
        detail = f"provider=request_failed http={result.get('status_code')}"
        await _record_lead_event(session, record, sent=False, detail=detail)

    return {
        "id": str(record.id),
        "lead_id": str(record.lead_id) if record.lead_id else None,
        "status": record.status,
        "provider": record.provider,
        "provider_message_id": record.provider_message_id,
        "provider_status": record.provider_status,
        "acknowledged": record.acknowledged,
        "error_code": record.error_code,
        "sent_at": record.sent_at.isoformat() if record.sent_at else None,
        "wa_me_link": record.wa_me_link,
    }


async def flush_queue(session: AsyncSession, *, limit: int = 20) -> list[dict]:
    rows = (
        await session.execute(
            sa_select(OutboundMessage)
            .where(OutboundMessage.status.in_(["queued", "awaiting_credential", "held"]))
            .order_by(OutboundMessage.created_at)
            .limit(limit)
        )
    ).scalars().all()

    results: list[dict] = []
    for record in rows:
        results.append(await _send_with_ack(session, record))
    return results


async def send_now(
    session: AsyncSession,
    *,
    lead_id: Any,
    phone: Any,
    text: str,
    message_type: str = "text",
) -> dict:
    """Enqueue and immediately attempt delivery (gated by credentials)."""
    record = await enqueue(
        session, lead_id=lead_id, message=text, phone=phone, channel=CHANNEL, message_type=message_type
    )
    return await _send_with_ack(session, record)


async def acknowledge_status(session: AsyncSession, provider_message_id: str, status: str, *, error_code: Optional[str] = None) -> Optional[OutboundMessage]:
    """Apply a provider delivery/read/failed update delivered via the webhook.

    Only ever moves an already-``sent`` (acknowledged) message to a richer
    provider status; a message that was never acknowledged stays untouched.
    """
    if not provider_message_id:
        return None
    record = (
        await session.execute(
            sa_select(OutboundMessage).where(OutboundMessage.provider_message_id == provider_message_id)
        )
    ).scalar_one_or_none()
    if record is None or not record.acknowledged:
        return None
    if status in ("delivered", "read", "sent", "failed") and status != record.provider_status:
        record.provider_status = status
        record.updated_at = datetime.now(timezone.utc)
        if status == "failed":
            record.status = "failed"
            record.error_code = error_code
            record.error = error_code or "provider delivery failure"
    return record


async def conversation_summary(session: AsyncSession) -> dict:
    """CEO-facing WhatsApp/revenue conversation metrics (no secrets)."""
    from sqlalchemy import func as sa_func

    today = _start_of_today_utc()
    now = datetime.now(timezone.utc)

    sent_total = (
        await session.execute(sa_select(sa_func.count()).select_from(OutboundMessage).where(OutboundMessage.status == "sent"))
    ).scalar_one()
    sent_today = (
        await session.execute(
            sa_select(sa_func.count()).select_from(OutboundMessage).where(
                OutboundMessage.status == "sent", OutboundMessage.sent_at >= today
            )
        )
    ).scalar_one()
    delivered_today = (
        await session.execute(
            sa_select(sa_func.count()).select_from(OutboundMessage).where(
                OutboundMessage.sent_at >= today,
                OutboundMessage.provider_status.in_(["delivered", "read"]),
            )
        )
    ).scalar_one()
    queued = (
        await session.execute(
            sa_select(sa_func.count()).select_from(OutboundMessage).where(
                OutboundMessage.status.in_(["queued", "held", "awaiting_credential"])
            )
        )
    ).scalar_one()
    failed = (
        await session.execute(sa_select(sa_func.count()).select_from(OutboundMessage).where(OutboundMessage.status == "failed"))
    ).scalar_one()

    replies_total = (
        await session.execute(sa_select(sa_func.count()).select_from(InboundMessage))
    ).scalar_one()
    replies_today = (
        await session.execute(
            sa_select(sa_func.count()).select_from(InboundMessage).where(InboundMessage.created_at >= today)
        )
    ).scalar_one()

    qualified = (
        await session.execute(
            sa_select(sa_func.count()).select_from(AcquisitionLead).where(
                AcquisitionLead.lead_status.in_(["INTERESTED", "DEMO", "PROPOSAL", "REPLIED"])
            )
        )
    ).scalar_one()
    buying_signals = (
        await session.execute(
            sa_select(sa_func.count()).select_from(AcquisitionLead).where(
                AcquisitionLead.buying_signal.is_(True), AcquisitionLead.lead_status != "WON"
            )
        )
    ).scalar_one()
    objections_today = (
        await session.execute(
            sa_select(sa_func.count()).select_from(InboundMessage).where(
                InboundMessage.created_at >= today, InboundMessage.objection.is_not(None)
            )
        )
    ).scalar_one()
    proposals_requested = (
        await session.execute(
            sa_select(sa_func.count()).select_from(InboundMessage).where(InboundMessage.intent == "PROPOSAL")
        )
    ).scalar_one()
    won = (
        await session.execute(
            sa_select(sa_func.count()).select_from(AcquisitionLead).where(AcquisitionLead.lead_status == "WON")
        )
    ).scalar_one()

    from src.models import Payment

    verified_sar = int(
        (
            await session.execute(
                sa_select(sa_func.coalesce(sa_func.sum(Payment.amount), 0)).where(Payment.status == "paid")
            )
        ).scalar_one()
        // 100
    )

    response_rate = round(replies_total / sent_total, 4) if sent_total else 0.0
    return {
        "connected": is_enabled(),
        "status": send_status(),
        "today": {
            "queued": int(queued),
            "sent": int(sent_today),
            "delivered": int(delivered_today),
            "replies": int(replies_today),
            "qualified": int(qualified),
            "proposals": int(proposals_requested),
            "won": int(won),
            "verified_sar": verified_sar,
        },
        "totals": {
            "sent": int(sent_total),
            "failed": int(failed),
            "replies": int(replies_total),
            "response_rate": response_rate,
            "qualified": int(qualified),
            "buying_signals": int(buying_signals),
            "objections_today": int(objections_today),
            "proposals_requested": int(proposals_requested),
            "won": int(won),
        },
        "as_of": now.isoformat(),
    }