"""Controlled campaign batches.

A campaign is a deliberately small, prioritized, human-approved batch — never a
mass-send list. Building a batch only prepares drafts and moves leads to
``READY``; nothing is sent automatically.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import func, select

from src.models import AcquisitionLead, Campaign, CampaignLead
from src.services.lead_normalize import is_valid_email, is_valid_phone
from src.services.lead_outreach import generate_message

CAMPAIGN_DIR = Path(__file__).resolve().parents[2] / "data" / "campaigns"
DEFAULT_BATCH_SIZE = 200


async def next_batch_no(session) -> int:
    current = (await session.execute(select(func.max(Campaign.batch_no)))).scalar_one_or_none()
    return (current or 0) + 1


async def build_campaign(
    session,
    *,
    size: int = DEFAULT_BATCH_SIZE,
    name: Optional[str] = None,
    batch_no: Optional[int] = None,
) -> Campaign:
    """Create the next prioritized batch of leads ready for outreach."""
    if batch_no is None:
        batch_no = await next_batch_no(session)

    already = select(CampaignLead.lead_id)
    query = (
        select(AcquisitionLead)
        .where(AcquisitionLead.lead_status == "NEW")
        .where(AcquisitionLead.priority.in_(("HIGH", "MEDIUM")))
        .where(~AcquisitionLead.id.in_(already))
        .order_by(AcquisitionLead.priority_score.desc(), AcquisitionLead.company_name)
    )
    candidates = (await session.execute(query)).scalars().all()

    # Only leads we can actually reach (valid phone or email).
    reachable = [
        lead for lead in candidates
        if is_valid_phone(lead.phone) or is_valid_email(lead.email)
    ]
    chosen = reachable[: max(1, size)]

    campaign = Campaign(
        name=name or f"Karma AI Launch Batch {batch_no}",
        batch_no=batch_no,
        description="First controlled outreach batch — prioritized, human-approved drafts.",
        status="ready",
    )
    session.add(campaign)
    await session.flush()

    for lead in chosen:
        draft = generate_message(lead)
        session.add(
            CampaignLead(
                campaign_id=campaign.id,
                lead_id=lead.id,
                segment=lead.segment,
                message_variant=draft["variant"],
                message_text=draft["message"],
                status="READY",
            )
        )
        lead.lead_status = "READY"
        lead.outreach_status = "READY"
        lead.last_message = draft["message"]

    await session.commit()
    await session.refresh(campaign)
    return campaign


async def campaign_payload(session, campaign: Campaign) -> dict:
    rows = (
        await session.execute(
            select(CampaignLead, AcquisitionLead)
            .join(AcquisitionLead, CampaignLead.lead_id == AcquisitionLead.id)
            .where(CampaignLead.campaign_id == campaign.id)
            .order_by(AcquisitionLead.priority_score.desc())
        )
    ).all()

    leads = []
    for cl, lead in rows:
        draft = generate_message(lead, variant=cl.message_variant)
        leads.append({
            "campaign_lead_id": str(cl.id),
            "lead_id": str(lead.id),
            "company_name": lead.company_name,
            "phone": lead.phone,
            "email": lead.email,
            "segment": lead.segment,
            "suggested_package": lead.suggested_package,
            "priority": lead.priority,
            "priority_score": lead.priority_score,
            "message_variant": cl.message_variant,
            "message": cl.message_text or draft["message"],
            "wa_link": draft["wa_link"],
            "status": cl.status,
        })

    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "batch_no": campaign.batch_no,
        "description": campaign.description,
        "status": campaign.status,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "count": len(leads),
        "leads": leads,
    }


async def export_campaign_json(session, campaign: Campaign) -> str:
    payload = await campaign_payload(session, campaign)
    CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
    path = CAMPAIGN_DIR / f"campaign_{campaign.batch_no:03d}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


async def campaign_csv(session, campaign: Campaign) -> str:
    payload = await campaign_payload(session, campaign)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["company_name", "phone", "email", "segment", "priority", "variant", "message", "wa_link", "status"])
    for lead in payload["leads"]:
        writer.writerow([
            lead["company_name"], lead["phone"] or "", lead["email"] or "",
            lead["segment"], lead["priority"], lead["message_variant"],
            lead["message"], lead["wa_link"] or "", lead["status"],
        ])
    return buffer.getvalue()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
