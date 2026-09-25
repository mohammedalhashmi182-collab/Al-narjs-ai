"""Telegram Bot API inbound webhook handler.

Same pipeline as the WhatsApp handler, mapped onto Telegram ``update`` objects:

  update
    -> ``X-Telegram-Bot-Api-Secret-Token`` verified (constant-time)
    -> deduplicated by ``tg:<chat_id>:<message_id>``
    -> sender linked to a lead (phone in text, or a previously linked chat)
    -> appended as a LeadEvent + stored InboundMessage
    -> intent classified, buying signal / objection / opt-out detected
    -> lead promoted and the revenue queue reprioritized

Governance: opt-outs always flip the lead to ``DO_NOT_CONTACT``. No raw payload
is persisted — only a payload hash. Secrets are never returned or logged.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.models import AcquisitionLead, InboundMessage, LeadEvent

from .lead_normalize import normalize_phone
from .whatsapp_webhook import _BUYING_INTENTS, _promote_lead, classify_intent

log = logging.getLogger(__name__)

CHANNEL = "telegram"
SIGNATURE_HEADER = "X-Telegram-Bot-Api-Secret-Token"

# Fields Telegram always sends alongside payload content; ignored when picking a
# message type so ``photo``/``document``/... can be detected generically.
_NON_CONTENT_KEYS = frozenset({
    "message_id", "from", "chat", "date", "edit_date", "text", "caption",
    "entities", "caption_entities", "new_chat_members", "left_chat_member",
    "new_chat_title", "new_chat_photo", "delete_chat_photo", "group_chat_created",
    "migrate_to_chat_id", "migrate_from_chat_id", "pinned_message",
    "reply_to_message", "via_bot", "forward_from", "forward_date",
})

# Saudi / international mobile patterns accepted in free text.
_PHONE_RE = re.compile(r"(?<!\d)(\+?(?:966|965|971|974)5\d{8}|05\d{8}|5\d{8})(?!\d)")
_DIGITS_RE = re.compile(r"\D")


def webhook_disabled_reason() -> str | None:
    if not settings.telegram_webhook_secret:
        return "TELEGRAM_WEBHOOK_SECRET not configured"
    return None


def verify_ok() -> bool:
    return webhook_disabled_reason() is None


def verify_secret(header_value: str | None) -> bool:
    """Constant-time comparison of Telegram's ``secret_token`` header."""
    secret = settings.telegram_webhook_secret
    if not secret or not header_value:
        return False
    return hmac.compare_digest(secret, header_value)


# --- Sender / lead mapping ----------------------------------------------------

def _digits(value: Any) -> str:
    return _DIGITS_RE.sub("", str(value or ""))


def _phone_from_text(text: Any) -> str | None:
    match = _PHONE_RE.search(str(text or ""))
    if not match:
        return None
    return normalize_phone(_digits(match.group(1)))


async def _lead_for_sender(session: AsyncSession, chat_id: Any, text: Any) -> AcquisitionLead | None:
    """Link a Telegram chat to a canonical lead.

    1. A phone number written in the message itself (the normal first contact).
    2. Otherwise any lead already linked to this chat in an earlier message —
       keeps the conversation stable without a schema change.
    """
    phone = _phone_from_text(text)
    if phone:
        lead = (
            await session.execute(
                sa_select(AcquisitionLead).where(AcquisitionLead.phone == phone).order_by(AcquisitionLead.created_at)
            )
        ).scalars().first()
        if lead is not None:
            return lead

    prior = (
        await session.execute(
            sa_select(InboundMessage)
            .where(
                InboundMessage.sender_number == str(chat_id)[:32],
                InboundMessage.lead_id.is_not(None),
            )
            .order_by(InboundMessage.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if prior is not None and prior.lead_id:
        return (
            await session.execute(sa_select(AcquisitionLead).where(AcquisitionLead.id == prior.lead_id))
        ).scalar_one_or_none()
    return None


# --- Processing ---------------------------------------------------------------

def _timestamp(ts: Any) -> datetime | None:
    try:
        if isinstance(ts, (int, float)) and ts > 0:
            return datetime.fromtimestamp(float(ts), tz=UTC)
        if isinstance(ts, str):
            try:
                return datetime.fromtimestamp(float(ts), tz=UTC)
            except ValueError:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, OverflowError, OSError):
        return None
    return None


def _message_type(message: dict) -> str:
    if isinstance(message.get("text"), str):
        return "text"
    for key in message:
        if key in _NON_CONTENT_KEYS:
            continue
        if isinstance(message.get(key), dict):
            return key[:20]
    return "unknown"


def _extract_text(message: dict) -> str:
    for key in ("text", "caption"):
        value = message.get(key)
        if isinstance(value, str):
            return value
    return ""


async def process_inbound_update(session: AsyncSession, update: Any) -> dict:
    """Process one Telegram ``update`` body. Always answers quickly upstream."""
    summary: dict = {
        "updates": 0,
        "messages_processed": 0,
        "duplicates_skipped": 0,
        "mapped_leads": 0,
        "unmatched": 0,
    }
    if not isinstance(update, dict):
        return summary

    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        return summary
    summary["updates"] = 1

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return summary

    message_id = message.get("message_id")
    provider_id = f"tg:{chat_id}:{message_id}"[:255]
    existing = (
        await session.execute(
            sa_select(InboundMessage).where(InboundMessage.provider_message_id == provider_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        summary["duplicates_skipped"] += 1
        return summary

    text = _extract_text(message)
    msg_type = _message_type(message)
    intent, objection = classify_intent(text)
    buying = intent in _BUYING_INTENTS
    now_utc = datetime.now(UTC)

    rec = InboundMessage(
        id=uuid4(),
        lead_id=None,
        sender_number=str(chat_id)[:32],
        provider_message_id=provider_id,
        occurred_at=_timestamp(message.get("date")) or now_utc,
        message_type=msg_type,
        text=text[:4000] or None,
        payload_hash=hashlib.sha256(str(update).encode("utf-8")).hexdigest(),
        processing_status="received",
        intent=intent if intent != "UNKNOWN" else None,
        buying_signal=buying,
        objection=objection,
    )
    session.add(rec)
    await session.flush()
    summary["messages_processed"] += 1

    lead = await _lead_for_sender(session, chat_id, text)
    if lead is None:
        rec.processing_status = "unmatched"
        summary["unmatched"] += 1
        await session.flush()
        return summary

    rec.lead_id = lead.id
    rec.processing_status = "processed"
    before_status, after_status = _promote_lead(lead, rec.intent or "UNKNOWN", rec.buying_signal, rec.objection)
    session.add(LeadEvent(
        lead_id=lead.id,
        event_type="message_received",
        status_before=before_status,
        status_after=after_status,
        channel=CHANNEL,
        message=(rec.text or "non-text message")[:2000],
        note=(
            f"intent={rec.intent or 'UNKNOWN'} buying_signal={rec.buying_signal}"
            + (f" objection={rec.objection}" if rec.objection else "")
        ),
        created_at=now_utc,
    ))
    summary["mapped_leads"] += 1
    await session.flush()
    return summary
