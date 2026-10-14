"""Lead pipeline: new -> qualified -> offer_sent -> payment_link_sent -> paid | lost.

Follow-ups are drafts like any other reply, so the owner's channel mode still
decides whether they reach the customer. Moyasar invoices are created only at
the moment a payment-link draft is actually sent (owner approval or auto mode),
never speculatively.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.models import AcquisitionLead, Payment
from src.models.automation import PIPELINE_STAGES, LeadPipeline, ReplyDraft

FOLLOWUP_STAGES = ("offer_sent", "payment_link_sent")
FOLLOWUP_SCHEDULE_NAME = "automation_followups"
FOLLOWUP_SCHEDULE_CRON = "0 * * * *"  # hourly


def followup_hours() -> list[int]:
    raw = get_settings().automation_followup_hours or "24,72,168"
    out = []
    for part in raw.split(","):
        try:
            out.append(max(1, int(part.strip())))
        except ValueError:
            continue
    return out or [24, 72, 168]


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


async def ensure(session: AsyncSession, lead: AcquisitionLead, *, channel: str | None = None, recipient: str | None = None) -> LeadPipeline:
    pipe = await session.get(LeadPipeline, lead.id)
    if pipe is None:
        pipe = LeadPipeline(lead_id=lead.id, channel=channel, recipient=recipient, stage="new",
                            followups_sent=0, history=[{"stage": "new", "at": _now().isoformat(), "note": "captured"}])
        session.add(pipe)
        await session.flush()
    else:
        pipe.channel = pipe.channel or channel
        pipe.recipient = pipe.recipient or recipient
    return pipe


def set_stage(pipe: LeadPipeline, stage: str, note: str = "") -> None:
    if stage not in PIPELINE_STAGES:
        raise ValueError(f"unknown stage {stage}")
    if pipe.stage == "paid" and stage != "paid":
        return  # a paid customer never drops back
    if pipe.stage == stage:
        return
    pipe.stage = stage
    pipe.history = [*(pipe.history or []), {"stage": stage, "at": _now().isoformat(), "note": note}]
    if stage in FOLLOWUP_STAGES:
        pipe.followups_sent = 0
        pipe.next_followup_at = _now() + timedelta(hours=followup_hours()[0])
    elif stage in ("paid", "lost"):
        pipe.next_followup_at = None
    if stage == "lost":
        pipe.lost_reason = note[:255] or None


def on_inbound(pipe: LeadPipeline) -> None:
    """The customer spoke: restart the follow-up clock, revive a lost lead."""
    if pipe.stage == "lost" and pipe.lost_reason not in ("opt_out", "not_interested"):
        set_stage(pipe, "qualified" if pipe.plan_key else "new", "customer came back")
    if pipe.stage in FOLLOWUP_STAGES:
        pipe.followups_sent = 0
        pipe.next_followup_at = _now() + timedelta(hours=followup_hours()[0])


async def on_draft_sent(session: AsyncSession, draft: ReplyDraft) -> None:
    if not draft.lead_id:
        return
    pipe = await session.get(LeadPipeline, draft.lead_id)
    if pipe is None:
        return
    if draft.kind == "payment_link":
        set_stage(pipe, "payment_link_sent", f"draft {draft.id}")
    elif draft.kind == "reply" and draft.plan_key and pipe.stage in ("new", "qualified"):
        set_stage(pipe, "offer_sent", f"draft {draft.id}")


def _base_url(base_url: str | None) -> str:
    s = get_settings()
    return (base_url or s.public_base_url or f"https://{s.domain}").rstrip("/")


async def ensure_payment_link(session: AsyncSession, draft: ReplyDraft, *, base_url: str | None = None) -> str:
    """Create (once) an invoice for the draft's plan and return its consent-gated /invoice URL."""
    from src.services import payments

    pipe = await session.get(LeadPipeline, draft.lead_id) if draft.lead_id else None
    if pipe is not None and pipe.payment_url and pipe.plan_key == draft.plan_key:
        return pipe.payment_url
    plan_key = draft.plan_key or (pipe.plan_key if pipe else None)
    if not plan_key:
        raise payments.PaymentError("no plan chosen for this lead")
    period = (draft.meta or {}).get("billing_period") or "monthly"
    addons = int((draft.meta or {}).get("addons") or 0)
    lead = await session.get(AcquisitionLead, draft.lead_id) if draft.lead_id else None
    payment = await payments.create_payment(
        session, plan_key, customer_name=lead.contact_name or lead.company_name if lead else None,
        customer_phone=lead.phone if lead else None, customer_email=lead.email if lead else None,
        lead_id=draft.lead_id, billing_period=period, addons=addons,
        conversation_packs=int((draft.meta or {}).get("conversation_packs") or 0),
        voice_packs=int((draft.meta or {}).get("voice_packs") or 0),
        founding=None,  # founding price auto-applies while seats remain
    )
    # The link is our invoice page, not a raw Moyasar checkout: the buyer must
    # tick the refund consent there before card or bank transfer (see
    # /api/payments/<id>/pay-card and /transfer-reported).
    payment.status = "invoice"
    url = f"{_base_url(base_url)}/invoice/{payment.id}"
    if pipe is not None:
        pipe.payment_id = payment.id
        pipe.payment_url = url
        pipe.plan_key = plan_key
    return url


async def request_payment_link(session: AsyncSession, lead_id: Any, plan_key: str, *, billing_period: str = "monthly",
                               addons: int = 0, base_url: str | None = None) -> ReplyDraft:
    """Owner-initiated: draft a payment-link message for a lead (mode still gates sending)."""
    from src.services import catalog, smart_reply

    if plan_key not in catalog.PACKAGES:
        raise ValueError("unknown plan")
    pipe = await session.get(LeadPipeline, lead_id)
    if pipe is None or not pipe.channel or not pipe.recipient:
        raise LookupError("lead has no reachable channel")
    if pipe.plan_key != plan_key:
        pipe.payment_url = None
    pipe.plan_key = plan_key
    pkg = catalog.PACKAGES[plan_key]
    text = (f"هذا رابط الاشتراك الآمن (ميسّر) لباقة «{pkg['name']}»"
            f"{' السنوية' if billing_period == 'annual' else ''}:\n{{payment_url}}\nبعد الدفع نبدأ تجهيز فريقك مباشرة.")
    draft = ReplyDraft(channel=pipe.channel, recipient=pipe.recipient, lead_id=lead_id, kind="payment_link",
                       draft_text=text, plan_key=plan_key, status="pending",
                       meta={"billing_period": billing_period, "addons": addons, "origin": "owner"})
    return await smart_reply.queue_or_send(session, draft, base_url=base_url)


async def run_followups(session: AsyncSession, *, now: datetime | None = None) -> dict:
    """Hourly: mark paid leads, draft due follow-ups, close exhausted ones as lost."""
    from src.services import smart_reply

    now = now or _now()
    summary = {"paid": 0, "followups": 0, "lost": 0, "skipped": 0}
    hours = followup_hours()

    pipes = list((await session.execute(
        select(LeadPipeline).where(LeadPipeline.stage.in_(FOLLOWUP_STAGES))
    )).scalars())
    for pipe in pipes:
        if pipe.payment_id:
            payment = await session.get(Payment, pipe.payment_id)
            if payment is not None and payment.status == "paid":
                set_stage(pipe, "paid", f"payment {payment.id}")
                summary["paid"] += 1
                continue
        due = _aware(pipe.next_followup_at)
        if due is None or due > now:
            continue
        if pipe.followups_sent >= len(hours):
            set_stage(pipe, "lost", "no_response")
            summary["lost"] += 1
            continue
        lead = await session.get(AcquisitionLead, pipe.lead_id)
        if lead is None or lead.opt_out or not pipe.channel or not pipe.recipient \
                or await smart_reply.get_mode(session, pipe.channel) == "off":
            summary["skipped"] += 1
            pipe.next_followup_at = now + timedelta(hours=hours[min(pipe.followups_sent, len(hours) - 1)])
            continue
        already = (await session.execute(select(ReplyDraft.id).where(
            ReplyDraft.lead_id == pipe.lead_id, ReplyDraft.kind == "followup", ReplyDraft.status == "pending"
        ))).first()
        if already is None:
            text = smart_reply.compose_followup(pipe.stage, pipe.followups_sent, pipe.plan_key, pipe.payment_url)
            await smart_reply.queue_or_send(session, ReplyDraft(
                channel=pipe.channel, recipient=pipe.recipient, lead_id=pipe.lead_id, kind="followup",
                draft_text=text, plan_key=pipe.plan_key, status="pending",
                meta={"attempt": pipe.followups_sent + 1, "stage": pipe.stage},
            ))
            summary["followups"] += 1
        pipe.followups_sent += 1
        idx = min(pipe.followups_sent, len(hours) - 1)
        pipe.next_followup_at = now + timedelta(hours=hours[idx] - hours[idx - 1] if idx > 0 else hours[0])
    await session.flush()
    return summary


async def pipeline_board(session: AsyncSession) -> dict:
    rows = list((await session.execute(select(LeadPipeline).order_by(LeadPipeline.updated_at.desc()).limit(500))).scalars())
    board: dict[str, list] = {s: [] for s in PIPELINE_STAGES}
    for p in rows:
        board.setdefault(p.stage, []).append({
            "lead_id": str(p.lead_id), "channel": p.channel, "recipient": p.recipient, "plan_key": p.plan_key,
            "payment_url": p.payment_url, "followups_sent": p.followups_sent,
            "next_followup_at": p.next_followup_at.isoformat() if p.next_followup_at else None,
            "lost_reason": p.lost_reason,
        })
    return {"counts": {k: len(v) for k, v in board.items()}, "stages": board}


async def ensure_followup_schedule(scheduler) -> None:
    from uuid import uuid4

    from src.automation.scheduler import ScheduleConfig
    from src.models import Schedule

    try:
        async with scheduler.session_factory() as session:
            exists = (await session.execute(select(Schedule).where(Schedule.name == FOLLOWUP_SCHEDULE_NAME))).scalar_one_or_none()
        if exists is not None:
            return
        await scheduler.add_schedule(ScheduleConfig(
            name=FOLLOWUP_SCHEDULE_NAME, target_type="automation_followups", target_id=uuid4(),
            payload={}, cron_expression=FOLLOWUP_SCHEDULE_CRON, timezone="Asia/Riyadh",
        ))
    except Exception:  # pragma: no cover
        import logging

        logging.getLogger(__name__).warning("Could not register follow-up schedule", exc_info=True)
