"""Write funnel messages, replies and proposals. This module never sends mail."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.services.funnel_messages import (
    PROOF_API,
    PROOF_MAILBOX,
    PROOF_REPLY,
    ProofError,
    evidence_hash,
    is_actually_sent,
    resolve_state,
    utcnow,
)
from src.services.funnel_replies import classify_reply
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ConsentBlocked(PermissionError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _clean_id(value: str | None) -> str | None:
    text = (value or "").strip().strip("<>").lower()
    return text or None


async def _event(session, lead_id, event_type: str, key: str, *, evidence_ref: str | None = None, channel: str | None = None, payload: dict | None = None) -> None:
    from src.models.funnel import FunnelEvent

    if lead_id is None:
        return
    existing = (
        await session.execute(select(FunnelEvent).where(FunnelEvent.idempotency_key == key))
    ).scalar_one_or_none()
    if existing is not None:
        return
    session.add(FunnelEvent(
        lead_id=lead_id,
        event_type=event_type,
        idempotency_key=key,
        evidence_ref=evidence_ref,
        channel=channel,
        actor="funnel",
        payload=payload or {},
    ))


async def _by_provider_id(session, provider_message_id: str):
    from src.models.funnel import FunnelMessage

    return (
        await session.execute(
            select(FunnelMessage).where(FunnelMessage.provider_message_id == provider_message_id)
        )
    ).scalar_one_or_none()


async def record_message(
    session,
    *,
    lead_id: UUID | None,
    channel: str,
    direction: str,
    requested: str,
    proof_kind: str,
    proof_ref: str | None = None,
    in_reply_to: str | None = None,
    occurred_at: datetime | None = None,
    error_code: str | None = None,
    enforce_consent: bool = False,
    purpose: str = "inquiry",
) -> dict:
    """Insert one message row. Repeating the same provider id returns the first row."""
    from src.models import AcquisitionLead
    from src.models.funnel import FunnelMessage
    from src.services.funnel_callback import outreach_blocked

    provider_id = _clean_id(proof_ref) if proof_kind != "none" else None
    if provider_id:
        existing = await _by_provider_id(session, provider_id)
        if existing is not None:
            return _public(existing, deduplicated=True)

    if proof_kind == "delivery_receipt":
        raise ProofError("delivery is recorded with record_delivery, not as a new send")

    reply_to = _clean_id(in_reply_to)
    if enforce_consent and direction == "outbound" and requested not in {"failed"}:
        lead = await session.get(AcquisitionLead, lead_id) if lead_id else None
        if lead is not None:
            reason = await outreach_blocked(session, lead, purpose=purpose)
            if reason:
                raise ConsentBlocked(reason)

    state = resolve_state(
        requested=requested,
        proof_kind=proof_kind,
        proof_ref=provider_id,
        prior_was_sent=proof_kind == PROOF_MAILBOX,
    )
    row = FunnelMessage(
        lead_id=lead_id,
        channel=channel,
        direction=direction,
        state=state,
        proof_kind=proof_kind,
        provider_message_id=provider_id,
        in_reply_to=reply_to,
        send_proof_ref=provider_id if proof_kind == PROOF_MAILBOX else None,
        delivery_proof_ref=None,
        accept_ref=provider_id if proof_kind == PROOF_API else None,
        error_code=error_code,
        occurred_at=occurred_at or utcnow(),
    )
    session.add(row)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        if provider_id:
            existing = await _by_provider_id(session, provider_id)
            if existing is not None:
                return _public(existing, deduplicated=True)
        raise

    if state == "sent" and lead_id is not None:
        lead = await session.get(AcquisitionLead, lead_id)
        if lead is not None and lead.last_contacted_at is None:
            lead.last_contacted_at = row.occurred_at
    await _event(
        session,
        row.lead_id,
        f"message_{state}",
        key=f"message:{provider_id or row.id}",
        evidence_ref=provider_id,
        channel=channel,
        payload={"state": state, "proof_kind": proof_kind, "direction": direction},
    )
    logger.info("Funnel message %s state=%s proof=%s", row.id, state, proof_kind)
    return _public(row, deduplicated=False)


async def record_delivery(session, *, sent_message_id: str, receipt_id: str) -> dict:
    """Mark delivery only when the outbound row already has a Message-ID."""
    sent_id = _clean_id(sent_message_id)
    receipt = _clean_id(receipt_id)
    row = await _by_provider_id(session, sent_id or "")
    if row is None or not row.send_proof_ref or not receipt:
        raise ProofError("delivery is not inferred before an independent send proof")
    if row.delivery_proof_ref:
        return _public(row, deduplicated=True)
    row.delivery_proof_ref = receipt
    if row.state != "replied":
        row.state = "delivered"
    await _event(
        session,
        row.lead_id,
        "message_delivered",
        key=f"delivery:{sent_id}:{receipt}",
        evidence_ref=receipt,
        channel=row.channel,
        payload={"state": row.state, "proof_kind": "delivery_receipt"},
    )
    logger.info("Funnel delivery recorded for message %s", row.id)
    return _public(row, deduplicated=False)


def _public(row, *, deduplicated: bool) -> dict:
    return {
        "id": str(row.id),
        "lead_id": str(row.lead_id) if row.lead_id else None,
        "state": row.state,
        "proof_kind": row.proof_kind,
        "provider_message_id": row.provider_message_id,
        "actually_sent": is_actually_sent(row.state, row.send_proof_ref),
        "delivered": bool(row.delivery_proof_ref) and row.state in {"delivered", "replied"},
        "deduplicated": deduplicated,
    }


async def approve_outreach(
    session,
    *,
    lead_id: UUID,
    message_id: str,
    channel: str = "email",
    purpose: str = "inquiry",
    occurred_at: datetime | None = None,
) -> dict:
    """Record an owner-approved send that already has a Message-ID. Does not send."""
    from src.services.agent_dispatch import record_send_proof

    result = await record_message(
        session,
        lead_id=lead_id,
        channel=channel,
        direction="outbound",
        requested="sent",
        proof_kind=PROOF_MAILBOX,
        proof_ref=message_id,
        occurred_at=occurred_at,
        enforce_consent=True,
        purpose=purpose,
    )
    if not result["deduplicated"]:
        kind = "customer_service" if purpose == "support" else "sales"
        await record_send_proof(session, lead_id=lead_id, kind=kind, message_id=_clean_id(message_id) or message_id)
    return result


async def record_reply(
    session,
    *,
    evidence_ref: str,
    text: str,
    lead_id: UUID | None = None,
    in_reply_to: str | None = None,
    channel: str = "email",
    occurred_at: datetime | None = None,
) -> dict:
    """Store a human reply classification plus the provider Message-ID."""
    from src.models import AcquisitionLead
    from src.models.funnel import FunnelReply

    provider_id = _clean_id(evidence_ref)
    if not provider_id:
        raise ValueError("reply evidence id is required")
    classification = classify_reply(text)
    digest = evidence_hash(text)
    existing = (
        await session.execute(select(FunnelReply).where(FunnelReply.evidence_ref == provider_id))
    ).scalar_one_or_none()
    if existing is not None:
        return {
            "classification": existing.classification,
            "evidence_ref": existing.evidence_ref,
            "lead_id": str(existing.lead_id) if existing.lead_id else None,
            "deduplicated": True,
        }

    parent = await _by_provider_id(session, _clean_id(in_reply_to) or "") if in_reply_to else None
    if lead_id is None and parent is not None:
        lead_id = parent.lead_id
    message = await record_message(
        session,
        lead_id=lead_id,
        channel=channel,
        direction="inbound",
        requested="replied",
        proof_kind=PROOF_REPLY,
        proof_ref=provider_id,
        in_reply_to=in_reply_to,
        occurred_at=occurred_at,
        enforce_consent=False,
    )
    if parent is not None and parent.send_proof_ref and parent.state in {"sent", "delivered"}:
        parent.state = "replied"
    reply = FunnelReply(
        lead_id=lead_id,
        message_row_id=UUID(message["id"]) if message.get("id") else None,
        classification=classification,
        evidence_ref=provider_id,
        evidence_hash=digest,
    )
    session.add(reply)
    await session.flush()
    if lead_id is not None:
        lead = await session.get(AcquisitionLead, lead_id)
        if lead is not None:
            lead.last_reply_at = occurred_at or utcnow()
            if classification == "interested":
                lead.buying_signal = True
            if classification == "opt_out":
                lead.opt_out = True
                from src.services.funnel_callback import _consent
                await _consent(session, lead.id, "email", "opt_out", provider_id)
        await _event(
            session,
            lead_id,
            "reply_classified",
            key=f"reply:{provider_id}",
            evidence_ref=provider_id,
            channel=channel,
            payload={"classification": classification},
        )
    logger.info("Classified reply %s as %s", provider_id, classification)
    return {
        "classification": classification,
        "evidence_ref": provider_id,
        "lead_id": str(lead_id) if lead_id else None,
        "deduplicated": False,
        "message_id": message["id"],
    }


async def record_proposal(session, *, lead_id: UUID, evidence_ref: str) -> dict:
    """Note that a proposal exists. Does not change lead_status and does not send."""
    ref = (evidence_ref or "").strip()
    if not ref:
        raise ValueError("proposal evidence id is required")
    await _event(
        session,
        lead_id,
        "proposal_recorded",
        key=f"proposal:{lead_id}:{ref}",
        evidence_ref=ref,
        channel="email",
        payload={},
    )
    from src.models.automation import LeadPipeline

    pipe = await session.get(LeadPipeline, lead_id)
    if pipe is not None and pipe.stage in {"new", "qualified"}:
        pipe.stage = "offer_sent"
        pipe.history = [*(pipe.history or []), {"stage": "offer_sent", "at": utcnow().isoformat(), "note": "proposal"}]
    logger.info("Recorded proposal for lead %s", lead_id)
    return {"lead_id": str(lead_id), "evidence_ref": ref}
