"""Consult-assistant lead capture (Al-Narjis consultant out-of-band ``lead_qualification``).

A lightweight companion to ``/api/leads`` used only by the Smart Consultant
(System 2, ``/api/consult``). It mirrors the public capture pipeline (normalise →
de-duplicate → classify → score → persist → welcome email) so an assistant-detected
lead lands in the same canonical ``AcquisitionLead`` funnel, but it never touches
the existing lead-status logic or the public intake endpoint.
"""

from __future__ import annotations

from src.utils.logger import get_logger

logger = get_logger(__name__)


async def capture_consult_lead(session_factory, data: dict) -> dict:
    """Persist one qualified lead discovered by the consultant.

    Returns ``{"created": bool, "lead_id": str | None, "dedupe": bool}``. Never
    raises — failures are logged and swallowed so the chat reply is unaffected.
    """
    try:
        from src.services.lead_normalize import normalize_email, normalize_phone

        name = str(data.get("client_name") or "").strip() or None
        raw_phone = str(data.get("phone") or "").strip() or None
        phone = normalize_phone(raw_phone)
        email = normalize_email(str(data.get("email") or "").strip() or "")
        package = str(data.get("package") or "").strip() or None
        bottleneck = str(data.get("primary_bottleneck") or "").strip() or None
        score = str(data.get("qualification_score") or "").strip() or None

        if not (phone or email or name):
            return {"created": False, "lead_id": None, "dedupe": False}

        notes = bottleneck
        if score:
            notes = (bottleneck or "") + f"\n[qualification: {score}]" if bottleneck else f"[qualification: {score}]"

        from src.services.funnel_callback import open_callback
        from src.services.funnel_identity import resolve_lead

        async with session_factory() as session:
            resolved = await resolve_lead(
                session,
                email=email,
                phone=raw_phone,
                name=name,
                source="consult_assistant",
                message=notes,
                package=package,
            )
            lead = resolved["lead"]
            if lead is None:
                return {"created": False, "lead_id": None, "dedupe": False}
            if not resolved["created"]:
                await open_callback(session, lead, source="consult_assistant")
                await session.commit()
                logger.info("Consult lead already on file: %s", lead.id)
                return {"created": False, "lead_id": str(lead.id), "dedupe": True}
            await open_callback(session, lead, source="consult_assistant")
            await session.commit()
            lead_id = lead.id
            lead_email = lead.email
            lead_name = lead.contact_name or lead.company_name

    except Exception as exc:  # noqa: BLE001 — capture must never break the chat
        logger.error("Consult lead capture failed (%s)", type(exc).__name__)
        return {"created": False, "lead_id": None, "dedupe": False}

    if lead_email:
        try:
            from src.services import email_service
            sent = await email_service.send_welcome(lead_email, lead_name or "عميلنا العزيز")
            if sent:
                from src.services.lead_contact_record import record_acknowledged_email

                async with session_factory() as session:
                    await record_acknowledged_email(session, lead_id, kind="welcome")
                    await session.commit()
        except Exception as e:  # noqa: BLE001
            logger.warning("Welcome email for consult lead failed: %s", type(e).__name__)
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