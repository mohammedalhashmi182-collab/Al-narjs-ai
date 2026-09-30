"""Consult-assistant lead capture (KarmaAI out-of-band ``lead_qualification``).

A lightweight companion to ``/api/leads`` used only by the Smart Consultant
(System 2, ``/api/consult``). It mirrors the public capture pipeline (normalise →
de-duplicate → classify → score → persist → welcome email) so an assistant-detected
lead lands in the same canonical ``AcquisitionLead`` funnel, but it never touches
the existing lead-status logic or the public intake endpoint.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from src.utils.logger import get_logger

logger = get_logger(__name__)


async def capture_consult_lead(session_factory, data: dict) -> dict:
    """Persist one qualified lead discovered by the consultant.

    Returns ``{"created": bool, "lead_id": str | None, "dedupe": bool}``. Never
    raises — failures are logged and swallowed so the chat reply is unaffected.
    """
    try:
        from src.models import AcquisitionLead, LeadEvent
        from src.services.lead_normalize import normalize_email, normalize_phone
        from src.services.lead_priority import score_lead
        from src.services.lead_segmentation import classify, suggest_package

        name = str(data.get("client_name") or "").strip() or None
        raw_phone = str(data.get("phone") or "").strip() or None
        phone = normalize_phone(raw_phone)
        email = normalize_email(str(data.get("email") or "").strip() or "")
        package = str(data.get("package") or "").strip() or None
        bottleneck = str(data.get("primary_bottleneck") or "").strip() or None
        score = str(data.get("qualification_score") or "").strip() or None

        if not (phone or email or name):
            return {"created": False, "lead_id": None, "dedupe": False}

        async with session_factory() as session:
            existing = None
            if phone or email:
                conds = []
                if phone:
                    conds.append(AcquisitionLead.phone == phone)
                if email:
                    conds.append(AcquisitionLead.email == email)
                existing = (
                    await session.execute(select(AcquisitionLead).where(*conds).limit(1))
                ).scalar_one_or_none()

            if existing is not None:
                logger.info("Consult lead skipped (already on file): %s", existing.id)
                return {"created": False, "lead_id": str(existing.id), "dedupe": True}

            segment, _ = classify(name or "")
            priority = score_lead(
                company_name=name or "",
                phone=phone,
                email=email,
                segment=segment,
            )
            notes = bottleneck
            if score:
                notes = (bottleneck or "") + f"\n[qualification: {score}]" if bottleneck else f"[qualification: {score}]"

            lead = AcquisitionLead(
                company_name=name or "عميل محتمل",
                contact_name=name,
                phone=phone,
                phone_raw=raw_phone,
                email=email,
                source="consult_assistant",
                segment=segment,
                suggested_package=package or suggest_package(segment),
                lead_status="NEW",
                priority=priority.priority,
                priority_score=priority.score,
                priority_reason=priority.reasons,
                notes=notes,
            )
            session.add(lead)
            await session.flush()
            session.add(LeadEvent(
                lead_id=lead.id,
                event_type="captured",
                status_after="NEW",
                channel="assistant",
                message=bottleneck,
            ))
            await session.commit()
            await session.refresh(lead)
            lead_id = lead.id
            lead_email = lead.email
            lead_name = lead.contact_name or lead.company_name

    except Exception as e:  # noqa: BLE001 — capture must never break the chat
        logger.error("Consult lead capture failed: %s", e)
        return {"created": False, "lead_id": None, "dedupe": False}

    if lead_email:
        try:
            from src.services import email_service
            await email_service.send_welcome(lead_email, lead_name or "عميلنا العزيز")
        except Exception as e:  # noqa: BLE001
            logger.warning("Welcome email for consult lead failed: %s", e)
        try:
            from src.main import _schedule_lead_followups
            try:
                await _schedule_lead_followups(str(lead_id), lead_email, lead_name)
            except Exception as e:  # noqa: BLE001
                logger.warning("Follow-up scheduling skipped: %s", e)
        except ImportError:
            pass

    logger.info("Consult lead captured: %s", lead_id)
    return {"created": True, "lead_id": str(lead_id), "dedupe": False}