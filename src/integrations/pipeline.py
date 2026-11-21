"""After a store connects, keep one CRM lead and one human follow-up.

The OAuth install already stores encrypted tokens. This records the merchant
in the same acquisition pipeline the owner already works, assigned to the
store manager and to the human owner. It does not call the store again and
does not change lead-status rules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from src.models import AcquisitionLead, ClientProject, LeadEvent, Task
from src.services.lead_normalize import normalize_phone


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _merge(lead: AcquisitionLead, value: dict) -> None:
    raw = dict(lead.raw_data or {})
    raw["store"] = value
    lead.raw_data = raw


async def record_connection(session, project_id: UUID, platform: str, store_name: str | None, merchant_id: str | None) -> None:
    project = await session.get(ClientProject, project_id)
    if project is None or platform not in ("salla", "zid"):
        return
    key = f"store:{platform}:{merchant_id or project_id}"
    lead = (
        await session.execute(select(AcquisitionLead).where(AcquisitionLead.dedup_key == key))
    ).scalar_one_or_none()
    created = lead is None
    now = _now()
    label = (store_name or project.client_name or platform)[:512]
    if lead is None:
        phone = normalize_phone(project.phone)
        lead = AcquisitionLead(
            company_name=label,
            contact_name=(project.client_name or "")[:512] or None,
            phone=phone,
            phone_raw=(project.phone or "")[:64] or None,
            email=(project.email or None),
            source=platform,
            segment="ecommerce",
            lead_status="NEW",
            priority="MEDIUM",
            sales_representative="owner",
            dedup_key=key,
            followup_stage="store_connected",
            next_followup_at=now,
        )
        session.add(lead)
        await session.flush()
    else:
        lead.company_name = label or lead.company_name
        lead.followup_stage = "store_connected"
        lead.next_followup_at = now
        if not (lead.sales_representative or "").strip():
            lead.sales_representative = "owner"
    _merge(lead, {
        "platform": platform,
        "merchant_id": merchant_id or "",
        "project_id": str(project_id),
        "store_name": store_name or "",
    })
    session.add(LeadEvent(
        lead_id=lead.id,
        event_type="store_connected",
        channel=platform,
        status_before=None if created else lead.lead_status,
        status_after=lead.lead_status,
        note=f"platform={platform}",
    ))
    task_key = f"store-followup:{platform}:{project_id}"
    existing = (await session.execute(select(Task).where(Task.key == task_key))).scalar_one_or_none()
    if existing is None:
        session.add(Task(
            key=task_key,
            title=f"متابعة متجر {platform}"[:512],
            description=f"متجر «{label}» ارتبط بالمشروع. المتابعة على المالك ووكيل إدارة المتجر. لا يُرسل شيء تلقائياً.",
            source="store_connect",
            status="escalated",
            priority=150,
            owner_agent="store_manager",
            department="ecommerce",
            evidence={
                "handler": "human_followup",
                "platform": platform,
                "project_id": str(project_id),
                "lead_id": str(lead.id),
                "human_owner": "owner",
            },
            learning="المتابعة على المالك. الربط لا يعني أن الطلبات تُدار آلياً.",
            due_at=now,
        ))
