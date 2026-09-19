"""Sales dashboard routes for the customer-acquisition system.

Everything here is owner-gated (same cookie auth as the rest of the admin area)
and deliberately small: the dashboard answers "who do I contact today, why, and
what do I say". No automatic sending happens anywhere in this module.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from src.config.settings import get_settings
from src.core.owner_auth import check_owner, require_owner
from src.models import (
    ACTIVE_STATUSES,
    LEAD_STATUSES,
    AcquisitionLead,
    Campaign,
    CampaignLead,
    LeadEvent,
)
from src.services import demo_content, lead_importer
from src.services.lead_campaigns import (
    DEFAULT_BATCH_SIZE,
    build_campaign,
    campaign_csv,
    campaign_payload,
    export_campaign_json,
)
from src.services.lead_next_action import compute_next_action, prepare_follow_up
from src.services.lead_outreach import VARIANT_LABELS_AR, determine_variant, generate_message
from src.services.lead_segmentation import SEGMENT_LABELS_AR

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")
templates.env.globals["page_lang"] = lambda request: request.cookies.get("narjis_lang", "ar")
templates.env.globals["settings"] = get_settings()
templates.env.globals["promo_info"] = lambda: {}


def _session_factory(request: Request):
    return request.app.state.session_factory


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _lead_dict(lead: AcquisitionLead) -> dict:
    next_action = compute_next_action(lead)
    return {
        "next_action": next_action["next_action"],
        "next_action_reason": next_action["reason"],
        "next_action_due": next_action["due"],
        "next_action_due_at": next_action["due_at"],
        "next_action_due_label": next_action["due_label"],
        "next_action_missing": next_action["missing"],
        "id": str(lead.id),
        "company_name": lead.company_name,
        "contact_name": lead.contact_name,
        "phone": lead.phone,
        "phone_raw": lead.phone_raw,
        "email": lead.email,
        "source": lead.source,
        "source_sheet": lead.source_sheet,
        "historical_customer": lead.historical_customer,
        "quotation_without_purchase": lead.quotation_without_purchase,
        "last_activity": lead.last_activity.isoformat() if lead.last_activity else None,
        "invoice_count": lead.invoice_count,
        "sales_representative": lead.sales_representative,
        "segment": lead.segment,
        "segment_label": SEGMENT_LABELS_AR.get(lead.segment, lead.segment),
        "segment_reason": lead.segment_reason,
        "suggested_package": lead.suggested_package,
        "lead_status": lead.lead_status,
        "priority": lead.priority,
        "priority_score": lead.priority_score,
        "priority_reason": lead.priority_reason or [],
        "outreach_status": lead.outreach_status,
        "last_contacted_at": lead.last_contacted_at.isoformat() if lead.last_contacted_at else None,
        "next_followup_at": lead.next_followup_at.isoformat() if lead.next_followup_at else None,
        "followup_count": lead.followup_count,
        "followup_stage": lead.followup_stage,
        "notes": lead.notes,
        "last_message": lead.last_message,
        "record_count": lead.record_count,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }


def _event_dict(event: LeadEvent) -> dict:
    return {
        "id": str(event.id),
        "event_type": event.event_type,
        "status_before": event.status_before,
        "status_after": event.status_after,
        "channel": event.channel,
        "message": event.message,
        "note": event.note,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


async def _log_event(
    session,
    lead: AcquisitionLead,
    event_type: str,
    *,
    status_before: Optional[str] = None,
    status_after: Optional[str] = None,
    channel: Optional[str] = None,
    message: Optional[str] = None,
    note: Optional[str] = None,
) -> None:
    session.add(LeadEvent(
        lead_id=lead.id,
        event_type=event_type,
        status_before=status_before,
        status_after=status_after,
        channel=channel,
        message=message,
        note=note,
    ))


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@router.get("/acquisition", response_class=HTMLResponse)
async def sales_dashboard_page(request: Request):
    if not check_owner(request):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "sales_dashboard.html")


@router.get("/acquisition/leads/{lead_id}", response_class=HTMLResponse)
async def sales_lead_page(request: Request, lead_id: str):
    if not check_owner(request):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "sales_lead.html", {"lead_id": lead_id})


@router.get("/acquisition/leads/{lead_id}/demo", response_class=HTMLResponse)
async def sales_lead_demo_page(request: Request, lead_id: str):
    if not check_owner(request):
        return RedirectResponse("/login")

    async with _session_factory(request)() as session:
        lead = (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.id == _uuid(lead_id)))
        ).scalar_one_or_none()
        if not lead:
            raise HTTPException(404, "Lead not found")
        lead_dict = _lead_dict(lead)

    package_key = lead_dict.get("suggested_package") or "social"
    detail = demo_content.get_package_detail(package_key) or demo_content.get_package_detail("social")
    return templates.TemplateResponse(
        request,
        "sales_demo.html",
        {"lead": lead_dict, "detail": detail, "package_key": package_key},
    )


@router.get("/acquisition/leads/{lead_id}/proposal", response_class=HTMLResponse)
async def sales_lead_proposal_page(request: Request, lead_id: str):
    """Printable one-page proposal built from evidence (never fabricated)."""
    if not check_owner(request):
        return RedirectResponse("/login")

    async with _session_factory(request)() as session:
        lead = (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.id == _uuid(lead_id)))
        ).scalar_one_or_none()
        if not lead:
            raise HTTPException(404, "Lead not found")
        lead_dict = _lead_dict(lead)

    package_key = lead_dict.get("suggested_package") or "social"
    detail = demo_content.get_package_detail(package_key) or demo_content.get_package_detail("social")
    from src.services import catalog as _catalog
    from src.services.revenue_tiers import (
        PRICE_SAR,
        data_flags,
        provenance,
        reference_id,
        score_lead,
    )

    price = PRICE_SAR.get(package_key, PRICE_SAR["social"])
    vat = round(price * 0.15)
    tier = score_lead(lead_dict)
    return templates.TemplateResponse(
        request,
        "sales_proposal.html",
        {
            "lead": lead_dict,
            "detail": detail,
            "package_key": package_key,
            "price": price,
            "vat": vat,
            "total": price + vat,
            "tier": tier.tier,
            "tier_score": tier.score,
            "tier_reasons": tier.reasons,
            "reference_id": reference_id(lead_dict),
            "provenance": provenance(lead_dict),
            "flags": data_flags(lead_dict),
            "catalog_names": _catalog.PACKAGES,
        },
    )


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(400, "Invalid id") from None


# ---------------------------------------------------------------------------
# API — overview + leads
# ---------------------------------------------------------------------------

@router.get("/api/acquisition/overview", dependencies=[Depends(require_owner)])
async def sales_overview(request: Request):
    now = _now()
    async with _session_factory(request)() as session:
        status_rows = dict(
            (await session.execute(
                select(AcquisitionLead.lead_status, func.count()).group_by(AcquisitionLead.lead_status)
            )).all()
        )
        total = (await session.execute(select(func.count()).select_from(AcquisitionLead))).scalar_one()
        segment_rows = dict(
            (await session.execute(
                select(AcquisitionLead.segment, func.count()).group_by(AcquisitionLead.segment)
            )).all()
        )
        priority_rows = dict(
            (await session.execute(
                select(AcquisitionLead.priority, func.count()).group_by(AcquisitionLead.priority)
            )).all()
        )

        due_rows = (
            await session.execute(
                select(AcquisitionLead)
                .where(AcquisitionLead.next_followup_at.is_not(None))
                .where(AcquisitionLead.next_followup_at <= now)
                .where(AcquisitionLead.lead_status.in_(ACTIVE_STATUSES))
                .order_by(AcquisitionLead.next_followup_at)
                .limit(50)
            )
        ).scalars().all()

        priority_leads = (
            await session.execute(
                select(AcquisitionLead)
                .where(AcquisitionLead.lead_status.in_(ACTIVE_STATUSES))
                .order_by(AcquisitionLead.priority_score.desc())
                .limit(50)
            )
        ).scalars().all()

    def rate(stage: str) -> float:
        return round((status_rows.get(stage, 0) / total * 100), 1) if total else 0.0

    pipelines = {
        "NEW": status_rows.get("NEW", 0),
        "READY": status_rows.get("READY", 0),
        "CONTACTED": status_rows.get("CONTACTED", 0),
        "REPLIED": status_rows.get("REPLIED", 0),
        "INTERESTED": status_rows.get("INTERESTED", 0),
        "DEMO": status_rows.get("DEMO", 0),
        "PROPOSAL": status_rows.get("PROPOSAL", 0),
        "WON": status_rows.get("WON", 0),
        "LOST": status_rows.get("LOST", 0),
        "FOLLOW_UP": status_rows.get("FOLLOW_UP", 0),
        "DO_NOT_CONTACT": status_rows.get("DO_NOT_CONTACT", 0),
    }
    return {
        "totals": {
            "total_leads": total,
            "unique_companies": total,
            "by_status": pipelines,
            "by_priority": priority_rows,
            "by_segment": segment_rows,
        },
        "today": {
            "followups_due": len(due_rows),
            "followups": [_lead_dict(l) for l in due_rows],
            "replies": [_lead_dict(l) for l in priority_leads if l.lead_status == "REPLIED"],
            "new_leads": pipelines["NEW"],
            "ready": pipelines["READY"],
            "demos": pipelines["DEMO"],
            "proposals": pipelines["PROPOSAL"],
        },
        "conversion": {
            "contacted_rate": rate("CONTACTED"),
            "reply_rate": rate("REPLIED"),
            "demo_rate": rate("DEMO"),
            "proposal_rate": rate("PROPOSAL"),
            "won_rate": rate("WON"),
        },
        "whatsapp_business_number": get_settings().whatsapp_business_number,
        "top_leads": [_lead_dict(l) for l in priority_leads],
    }


@router.get("/api/acquisition/leads", dependencies=[Depends(require_owner)])
async def sales_list_leads(
    request: Request,
    status: Optional[str] = None,
    segment: Optional[str] = None,
    priority: Optional[str] = None,
    q: Optional[str] = None,
    due: bool = False,
    limit: int = 50,
    offset: int = 0,
):
    query = select(AcquisitionLead)
    if status:
        query = query.where(AcquisitionLead.lead_status == status)
    if segment:
        query = query.where(AcquisitionLead.segment == segment)
    if priority:
        query = query.where(AcquisitionLead.priority == priority)
    if due:
        query = query.where(AcquisitionLead.next_followup_at.is_not(None)).where(
            AcquisitionLead.next_followup_at <= _now()
        ).where(AcquisitionLead.lead_status.in_(ACTIVE_STATUSES))
    if q:
        like = f"%{q}%"
        query = query.where(or_(
            AcquisitionLead.company_name.ilike(like),
            AcquisitionLead.phone.ilike(like),
            AcquisitionLead.email.ilike(like),
        ))

    query = query.order_by(AcquisitionLead.priority_score.desc(), AcquisitionLead.company_name)
    query = query.limit(min(limit, 500)).offset(offset)

    async with _session_factory(request)() as session:
        rows = (await session.execute(query)).scalars().all()
    return {"leads": [_lead_dict(l) for l in rows], "count": len(rows)}


@router.get("/api/acquisition/leads/{lead_id}", dependencies=[Depends(require_owner)])
async def sales_lead_detail(request: Request, lead_id: str):
    async with _session_factory(request)() as session:
        lead = (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.id == _uuid(lead_id)))
        ).scalar_one_or_none()
        if not lead:
            raise HTTPException(404, "Lead not found")
        events = (
            await session.execute(
                select(LeadEvent).where(LeadEvent.lead_id == lead.id).order_by(LeadEvent.created_at.desc())
            )
        ).scalars().all()
        draft = generate_message(lead)
    return {
        "lead": _lead_dict(lead),
        "events": [_event_dict(e) for e in events],
        "draft": draft,
        "follow_up": prepare_follow_up(lead, events),
        "variants": VARIANT_LABELS_AR,
        "suggested_variant": determine_variant(lead),
    }


class StatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None
    channel: Optional[str] = None


@router.post("/api/acquisition/leads/{lead_id}/status", dependencies=[Depends(require_owner)])
async def sales_update_status(request: Request, lead_id: str, body: StatusUpdate):
    if body.status not in LEAD_STATUSES:
        raise HTTPException(400, f"Unknown status: {body.status}")

    async with _session_factory(request)() as session:
        lead = (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.id == _uuid(lead_id)))
        ).scalar_one_or_none()
        if not lead:
            raise HTTPException(404, "Lead not found")

        before = lead.lead_status
        lead.lead_status = body.status
        lead.outreach_status = body.status
        if body.status in ("CONTACTED", "REPLIED", "INTERESTED", "DEMO", "PROPOSAL", "WON", "FOLLOW_UP"):
            lead.last_contacted_at = _now()
        if body.status == "WON":
            lead.next_followup_at = None
        await _log_event(
            session, lead, "status_change",
            status_before=before, status_after=body.status,
            channel=body.channel, note=body.note,
        )
        await session.commit()
        await session.refresh(lead)
        lead_dict = _lead_dict(lead)
    return {"success": True, "lead": lead_dict}


class MessageRequest(BaseModel):
    variant: Optional[str] = None
    lang: str = "ar"


@router.post("/api/acquisition/leads/{lead_id}/message", dependencies=[Depends(require_owner)])
async def sales_generate_message(request: Request, lead_id: str, body: MessageRequest):
    async with _session_factory(request)() as session:
        lead = (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.id == _uuid(lead_id)))
        ).scalar_one_or_none()
        if not lead:
            raise HTTPException(404, "Lead not found")

        variant = body.variant or determine_variant(lead)
        draft = generate_message(lead, variant=variant, lang=body.lang if body.lang in ("ar", "en") else "ar")
        lead.last_message = draft["message"]
        lead.outreach_status = "READY"
        await _log_event(
            session, lead, "message_generated",
            channel="whatsapp", message=draft["message"], note=draft["variant_label"],
        )
        await session.commit()
    return {"success": True, "draft": draft}


class FollowupRequest(BaseModel):
    days: Optional[int] = None
    next_followup_at: Optional[str] = None
    note: Optional[str] = None


@router.post("/api/acquisition/leads/{lead_id}/followup", dependencies=[Depends(require_owner)])
async def sales_schedule_followup(request: Request, lead_id: str, body: FollowupRequest):
    target = _parse_dt(body.next_followup_at)
    if target is None and body.days is not None:
        target = _now() + timedelta(days=max(1, body.days))
    if target is None:
        raise HTTPException(400, "Provide days or next_followup_at")

    async with _session_factory(request)() as session:
        lead = (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.id == _uuid(lead_id)))
        ).scalar_one_or_none()
        if not lead:
            raise HTTPException(404, "Lead not found")

        lead.next_followup_at = target
        lead.followup_count = (lead.followup_count or 0) + 1
        lead.followup_stage = lead.lead_status
        if lead.lead_status in ("CONTACTED", "REPLIED", "INTERESTED", "DEMO", "PROPOSAL"):
            lead.lead_status = "FOLLOW_UP"
        lead.outreach_status = "FOLLOW_UP"
        await _log_event(
            session, lead, "followup_scheduled",
            status_before=lead.followup_stage, status_after=lead.lead_status,
            note=body.note or f"متابعة بعد {body.days or '-'} يوم",
        )
        await session.commit()
        await session.refresh(lead)
        lead_dict = _lead_dict(lead)
    return {"success": True, "lead": lead_dict}


class NoteRequest(BaseModel):
    note: str


@router.post("/api/acquisition/leads/{lead_id}/note", dependencies=[Depends(require_owner)])
async def sales_add_note(request: Request, lead_id: str, body: NoteRequest):
    async with _session_factory(request)() as session:
        lead = (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.id == _uuid(lead_id)))
        ).scalar_one_or_none()
        if not lead:
            raise HTTPException(404, "Lead not found")
        lead.notes = ((lead.notes + "\n") if lead.notes else "") + body.note.strip()
        await _log_event(session, lead, "note", note=body.note.strip())
        await session.commit()
    return {"success": True}


@router.post("/api/acquisition/leads/{lead_id}/do-not-contact", dependencies=[Depends(require_owner)])
async def sales_do_not_contact(request: Request, lead_id: str):
    async with _session_factory(request)() as session:
        lead = (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.id == _uuid(lead_id)))
        ).scalar_one_or_none()
        if not lead:
            raise HTTPException(404, "Lead not found")
        before = lead.lead_status
        lead.lead_status = "DO_NOT_CONTACT"
        lead.outreach_status = "DO_NOT_CONTACT"
        lead.next_followup_at = None
        await _log_event(
            session, lead, "opt_out",
            status_before=before, status_after="DO_NOT_CONTACT",
            note="طلب عدم التواصل",
        )
        await session.commit()
    return {"success": True, "lead_status": "DO_NOT_CONTACT"}


# ---------------------------------------------------------------------------
# API — campaigns
# ---------------------------------------------------------------------------

class CampaignRequest(BaseModel):
    size: int = DEFAULT_BATCH_SIZE
    name: Optional[str] = None


@router.get("/api/acquisition/campaigns", dependencies=[Depends(require_owner)])
async def sales_list_campaigns(request: Request):
    async with _session_factory(request)() as session:
        campaigns = (
            await session.execute(select(Campaign).order_by(Campaign.batch_no.desc()))
        ).scalars().all()
        counts = dict(
            (await session.execute(
                select(CampaignLead.campaign_id, func.count()).group_by(CampaignLead.campaign_id)
            )).all()
        )
    return {"campaigns": [
        {
            "id": str(c.id),
            "name": c.name,
            "batch_no": c.batch_no,
            "status": c.status,
            "count": counts.get(c.id, 0),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in campaigns
    ]}


@router.post("/api/acquisition/campaigns", dependencies=[Depends(require_owner)])
async def sales_create_campaign(request: Request, body: CampaignRequest):
    size = max(1, min(body.size or DEFAULT_BATCH_SIZE, 500))
    async with _session_factory(request)() as session:
        campaign = await build_campaign(session, size=size, name=body.name)
        payload = await campaign_payload(session, campaign)
        await export_campaign_json(session, campaign)
    return {"success": True, "campaign": {k: payload[k] for k in ("id", "name", "batch_no", "status", "count")}}


@router.get("/api/acquisition/campaigns/{campaign_id}", dependencies=[Depends(require_owner)])
async def sales_campaign_detail(request: Request, campaign_id: str):
    async with _session_factory(request)() as session:
        campaign = (
            await session.execute(select(Campaign).where(Campaign.id == _uuid(campaign_id)))
        ).scalar_one_or_none()
        if not campaign:
            raise HTTPException(404, "Campaign not found")
        payload = await campaign_payload(session, campaign)
    return payload


@router.get("/api/acquisition/campaigns/{campaign_id}/export.csv", dependencies=[Depends(require_owner)])
async def sales_campaign_csv(request: Request, campaign_id: str):
    async with _session_factory(request)() as session:
        campaign = (
            await session.execute(select(Campaign).where(Campaign.id == _uuid(campaign_id)))
        ).scalar_one_or_none()
        if not campaign:
            raise HTTPException(404, "Campaign not found")
        content = await campaign_csv(session, campaign)
    return PlainTextResponse(
        content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="campaign_{campaign.batch_no:03d}.csv"'},
    )


@router.post("/api/acquisition/import", dependencies=[Depends(require_owner)])
async def sales_import_lead_source(
    request: Request,
    file: UploadFile = File(...),
    campaign: int = Form(0),
):
    """Owner-gated, idempotent lead-source import (same pipeline as import_leads.py).

    Accepts the historical invoices/quotations .xlsx (or .csv) and persists the
    normalized leads into the production database, optionally building the next
    campaign batch of `campaign` leads. No messages are sent here.
    """
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm", ".csv", ".txt")):
        raise HTTPException(415, "يُقبل فقط ملفات .xlsx أو .csv")
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "الملف كبير جداً (الحد الأقصى 25MB)")

    suffix = Path(file.filename).suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(data)
        tmp.close()
        raw = lead_importer.extract_records(tmp.name)
        leads = lead_importer.build_leads(raw)
        stats = lead_importer.compute_stats(raw, leads)
        if not leads:
            return {"imported": 0, "created": 0, "updated": 0, "stats": stats}
        async with _session_factory(request)() as session:
            created, updated = await lead_importer.persist_leads(session, leads)
        result = {
            "imported": len(leads),
            "created": created,
            "updated": updated,
            "stats": stats,
        }
        if campaign:
            from src.services.lead_campaigns import build_campaign

            size = max(1, min(campaign, 500))
            async with _session_factory(request)() as session:
                batch = await build_campaign(session, size=size)
            result["campaign"] = {
                "id": str(batch.id),
                "batch_no": batch.batch_no,
                "target": size,
            }
        return result
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
