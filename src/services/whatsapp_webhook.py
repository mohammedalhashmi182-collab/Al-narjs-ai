"""WhatsApp Business Cloud API inbound webhook handler.

Pipeline per inbound message:

  provider message
    -> signature verified (HMAC-SHA256, X-Hub-Signature-256)
    -> deduplicated by provider message id
    -> mapped to the canonical lead by normalized sender number
    -> appended as a LeadEvent + stored InboundMessage
    -> intent classified, buying signal / objection / opt-out detected
    -> lead promoted (conversation state) and the revenue queue reprioritized

Governance: opt-outs always flip the lead to ``DO_NOT_CONTACT`` and the sender
never messages them again. No raw payload is persisted — only a payload hash.
Secrets are never returned or logged.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
from datetime import datetime, timezone, UTC
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.models import AcquisitionLead, InboundMessage, LeadEvent, OutboundMessage

from .lead_normalize import normalize_phone

log = logging.getLogger(__name__)

CHANNEL = "whatsapp"

# --- Classification vocabulary -------------------------------------------------
INTENTS = (
    "INTERESTED",
    "QUESTION",
    "PRICE",
    "DEMO",
    "PROPOSAL",
    "READY_TO_BUY",
    "NOT_INTERESTED",
    "FOLLOW_UP_LATER",
    "OPT_OUT",
    "UNKNOWN",
)

# Intent keywords (Arabic + English). Matching is case-insensitive; Arabic
# letters are compared loosely (roughly normalized in ``_norm``).
_KEYWORDS: dict[str, list[str]] = {
    "OPT_OUT": [
        "لا ترسل", "لا تبعت", "ما تبعت", "تركوني", "اشيلوني", "أيقفوا", "ايقفوا",
        "بطلوا", "كفاية رسائل", "لا تزعجوني", "لست مهتم بالرسائل", "unsubscribe",
        "opt out", "opt-out", "stop messaging", "don't message", "لا اريد رسائل",
        "ابلغوا عن", "ارفعوني من القائمة", "ما ابي رسايل", "منعني",
    ],
    "READY_TO_BUY": [
        "ابغى", "ابغا", "ابي", "أبي", "اريد", "أريد", "عايز", "بدنا",
        "خلنا نبدأ", "نبدأ", "ابدأ", "ابدا", "أبدأ", "اتفقنا", "موافق",
        "سجلنا", "اشترك", "أشترى", "اشتري", "اشتركوا", "سووا لنا الاشتراك",
        "buy", "purchase", "subscribe", "start now", "we agree", "I want it",
        "نحتاج نبدأ", "جهزو لنا", "فعّلوا",
    ],
    "PRICE": [
        "كم السعر", "كم سعره", "بكم", "السعر", "سعر", "التكلفة", "كم تكلفة",
        "كم الثمن", "بكم تبدأ", "تسعير", "سعر الاشتراك", "price", "cost",
        "how much", "pricing", "كم الرسوم", "الأقساط",
    ],
    "DEMO": [
        "ارسلوا العرض", "ابعتوا العرض", "ارسل العرض", "ابعت العرض", "شوفوا العرض",
        "جرّب", "جرب", "نجرب", "ديمو", "demo", "عرض تجريبي", "التجربة",
        "أرسل لنا العرض", "جهزوا العرض", "ابعتوه", "نتعرف عليه",
    ],
    "PROPOSAL": [
        "عرض سعر", "عرض رسمي", "proposal", "كشف حساب", "عقد", "فقرة", "فاتورة",
        "ارسلوا مقترح", "مقترح", "نحتاج عرض", "بالعرض",
    ],
    "FOLLOW_UP_LATER": [
        "بعدين", "لاحقا", "لاحقاً", "وقت لاحق", "مشغول", "انشغل", "سأرجع لكم",
        "نشاور", "نرجع لك", "خلنا نفكر", "بدنا نفكر", "اررجع لكم", "after",
        "later", "busy", "come back", "we'll get back", "check later",
        "بعد شوية", "بعد فترة",
    ],
    "NOT_INTERESTED": [
        "لست مهتم", "مش مهتم", "مش فايدنا", "لا شكرا", "لا شكراً", "ما نحتاج",
        "ما نحتاجه", "مو محتاجين", "not interested", "no thanks", "لا نشكر",
        "شكرا، لا", "معندناش", "ليش ندفع", "مش حابين",
    ],
    "QUESTION": [
        "سؤال", "كيف", "شلون", "وش", "ممكن", "هل في", "هل عندكم", "كم مدة",
        "question", "how", "what do you", "وين", "فيه", "عندكم", "يعني",
    ],
    "INTERESTED": [
        "مهتم", "ممتاز", "رائع", "تمام", "حلو", "يعجبني", "عاجبني", "يناسب",
        "مناسب", "نفسنا", "بسعر مناسب", "ok", "great", "nice", "interested",
        "good", "يعطيك العافية", "تابعوا", "كملوا", "استمروا", "بس عندي سؤال",
    ],
}

# Intent matching priority — OPT_OUT wins over everything else.
_INTENT_ORDER = (
    "OPT_OUT",
    "READY_TO_BUY",
    "PRICE",
    "PROPOSAL",
    "DEMO",
    "NOT_INTERESTED",
    "FOLLOW_UP_LATER",
    "INTERESTED",
    "QUESTION",
    "UNKNOWN",
)

_BUYING_INTENTS = {"INTERESTED", "PRICE", "DEMO", "PROPOSAL", "READY_TO_BUY"}

_OBJECTIONS = {
    "price": ["غالي", "مكلف", "expensive", "كثير", "تكلفة عالية", "الميزانية", "ميزانيتنا", "باهظ"],
    "competitor": ["عندنا مزود", "مع المزود", "عندنا احد", "شريكنا", "competitor", "another vendor"],
    "timing": ["الوقت الحالي", "الحين مش مناسب", "not the right time", "هالسنة"],
    "decision": ["المدير مسافر", "بناخد رأي", "نشاور الشركاء", "decision maker"],
    "trust": ["وثوق", "التجربة الفعلية", "بدنا نتأكد", "trust", "proof"],
}

_NORM_RE = re.compile(r"[^\w\s]", re.UNICODE)


def _norm(text: str) -> str:
    """Light normalization for keyword matching (not a display form)."""
    out: list[str] = []
    for ch in text.lower():
        if ch in "أإآٱ":
            out.append("ا")
        elif ch in "ىئ":
            out.append("ي")
        elif ch == "ؤ":
            out.append("و")
        elif ch == "ة":
            out.append("ه")
        else:
            out.append(ch)
    return _NORM_RE.sub(" ", "".join(out)).strip()


def verify_webhook_signature(signature: Optional[str], raw_body: bytes) -> bool:
    """Validate ``X-Hub-Signature-256`` using the app secret (constant-time)."""
    secret = settings.whatsapp_app_secret
    if not secret or not signature:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def classify_intent(text: str) -> tuple[str, Optional[str]]:
    """Return ``(intent, objection_or_None)`` from free text."""
    text = _norm(str(text or "") or "")
    if not text:
        return "UNKNOWN", None

    for intent in _INTENT_ORDER:
        if intent == "UNKNOWN":
            return "UNKNOWN", _detect_objection(text)
        for kw in _KEYWORDS.get(intent, []):
            if kw in text:
                return intent, _detect_objection(text)
    return "UNKNOWN", _detect_objection(text)


def _detect_objection(text: str) -> Optional[str]:
    for obj, kws in _OBJECTIONS.items():
        if any(kw in text for kw in kws):
            return obj
    return None


# --- Lead mapping -------------------------------------------------------------

def _digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


async def _map_sender_to_lead(session: AsyncSession, sender: Any, wa_id: Any = None) -> Optional[AcquisitionLead]:
    """Find the canonical lead for an inbound WhatsApp sender."""
    norm = normalize_phone(sender) or normalize_phone(wa_id)
    candidates: list[Optional[str]] = [norm]
    hands = [sender, wa_id]
    for h in hands:
        n = normalize_phone(h)
        if n:
            candidates.append(n)

    seen: set[str] = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        lead = (
            await session.execute(
                sa_select(AcquisitionLead).where(AcquisitionLead.phone == cand).order_by(AcquisitionLead.created_at)
            )
        ).scalars().first()
        if lead is not None:
            return lead

    # Match by stored raw phone digits (leads imported with unparsed formats).
    digits = _digits(sender) or _digits(wa_id)
    if len(digits) >= 9:
        raw_rows = (
            await session.execute(
                sa_select(AcquisitionLead).where(
                    AcquisitionLead.phone_raw.is_not(None)
                )
            )
        ).scalars().all()
        for lead in raw_rows:
            if digits in _digits(lead.phone_raw):
                return lead
        phone_rows = (
            await session.execute(
                sa_select(AcquisitionLead).where(
                    AcquisitionLead.phone.is_not(None)
                )
            )
        ).scalars().all()
        for lead in phone_rows:
            if digits in _digits(lead.phone):
                return lead

    # Fall back to a lead that we recently messaged on this number.
    outbound = (
        await session.execute(
            sa_select(OutboundMessage)
            .where(OutboundMessage.phone.is_not(None))
            .order_by(OutboundMessage.created_at.desc())
            .limit(500)
        )
    ).scalars().all()
    for rec in outbound:
        if digits and digits in _digits(rec.phone) and rec.lead_id:
            lead = (
                await session.execute(
                    sa_select(AcquisitionLead).where(AcquisitionLead.id == rec.lead_id)
                )
            ).scalar_one_or_none()
            if lead is not None:
                return lead
    return None


# --- Processing ---------------------------------------------------------------

def _timestamp(ts: Any) -> Optional[datetime]:
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


async def _record_message(session: AsyncSession, *, sender: Any, wa_id: Any, message: dict, entry_hash: str) -> InboundMessage:
    msg_id = message.get("id") or uuid4()
    occurred = _timestamp(message.get("timestamp"))
    msg_type = message.get("type") or "unknown"
    text = ""
    text_body = (message.get("text") or {}).get("body")
    if isinstance(text_body, str):
        text = text_body
    media = None
    if msg_type != "text" and msg_type != "unknown":
        media = message.get(msg_type) or {}

    intent_raw = text
    if not intent_raw and isinstance(media, dict):
        intent_raw = (media.get("caption") or "")

    intent, objection = classify_intent(intent_raw)
    buying = intent in _BUYING_INTENTS

    rec = InboundMessage(
        id=uuid4(),
        lead_id=None,
        sender_number=str(sender or "")[:32] or None,
        provider_message_id=str(msg_id)[:255],
        occurred_at=occurred,
        message_type=msg_type[:20],
        text=text[:4000] or None,
        media_meta=media,
        payload_hash=entry_hash,
        processing_status="received",
        intent=intent if intent != "UNKNOWN" else None,
        buying_signal=buying,
        objection=objection,
    )
    session.add(rec)
    await session.flush()
    return rec


def _promote_lead(lead: AcquisitionLead, intent: str, buying: bool, objection: Optional[str], *, status_promote: bool = True) -> tuple[str, str]:
    """Return ``(status_before, status_after)``. Opt-out is unconditional."""
    before = lead.lead_status or "NEW"
    now_utc = datetime.now(timezone.utc)

    if intent == "OPT_OUT" or objection == "opted_out":
        lead.opt_out = True
        lead.buying_signal = False
        lead.last_reply_at = now_utc
        lead.intent = intent
        if before != "DO_NOT_CONTACT":
            lead.lead_status = "DO_NOT_CONTACT"
            return before, "DO_NOT_CONTACT"
        return before, before

    lead.last_reply_at = now_utc
    lead.intent = intent

    if buying:
        lead.buying_signal = True
        lead.priority_score = min(100, (lead.priority_score or 0) + 40)
        lead.priority = "HIGH"

    if not status_promote:
        return before, before

    mapping = {
        "READY_TO_BUY": "INTERESTED",
        "PRICE": "INTERESTED",
        "INTERESTED": "INTERESTED",
        "DEMO": "DEMO",
        "PROPOSAL": "PROPOSAL",
    }
    desired = mapping.get(intent)
    if desired:
        rank = {"NEW": 0, "READY": 1, "CONTACTED": 2, "REPLIED": 3, "INTERESTED": 4, "DEMO": 5, "PROPOSAL": 6}
        if rank.get(before, 0) < rank[desired]:
            lead.lead_status = desired
            return before, desired
        action_to = {"REPLIED": "REPLIED"}
        if intent not in _BUYING_INTENTS and before in ("NEW", "READY", "CONTACTED"):
            lead.lead_status = "REPLIED"
            return before, "REPLIED"
        return before, before
    if before in ("NEW", "READY", "CONTACTED"):
        lead.lead_status = "REPLIED"
        return before, "REPLIED"
    return before, before


async def process_inbound_payload(session: AsyncSession, payload: dict) -> dict:
    """Process one webhook body: status updates and inbound messages."""
    summary: dict = {"messages_processed": 0, "duplicates_skipped": 0, "status_updates": 0, "mapped_leads": 0, "unmatched": 0}
    now_utc = datetime.now(timezone.utc)

    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}

            # Delivery/read status updates on our outbound messages.
            for status_row in value.get("statuses") or []:
                mid = status_row.get("id")
                state = status_row.get("status")
                if mid and state:
                    from .whatsapp_sender import acknowledge_status

                    err = None
                    errors = status_row.get("errors")
                    if isinstance(errors, list) and errors:
                        err = str(errors[0].get("code") or errors[0].get("title") or "")[:50]
                    rec = await acknowledge_status(session, str(mid), str(state), error_code=err)
                    if rec is not None:
                        summary["status_updates"] += 1

            # Inbound messages.
            for message in value.get("messages") or []:
                if message.get("from") is None and value.get("contacts"):
                    message["from"] = (value["contacts"][0] or {}).get("wa_id")

                entry_hash = hashlib.sha256((str(message)).encode("utf-8")).hexdigest()
                msg_id = str(message.get("id") or "")

                if msg_id and msg_id != "None":
                    existing = (
                        await session.execute(
                            sa_select(InboundMessage).where(InboundMessage.provider_message_id == msg_id)
                        )
                    ).scalar_one_or_none()
                    if existing is not None:
                        summary["duplicates_skipped"] += 1
                        continue

                sender = message.get("from")
                wa_id = None
                parts = [p for p in (value.get("contacts") or []) if p]
                if parts:
                    wa_id = (parts[0] or {}).get("wa_id")

                rec = await _record_message(
                    session, sender=sender, wa_id=wa_id, message=message, entry_hash=entry_hash
                )
                summary["messages_processed"] += 1

                lead = await _map_sender_to_lead(session, sender, wa_id)
                if lead is None:
                    rec.processing_status = "unmatched"
                    summary["unmatched"] += 1
                    await session.flush()
                    continue

                rec.lead_id = lead.id
                rec.processing_status = "processed"
                before = lead.lead_status or "NEW"
                before_status, after_status = _promote_lead(
                    lead, rec.intent or "UNKNOWN", rec.buying_signal, rec.objection
                )
                session.add(LeadEvent(
                    lead_id=lead.id,
                    event_type="message_received",
                    status_before=before_status or before,
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


def webhook_disabled_reason() -> Optional[str]:
    if not settings.whatsapp_app_secret:
        return "WHATSAPP_APP_SECRET not configured"
    if not settings.whatsapp_webhook_verify_token:
        return "WHATSAPP_WEBHOOK_VERIFY_TOKEN not configured"
    return None


def verify_ok() -> bool:
    return webhook_disabled_reason() is None