"""Canonical lead identity.

``AcquisitionLead.id`` is the only customer id. Email, phone, the consult
capture and a legacy ``leads`` key are aliases. The same email or the same
phone always resolves to the same id. Two different people are not merged:
when the email and the phone already belong to two leads, the email lead is
returned and a conflict event is stored.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.services.lead_normalize import is_valid_email, normalize_email, normalize_phone
from src.utils.logger import get_logger

logger = get_logger(__name__)

SOURCE_EMAIL = "email"
SOURCE_PHONE = "phone"
SOURCE_LEGACY = "legacy_leads"


def canonical_email(value: str | None) -> str | None:
    if not is_valid_email(value):
        return None
    return normalize_email(value)


def canonical_phone(value: str | None) -> str | None:
    return normalize_phone(value)


async def _alias(session, source: str, key: str):
    from src.models.funnel import LeadAlias

    return (
        await session.execute(
            select(LeadAlias).where(LeadAlias.source == source, LeadAlias.external_key == key)
        )
    ).scalar_one_or_none()


async def _lead_by_alias(session, source: str, key: str):
    from src.models import AcquisitionLead

    row = await _alias(session, source, key)
    if row is None:
        return None
    return await session.get(AcquisitionLead, row.lead_id)


async def _append_event(session, lead_id, event_type: str, *, idempotency_key: str, evidence_ref: str | None = None, payload: dict | None = None) -> None:
    from src.models.funnel import FunnelEvent

    existing = (
        await session.execute(select(FunnelEvent).where(FunnelEvent.idempotency_key == idempotency_key))
    ).scalar_one_or_none()
    if existing is not None:
        return
    session.add(FunnelEvent(
        lead_id=lead_id,
        event_type=event_type,
        idempotency_key=idempotency_key,
        evidence_ref=evidence_ref,
        payload=payload or {},
        actor="funnel",
    ))


async def _attach_alias(session, lead_id, source: str, key: str) -> bool:
    """Insert the alias. Return False when the key already belongs to someone."""
    from src.models.funnel import LeadAlias

    current = await _alias(session, source, key)
    if current is not None:
        return current.lead_id == lead_id
    try:
        async with session.begin_nested():
            session.add(LeadAlias(lead_id=lead_id, source=source, external_key=key))
            await session.flush()
    except IntegrityError:
        return False
    return True


async def resolve_lead(
    session,
    *,
    email: str | None = None,
    phone: str | None = None,
    name: str | None = None,
    source: str = "website",
    message: str | None = None,
    package: str | None = None,
    segment: str | None = None,
    segment_reason: str | None = None,
    priority: str | None = None,
    priority_score: int | None = None,
    priority_reason: list | None = None,
) -> dict:
    """Return ``{lead, created, conflict}``. Creates a lead only when needed."""
    from src.models import AcquisitionLead, LeadEvent
    from src.services.lead_priority import score_lead
    from src.services.lead_segmentation import classify, suggest_package

    email_key = canonical_email(email)
    phone_key = canonical_phone(phone)
    display = (name or "").strip() or None

    by_email = await _lead_by_alias(session, SOURCE_EMAIL, email_key) if email_key else None
    if by_email is None and email_key:
        by_email = (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.email == email_key).limit(1))
        ).scalar_one_or_none()
    by_phone = await _lead_by_alias(session, SOURCE_PHONE, phone_key) if phone_key else None
    if by_phone is None and phone_key:
        by_phone = (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.phone == phone_key).limit(1))
        ).scalar_one_or_none()

    conflict = False
    if by_email is not None and by_phone is not None and by_email.id != by_phone.id:
        conflict = True
        lead = by_email
    else:
        lead = by_email or by_phone

    created = False
    if lead is None:
        if not (email_key or phone_key or display):
            return {"lead": None, "created": False, "conflict": False}
        if segment is None:
            segment, segment_reason = classify(display or "")
        if priority is None or priority_score is None:
            scored = score_lead(
                company_name=display or "",
                phone=phone_key,
                email=email_key,
                segment=segment or "unknown",
            )
            priority = priority or scored.priority
            priority_score = scored.score if priority_score is None else priority_score
            priority_reason = priority_reason if priority_reason is not None else scored.reasons
        lead = AcquisitionLead(
            company_name=display or "عميل محتمل",
            contact_name=display,
            phone=phone_key,
            phone_raw=(phone or None),
            email=email_key,
            source=source,
            segment=segment or "unknown",
            segment_reason=segment_reason,
            suggested_package=package or suggest_package(segment or "unknown"),
            lead_status="NEW",
            priority=priority or "LOW",
            priority_score=int(priority_score or 0),
            priority_reason=priority_reason or [],
            notes=message,
        )
        session.add(lead)
        await session.flush()
        session.add(LeadEvent(
            lead_id=lead.id,
            event_type="captured",
            status_after="NEW",
            channel=source,
            message=message,
        ))
        created = True
        await _append_event(
            session,
            lead.id,
            "identity_created",
            idempotency_key=f"identity:{lead.id}",
            payload={"source": source},
        )
    else:
        if email_key and not lead.email:
            taken = await _lead_by_alias(session, SOURCE_EMAIL, email_key)
            if taken is None:
                other = (
                    await session.execute(
                        select(AcquisitionLead.id).where(AcquisitionLead.email == email_key, AcquisitionLead.id != lead.id).limit(1)
                    )
                ).scalar_one_or_none()
                if other is None:
                    lead.email = email_key
        if phone_key and not lead.phone and not conflict:
            lead.phone = phone_key

    if email_key:
        attached = await _attach_alias(session, lead.id, SOURCE_EMAIL, email_key)
        if not attached:
            conflict = True
    if phone_key and not conflict:
        attached = await _attach_alias(session, lead.id, SOURCE_PHONE, phone_key)
        if not attached:
            conflict = True
    if conflict:
        await _append_event(
            session,
            lead.id,
            "identity_conflict",
            idempotency_key=f"identity-conflict:{lead.id}:{email_key or ''}:{phone_key or ''}",
            payload={"kept": "email" if email_key else "phone"},
        )
    logger.info("Resolved canonical lead %s created=%s conflict=%s", lead.id, created, conflict)
    return {"lead": lead, "created": created, "conflict": conflict}


async def bind_legacy_lead(session, legacy_id: str, *, email: str | None = None, phone: str | None = None, name: str | None = None) -> dict:
    """Point a legacy ``leads`` primary key at the canonical acquisition lead.

    Does not read or write the legacy table. The caller passes the key.
    """
    key = (legacy_id or "").strip()
    if not key:
        return {"lead": None, "created": False}
    existing = await _lead_by_alias(session, SOURCE_LEGACY, key)
    if existing is not None:
        return {"lead": existing, "created": False, "conflict": False}
    resolved = await resolve_lead(session, email=email, phone=phone, name=name, source="legacy_leads")
    lead = resolved["lead"]
    if lead is None:
        return resolved
    await _attach_alias(session, lead.id, SOURCE_LEGACY, key)
    await _append_event(
        session,
        lead.id,
        "legacy_bound",
        idempotency_key=f"legacy:{key}",
        evidence_ref=key,
    )
    resolved["bound"] = True
    return resolved


async def find_by_any(session, *, email: str | None = None, phone: str | None = None):
    """Read-only lookup used by reconciliation. Does not create a lead."""
    from src.models import AcquisitionLead

    email_key = canonical_email(email)
    phone_key = canonical_phone(phone)
    if email_key:
        found = await _lead_by_alias(session, SOURCE_EMAIL, email_key)
        if found is not None:
            return found
        found = (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.email == email_key).limit(1))
        ).scalar_one_or_none()
        if found is not None:
            return found
    if phone_key:
        found = await _lead_by_alias(session, SOURCE_PHONE, phone_key)
        if found is not None:
            return found
        return (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.phone == phone_key).limit(1))
        ).scalar_one_or_none()
    return None


async def touch_aliases_for_existing(session, lead) -> None:
    """Backfill aliases for a lead that already exists. No status change."""
    if lead.email:
        key = canonical_email(lead.email)
        if key:
            await _attach_alias(session, lead.id, SOURCE_EMAIL, key)
    if lead.phone:
        key = canonical_phone(lead.phone)
        if key:
            await _attach_alias(session, lead.id, SOURCE_PHONE, key)
