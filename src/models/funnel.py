"""Additive revenue-funnel records.

These tables sit beside ``acquisition_leads``. They do not replace it and they
do not change ``lead_status``. Rows are inserted; nothing in this package
updates an event, a consent row, or a payment link after it is written.

``AcquisitionLead.id`` stays the canonical customer id. Aliases point email,
phone, consult, Gmail Message-ID and the legacy ``leads`` key at that id.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base

MESSAGE_STATES = (
    "draft",
    "queued",
    "accepted",
    "sent",
    "delivered",
    "replied",
    "failed",
)
REPLY_CLASSES = ("interested", "not_now", "opt_out", "unknown")
CONSENT_STATUSES = ("granted", "opt_out")


def _now() -> datetime:
    return datetime.now(UTC)


class LeadAlias(Base):
    """One external key for one canonical acquisition lead. Never repointed."""

    __tablename__ = "lead_identity_aliases"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("acquisition_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    external_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("source", "external_key", name="uq_lead_alias_source_key"),
    )


class FunnelEvent(Base):
    """Append-only lead history. Callers insert; there is no update path."""

    __tablename__ = "funnel_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("acquisition_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[Optional[str]] = mapped_column(String(20))
    actor: Mapped[Optional[str]] = mapped_column(String(40))
    evidence_ref: Mapped[Optional[str]] = mapped_column(String(255))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_funnel_event_idempotency"),
        Index("ix_funnel_events_lead_created", "lead_id", "created_at"),
    )


class FunnelMessage(Base):
    """One outbound or inbound message and the proof behind its state.

    ``accepted`` means a provider API answered. That is not ``sent`` and it is
    not ``delivered``. ``sent`` requires a mailbox Message-ID. ``delivered``
    requires a separate delivery receipt. Draft and queued rows never count
    as sent.
    """

    __tablename__ = "funnel_messages"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("acquisition_leads.id", ondelete="SET NULL"), index=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    proof_kind: Mapped[str] = mapped_column(String(40), nullable=False, default="none")
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255))
    in_reply_to: Mapped[Optional[str]] = mapped_column(String(255))
    send_proof_ref: Mapped[Optional[str]] = mapped_column(String(255))
    delivery_proof_ref: Mapped[Optional[str]] = mapped_column(String(255))
    accept_ref: Mapped[Optional[str]] = mapped_column(String(255))
    error_code: Mapped[Optional[str]] = mapped_column(String(50))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("provider_message_id", name="uq_funnel_message_provider_id"),
        Index("ix_funnel_messages_state_occurred", "state", "occurred_at"),
    )


class FunnelReply(Base):
    """A classified human reply. The evidence is the provider Message-ID."""

    __tablename__ = "funnel_replies"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("acquisition_leads.id", ondelete="SET NULL"), index=True
    )
    message_row_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("evidence_ref", name="uq_funnel_reply_evidence"),
    )


class LeadConsent(Base):
    """Append-only consent. The newest row for a channel is the current choice."""

    __tablename__ = "lead_consents"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("acquisition_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_ref: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())

    __table_args__ = (
        Index("ix_lead_consents_lead_channel", "lead_id", "channel", "created_at"),
    )


class FunnelCallback(Base):
    """One CRM case for a website or consult contact, with an owner and an SLA."""

    __tablename__ = "funnel_callbacks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("acquisition_leads.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    next_step: Mapped[str] = mapped_column(Text, nullable=False)
    owner_agent: Mapped[str] = mapped_column(String(100), nullable=False)
    work_kind: Mapped[str] = mapped_column(String(30), nullable=False, default="sales")
    sla_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("lead_id", name="uq_funnel_callback_lead"),
    )


class PaymentLeadLink(Base):
    """Auditable link from a payment to a lead. Existing payments stay as they are.

    A row is written only for an owner session or a signed lead token. Matching
    a payment to a lead by email or phone is not a supported method.
    """

    __tablename__ = "payment_lead_links"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    payment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False
    )
    lead_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("acquisition_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("payment_id", name="uq_payment_lead_link_payment"),
    )
