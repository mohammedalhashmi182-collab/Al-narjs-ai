"""Read-only daily funnel counts. No sends, no status changes, no invented revenue."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from src.services.funnel_messages import SENT_STATES, legacy_api_ack_state


def day_window(day: datetime | None = None) -> tuple[datetime, datetime]:
    start = (day or datetime.now(UTC)).astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


async def daily_kpis(session, *, day: datetime | None = None) -> dict:
    from src.models import AcquisitionLead, Payment
    from src.models.funnel import FunnelCallback, FunnelEvent, FunnelMessage, FunnelReply, PaymentLeadLink

    start, end = day_window(day)

    sent = (
        await session.execute(
            select(func.count()).select_from(FunnelMessage).where(
                FunnelMessage.direction == "outbound",
                FunnelMessage.send_proof_ref.is_not(None),
                FunnelMessage.state.in_(tuple(SENT_STATES)),
                FunnelMessage.occurred_at >= start,
                FunnelMessage.occurred_at < end,
            )
        )
    ).scalar_one()
    delivered = (
        await session.execute(
            select(func.count()).select_from(FunnelMessage).where(
                FunnelMessage.delivery_proof_ref.is_not(None),
                FunnelMessage.occurred_at >= start,
                FunnelMessage.occurred_at < end,
            )
        )
    ).scalar_one()
    replies = (
        await session.execute(
            select(func.count()).select_from(FunnelReply).where(
                FunnelReply.created_at >= start,
                FunnelReply.created_at < end,
            )
        )
    ).scalar_one()
    qualified = (
        await session.execute(
            select(func.count(func.distinct(FunnelReply.lead_id))).where(
                FunnelReply.classification == "interested",
                FunnelReply.created_at >= start,
                FunnelReply.created_at < end,
            )
        )
    ).scalar_one()
    proposals = (
        await session.execute(
            select(func.count()).select_from(FunnelEvent).where(
                FunnelEvent.event_type == "proposal_recorded",
                FunnelEvent.created_at >= start,
                FunnelEvent.created_at < end,
            )
        )
    ).scalar_one()
    linked_payments = (
        await session.execute(
            select(func.count())
            .select_from(PaymentLeadLink)
            .join(Payment, Payment.id == PaymentLeadLink.payment_id)
            .where(
                Payment.status == "paid",
                PaymentLeadLink.created_at >= start,
                PaymentLeadLink.created_at < end,
            )
        )
    ).scalar_one()
    failed = (
        await session.execute(
            select(func.count()).select_from(FunnelMessage).where(
                FunnelMessage.state == "failed",
                FunnelMessage.occurred_at >= start,
                FunnelMessage.occurred_at < end,
            )
        )
    ).scalar_one()
    inbound_leads = (
        await session.execute(
            select(func.count()).select_from(AcquisitionLead).where(
                AcquisitionLead.source.in_(("website", "consult_assistant")),
                AcquisitionLead.created_at >= start,
                AcquisitionLead.created_at < end,
            )
        )
    ).scalar_one()
    callbacks = (
        await session.execute(
            select(func.count()).select_from(FunnelCallback).where(
                FunnelCallback.created_at >= start,
                FunnelCallback.created_at < end,
            )
        )
    ).scalar_one()

    alerts = []
    if int(sent or 0) == 0 and int(replies or 0) == 0:
        alerts.append({"code": "zero_activity", "severity": "warning"})
    missing = int(inbound_leads or 0) - int(callbacks or 0)
    if missing > 0:
        alerts.append({"code": "missing_callbacks", "severity": "warning", "count": missing})
    if int(failed or 0) > 0:
        alerts.append({"code": "failed_sends", "severity": "warning", "count": int(failed)})

    return {
        "day": start.date().isoformat(),
        "actually_sent": int(sent or 0),
        "delivered": int(delivered or 0),
        "human_replies": int(replies or 0),
        "qualified_conversations": int(qualified or 0),
        "proposals": int(proposals or 0),
        "linked_payments": int(linked_payments or 0),
        "failed_sends": int(failed or 0),
        "alerts": alerts,
    }


def explain_legacy_outbound(status: str | None) -> dict:
    """Read a historical outbound row without promoting an API ack to delivery."""
    state = legacy_api_ack_state(status)
    return {
        "state": state,
        "actually_sent": False,
        "delivered": False,
        "counts_as_sent": False,
    }
