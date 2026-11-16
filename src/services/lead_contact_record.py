"""Record that an outbound email was acknowledged by the provider.

This stamps ``last_contacted_at`` and appends a lead event. It does not change
``lead_status`` or ``outreach_status`` — those transitions stay with the
existing owner-controlled CRM routes.

Mailbox mail sent outside this app (the company Gmail UI) is not visible here.
Reading that mailbox and writing it back needs a separate owner decision.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from src.utils.logger import get_logger

logger = get_logger(__name__)


async def record_acknowledged_email(session, lead_id, *, kind: str) -> bool:
    """Return True when the lead exists and the contact stamp was applied."""
    from src.models import AcquisitionLead, LeadEvent

    if not lead_id:
        return False
    try:
        uid = lead_id if isinstance(lead_id, UUID) else UUID(str(lead_id))
    except (TypeError, ValueError):
        return False
    lead = await session.get(AcquisitionLead, uid)
    if lead is None:
        return False
    status = lead.lead_status
    lead.last_contacted_at = datetime.now(UTC)
    session.add(
        LeadEvent(
            lead_id=lead.id,
            event_type="email_acknowledged",
            channel="email",
            note=(kind or "email")[:50],
            status_before=status,
            status_after=status,
        )
    )
    logger.info("Recorded acknowledged email for lead %s kind=%s", lead.id, (kind or "email")[:50])
    return True
