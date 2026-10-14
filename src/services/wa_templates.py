"""WhatsApp message templates for messages outside the 24-hour customer-service window.

Meta only delivers free-form text within 24 hours of the customer's last
inbound message. Outside that window a pre-approved template is required.

``send_business_initiated`` picks the path:

1. inside the 24h window            -> plain text through ``whatsapp_sender``
2. outside, template ``approved``   -> template message through the Cloud API
3. otherwise (no approved template, WhatsApp not configured, or the send
   failed)                          -> fallback: a queued ``wa.me`` link for the
   owner plus a Telegram War Room note. Nothing is marked sent without an ack.

``DEFAULT_TEMPLATES`` is the list to submit in Meta Business Manager; see
``docs/whatsapp-templates.md``. Their status starts as ``draft`` and is only
switched to ``approved`` by the owner once Meta approves each one.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import InboundMessage, OutboundMessage
from src.models.ops import TEMPLATE_STATUSES, WhatsAppTemplate

log = logging.getLogger(__name__)

WINDOW = timedelta(hours=24)
FALLBACK_STATUS = "awaiting_manual"

# name -> definition. Bodies use Meta's {{1}}, {{2}} positional parameters.
DEFAULT_TEMPLATES: dict[str, dict] = {
    "renewal_reminder_ar": {
        "purpose": "renewal", "category": "UTILITY", "language": "ar",
        "body": "مرحباً {{1}}، اشتراكك في باقة {{2}} لدى النرجس للذكاء الاصطناعي ينتهي في {{3}}. "
                "رابط فاتورة التجديد: {{4}}",
    },
    "followup_ar": {
        "purpose": "followup", "category": "MARKETING", "language": "ar",
        "body": "مرحباً {{1}}، نتابع معك بخصوص طلبك لدى النرجس للذكاء الاصطناعي. "
                "هل تحب نكمل؟ رد على هذه الرسالة وبنساعدك.",
    },
    "payment_link_ar": {
        "purpose": "payment_link", "category": "UTILITY", "language": "ar",
        "body": "مرحباً {{1}}، هذا رابط الدفع الآمن لباقة {{2}}: {{3}}",
    },
    "weekly_report_ar": {
        "purpose": "weekly_report", "category": "UTILITY", "language": "ar",
        "body": "مرحباً {{1}}، تقريرك الأسبوعي من النرجس للذكاء الاصطناعي جاهز: {{2}} محادثة هذا الأسبوع. "
                "رد على هذه الرسالة لنرسل لك التفاصيل.",
    },
}


def param_count(body: str) -> int:
    n = 0
    while "{{" + str(n + 1) + "}}" in body:
        n += 1
    return n


async def seed_defaults(session: AsyncSession) -> int:
    """Insert missing default templates as ``draft``. Never overwrites an existing status."""
    added = 0
    for name, d in DEFAULT_TEMPLATES.items():
        if await session.get(WhatsAppTemplate, name) is None:
            session.add(WhatsAppTemplate(name=name, language=d["language"], category=d["category"],
                                         purpose=d["purpose"], body=d["body"],
                                         param_count=param_count(d["body"]), status="draft"))
            added += 1
    await session.flush()
    return added


async def set_status(session: AsyncSession, name: str, status: str) -> WhatsAppTemplate:
    if status not in TEMPLATE_STATUSES:
        raise ValueError("unknown status")
    row = await session.get(WhatsAppTemplate, name)
    if row is None:
        raise LookupError(name)
    row.status = status
    await session.flush()
    return row


async def approved_for(session: AsyncSession, purpose: str) -> WhatsAppTemplate | None:
    return (await session.execute(
        select(WhatsAppTemplate).where(WhatsAppTemplate.purpose == purpose,
                                       WhatsAppTemplate.status == "approved").limit(1)
    )).scalar_one_or_none()


def _digits(phone: Any) -> str:
    return "".join(ch for ch in str(phone or "") if ch.isdigit())


async def last_inbound_at(session: AsyncSession, phone: Any) -> datetime | None:
    digits = _digits(phone)
    if not digits:
        return None
    tail = digits[-9:]
    rows = (await session.execute(
        select(InboundMessage.sender_number, func.max(InboundMessage.occurred_at), func.max(InboundMessage.created_at))
        .where(InboundMessage.sender_number.like(f"%{tail}"))
        .group_by(InboundMessage.sender_number)
    )).all()
    best = None
    for _num, occurred, created in rows:
        ts = occurred or created
        if ts is not None and ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if ts and (best is None or ts > best):
            best = ts
    return best


async def within_window(session: AsyncSession, phone: Any, now: datetime | None = None) -> bool:
    last = await last_inbound_at(session, phone)
    return bool(last and (now or datetime.now(UTC)) - last < WINDOW)


def build_template_payload(to: str, tpl: WhatsAppTemplate, params: list[str]) -> dict:
    """Cloud API template payload. Never contains credentials."""
    payload = {
        "messaging_product": "whatsapp",
        "to": _digits(to),
        "type": "template",
        "template": {"name": tpl.name, "language": {"code": tpl.language}},
    }
    if tpl.param_count:
        values = [str(p)[:1000] for p in (params or [])][: tpl.param_count]
        values += ["-"] * (tpl.param_count - len(values))
        payload["template"]["components"] = [
            {"type": "body", "parameters": [{"type": "text", "text": v} for v in values]}
        ]
    return payload


async def _post_template(payload: dict) -> dict:
    """POST through the same gateway as ``whatsapp_sender`` (seam for tests)."""
    import httpx

    from src.services import whatsapp_sender

    url, headers = whatsapp_sender._gateway_endpoint()
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            code = None
            try:
                code = ((r.json() or {}).get("error") or {}).get("code")
            except Exception:  # noqa: BLE001
                pass
            return {"ok": False, "status_code": r.status_code, "error_code": str(code) if code else None}
        mid = ((r.json().get("messages") or [{}])[0].get("id")) or None
        return {"ok": True, "provider_message_id": mid}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error_code": "network", "error": type(exc).__name__}


def _fill(body: str, params: list[str]) -> str:
    for i, p in enumerate(params or [], start=1):
        body = body.replace("{{" + str(i) + "}}", str(p))
    return body


async def _fallback(session: AsyncSession, *, phone: Any, text: str, lead_id: Any, purpose: str, reason: str) -> dict:
    from src.services import ops_monitor, whatsapp_sender

    session.add(OutboundMessage(
        id=uuid4(), lead_id=lead_id, channel="whatsapp", phone=(str(phone or ""))[:32] or None,
        text=text, status=FALLBACK_STATUS, message_type="text", provider="wa.me",
        error=reason[:500], wa_me_link=whatsapp_sender._wa_me_link(phone, text),
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    ))
    await session.flush()
    await ops_monitor.alert_owner(
        f"wa-fallback:{purpose}",
        f"📨 رسالة واتساب ({purpose}) تحتاج إرسالاً يدوياً: {reason}. تجدها في طابور الرسائل بحالة {FALLBACK_STATUS}.",
        cooldown=600,
    )
    return {"ok": False, "path": "fallback", "reason": reason}


async def send_business_initiated(
    session: AsyncSession, *, phone: Any, purpose: str, text: str,
    params: list[str] | None = None, lead_id: Any = None, now: datetime | None = None,
) -> dict:
    """Deliver a business-initiated WhatsApp message by the right path (see module doc)."""
    from src.services import whatsapp_sender

    if not _digits(phone):
        return {"ok": False, "path": "none", "reason": "no phone"}
    if not whatsapp_sender.is_enabled():
        return await _fallback(session, phone=phone, text=text, lead_id=lead_id, purpose=purpose,
                               reason="WhatsApp Cloud API not configured")
    if await within_window(session, phone, now):
        res = await whatsapp_sender.send_now(session, lead_id=lead_id, phone=phone, text=text)
        if res.get("ok") or res.get("status") == "sent":
            return {"ok": True, "path": "session_text"}
        return await _fallback(session, phone=phone, text=text, lead_id=lead_id, purpose=purpose,
                               reason=f"text send failed ({res.get('error_code') or 'error'})")
    tpl = await approved_for(session, purpose)
    if tpl is None:
        return await _fallback(session, phone=phone, text=text, lead_id=lead_id, purpose=purpose,
                               reason=f"outside 24h window and no approved template for {purpose}")
    params = params or []
    res = await _post_template(build_template_payload(str(phone), tpl, params))
    now_ = datetime.now(UTC)
    session.add(OutboundMessage(
        id=uuid4(), lead_id=lead_id, channel="whatsapp", phone=str(phone)[:32],
        text=_fill(tpl.body, params), status="sent" if res.get("ok") else "failed",
        provider="meta_cloud", message_type="template",
        provider_message_id=(str(res.get("provider_message_id"))[:255] if res.get("provider_message_id") else None),
        acknowledged=bool(res.get("ok")), acknowledged_at=now_ if res.get("ok") else None,
        sent_at=now_ if res.get("ok") else None, error_code=res.get("error_code"),
        created_at=now_, updated_at=now_,
    ))
    await session.flush()
    if res.get("ok"):
        return {"ok": True, "path": "template", "template": tpl.name}
    return await _fallback(session, phone=phone, text=text, lead_id=lead_id, purpose=purpose,
                           reason=f"template {tpl.name} send failed ({res.get('error_code') or 'error'})")


def params_from_text(purpose: str, text: str) -> list[str]:
    """Best-effort template parameters for a draft written as free text."""
    import re

    if purpose == "payment_link":
        url = re.search(r"https?://\S+", text or "")
        return ["عميلنا", "المختارة", url.group(0) if url else "-"]
    return ["عميلنا"]
