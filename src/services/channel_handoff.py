"""Open a human follow-up when a channel message has no lead, or shows buying intent.

The lead status machine is left to the existing promoter. This module only
creates the CRM row for an unknown WhatsApp sender, records the source, and
queues one owner task. It does not send a message.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AcquisitionLead, LeadEvent, Task
from src.services.lead_normalize import normalize_phone


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _merge(lead: AcquisitionLead, key: str, value: dict) -> None:
    raw = dict(lead.raw_data or {})
    raw[key] = value
    lead.raw_data = raw


async def ensure_whatsapp_lead(
    session: AsyncSession, *, sender: str, name: Optional[str]
) -> tuple[Optional[AcquisitionLead], bool]:
    """Create a CRM lead for a sender we could not match. Returns ``(lead, created)``."""
    phone = normalize_phone(sender)
    if not phone:
        return None, False
    key = f"whatsapp:{phone}"
    existing = (
        await session.execute(select(AcquisitionLead).where(AcquisitionLead.dedup_key == key))
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False
    label = (name or "").strip()[:80] or f"واتساب {phone[-4:]}"
    lead = AcquisitionLead(
        company_name=label[:512],
        contact_name=(name or "").strip()[:512] or None,
        phone=phone,
        phone_raw=str(sender or "")[:64] or None,
        source="whatsapp",
        segment="unknown",
        lead_status="NEW",
        priority="MEDIUM",
        sales_representative="owner",
        dedup_key=key,
    )
    session.add(lead)
    await session.flush()
    session.add(LeadEvent(
        lead_id=lead.id,
        event_type="captured",
        channel="whatsapp",
        status_before=None,
        status_after="NEW",
        note="source=whatsapp",
    ))
    return lead, True


async def queue_human_handoff(
    session: AsyncSession,
    lead: AcquisitionLead,
    *,
    channel: str,
    reason: str,
    message: str,
) -> bool:
    """Queue one owner follow-up. Returns whether the task row was created.

    Opted-out leads are not queued. Lead status is not changed here.
    """
    if lead.opt_out or (lead.lead_status or "") == "DO_NOT_CONTACT":
        return False
    now = _now()
    lead.next_followup_at = now
    lead.followup_stage = "human_handoff"
    if not (lead.sales_representative or "").strip():
        lead.sales_representative = "owner"
    if reason == "high_intent":
        lead.priority = "HIGH"
    reasons = list(lead.priority_reason or [])
    note = "تحويل بشري من واتساب" if channel == "whatsapp" else f"تحويل بشري من {channel}"
    if note not in reasons:
        reasons.append(note)
        lead.priority_reason = reasons
    _merge(lead, "handoff", {"channel": channel, "reason": reason, "at": now.isoformat()})
    session.add(LeadEvent(
        lead_id=lead.id,
        event_type="human_handoff",
        channel=channel[:20],
        status_before=lead.lead_status,
        status_after=lead.lead_status,
        message=(message or "")[:500] or None,
        note=f"reason={reason}",
    ))
    key = f"handoff:{channel}:{lead.id}"
    existing = (await session.execute(select(Task).where(Task.key == key))).scalar_one_or_none()
    if existing is not None:
        existing.evidence = {**(existing.evidence or {}), "reason": reason, "at": now.isoformat()}
        return False
    session.add(Task(
        key=key,
        title=f"متابعة بشرية — {channel}"[:512],
        description=(message or "رسالة واردة بلا رد آلي")[:4000],
        source="channel_handoff",
        status="escalated",
        priority=200 if reason == "high_intent" else 160,
        owner_agent="customer_manager",
        department="customer_service",
        evidence={"handler": "human_followup", "channel": channel, "reason": reason, "lead_id": str(lead.id)},
        learning="المتابعة على المالك. لم يُرسل رد آلي.",
        due_at=now,
    ))
    return True
