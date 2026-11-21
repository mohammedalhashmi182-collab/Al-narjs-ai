"""Open a CRM case when the website or the consult chat receives a person.

The case stores the next step, the specialist who owns it, and the SLA.
It does not change ``lead_status`` and it does not send a message.
"""

from __future__ import annotations

import re
from datetime import timedelta

from sqlalchemy import select

from src.services.agent_dispatch import choose_agent, open_task_counts
from src.services.funnel_identity import resolve_lead
from src.services.funnel_messages import utcnow
from src.services.lead_normalize import is_valid_email, normalize_phone
from src.utils.logger import get_logger

logger = get_logger(__name__)

SLA_HOURS = 4
_EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?:\+?966|00966|0)?5\d{8}")

_NEXT_STEP = {
    "website": "راجع طلب الموقع، ثبّت الاحتياج، وجه الرد للمالك قبل أي إرسال.",
    "consult_assistant": "راجع الاستشارة، ثبّت الاحتياج، وجه الرد للمالك قبل أي إرسال.",
    "support": "راجع سؤال خدمة العملاء ورد خلال مهلة الخدمة.",
}


def _kind_for(source: str) -> str:
    if source == "support":
        return "customer_service"
    return "sales"


async def _consent(session, lead_id, channel: str, status: str, evidence_ref: str) -> None:
    from src.models.funnel import LeadConsent

    session.add(LeadConsent(
        lead_id=lead_id,
        channel=channel,
        status=status,
        evidence_ref=evidence_ref[:255],
    ))


async def latest_consent(session, lead_id, channel: str) -> str | None:
    from src.models.funnel import LeadConsent

    row = (
        await session.execute(
            select(LeadConsent)
            .where(LeadConsent.lead_id == lead_id, LeadConsent.channel == channel)
            .order_by(LeadConsent.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return row.status if row is not None else None


async def outreach_blocked(session, lead, *, purpose: str) -> str | None:
    """Return a reason when a new send must not be queued. None means allowed."""
    if getattr(lead, "opt_out", False):
        return "opt_out"
    email_choice = await latest_consent(session, lead.id, "email")
    if email_choice == "opt_out":
        return "opt_out"
    if purpose == "marketing":
        if email_choice == "granted":
            return None
        marketing = await latest_consent(session, lead.id, "marketing")
        if marketing == "granted":
            return None
        return "marketing_consent_missing"
    if purpose == "inquiry":
        inquiry = await latest_consent(session, lead.id, "inquiry")
        if inquiry == "granted":
            return None
        return "inquiry_consent_missing"
    return "purpose_not_allowed"


async def open_callback(
    session,
    lead,
    *,
    source: str,
    consent_marketing: bool = False,
) -> dict:
    """Create the case once. A repeat call returns the same row."""
    from src.models.automation import LeadPipeline
    from src.models.funnel import FunnelCallback, FunnelEvent

    existing = (
        await session.execute(select(FunnelCallback).where(FunnelCallback.lead_id == lead.id))
    ).scalar_one_or_none()
    if existing is None:
        kind = _kind_for(source)
        owner = choose_agent(kind, await open_task_counts(session))
        due = utcnow() + timedelta(hours=SLA_HOURS)
        existing = FunnelCallback(
            lead_id=lead.id,
            source=source,
            next_step=_NEXT_STEP.get(source, _NEXT_STEP["website"]),
            owner_agent=owner,
            work_kind=kind,
            sla_due_at=due,
            status="open",
        )
        session.add(existing)
        await session.flush()
        session.add(FunnelEvent(
            lead_id=lead.id,
            event_type="callback_opened",
            idempotency_key=f"callback:{lead.id}",
            channel=source,
            actor="funnel",
            evidence_ref=str(existing.id),
            payload={"owner_agent": owner, "work_kind": kind},
        ))
        pipe = await session.get(LeadPipeline, lead.id)
        if pipe is None:
            session.add(LeadPipeline(
                lead_id=lead.id,
                channel="website" if source == "website" else "consult",
                recipient=(lead.email or lead.phone or "")[:64] or None,
                stage="new",
                history=[{"stage": "new", "at": utcnow().isoformat(), "note": "callback"}],
            ))
        await _consent(session, lead.id, "inquiry", "granted", f"callback:{lead.id}")
    if consent_marketing:
        await _consent(session, lead.id, "email", "granted", f"callback-consent:{lead.id}")
    logger.info("Funnel callback open for lead %s source=%s", lead.id, source)
    return public_callback(existing)


def public_callback(row) -> dict:
    return {
        "lead_id": str(row.lead_id),
        "source": row.source,
        "next_step": row.next_step,
        "owner_agent": row.owner_agent,
        "work_kind": row.work_kind,
        "sla_due_at": row.sla_due_at.isoformat() if row.sla_due_at else None,
        "status": row.status,
    }


async def open_website_case(session, *, name, email, phone, message, package, segment, segment_reason, priority, priority_score, priority_reason, consent_marketing: bool = False, attribution: dict | None = None) -> dict:
    resolved = await resolve_lead(
        session,
        email=email,
        phone=phone,
        name=name,
        source="website",
        message=message,
        package=package,
        segment=segment,
        segment_reason=segment_reason,
        priority=priority,
        priority_score=priority_score,
        priority_reason=priority_reason,
        attribution=attribution,
    )
    lead = resolved["lead"]
    if lead is None:
        return {"lead": None, "created": False, "callback": None}
    callback = await open_callback(session, lead, source="website", consent_marketing=consent_marketing)
    return {"lead": lead, "created": resolved["created"], "callback": callback, "conflict": resolved["conflict"]}


def contacts_in_text(text: str) -> dict:
    """Pull an email and a Saudi mobile out of a chat turn. Nothing else."""
    raw = text or ""
    email = None
    for match in _EMAIL_RE.findall(raw):
        if is_valid_email(match) and match.lower() != "alnarjisai@gmail.com":
            email = match
            break
    phone = None
    compact = re.sub(r"[\s\-]", "", raw)
    found = _PHONE_RE.search(compact)
    if found and normalize_phone(found.group(0)):
        phone = found.group(0)
    return {"email": email, "phone": phone}


async def note_consult_turn(session_factory, history: list[dict]) -> dict | None:
    """If the visitor typed a phone or email, open the same CRM case. Never raises."""
    try:
        last = next((m.get("content") or "" for m in reversed(history) if m.get("role") == "user"), "")
        found = contacts_in_text(last)
        if not (found["email"] or found["phone"]):
            return None
        async with session_factory() as session:
            resolved = await resolve_lead(
                session,
                email=found["email"],
                phone=found["phone"],
                source="consult_assistant",
                message=None,
            )
            lead = resolved["lead"]
            if lead is None:
                return None
            callback = await open_callback(session, lead, source="consult_assistant")
            alert = None
            from src.services.hot_lead import schedule_alert, stamp_hot, trial_requested

            if trial_requested(last):
                alert = stamp_hot(lead, "trial", excerpt=last)
            await session.commit()
            schedule_alert(alert)
        logger.info("Consult turn opened callback for lead %s", lead.id)
        return {"lead_id": str(lead.id), "created": resolved["created"], "callback": callback}
    except Exception as exc:  # noqa: BLE001 - the chat reply must still be returned
        logger.warning("Consult callback skipped (%s)", type(exc).__name__)
        return None
