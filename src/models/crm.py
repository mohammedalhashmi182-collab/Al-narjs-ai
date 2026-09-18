"""Customer-acquisition CRM models for Karma AI / Al-Narjis AI.

These tables power the internal lead-acquisition system that turns the imported
company database into controlled outreach: clean leads, segments, explainable
priority, outreach drafts, demos, follow-ups and conversion tracking.

``AcquisitionLead`` is the single canonical lead record for the whole product:
both publicly captured website leads (``source="website"``) and imported
prospects (``source="excel_import"``) live here, so the dashboard shows one
unified pipeline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

# Lead lifecycle stages. Order matters for funnel reporting.
LEAD_STATUSES = (
    "NEW",
    "READY",
    "CONTACTED",
    "REPLIED",
    "INTERESTED",
    "DEMO",
    "PROPOSAL",
    "WON",
    "LOST",
    "FOLLOW_UP",
    "DO_NOT_CONTACT",
)

# Stages that still need human attention (never silently dropped).
ACTIVE_STATUSES = (
    "NEW",
    "READY",
    "CONTACTED",
    "REPLIED",
    "INTERESTED",
    "DEMO",
    "PROPOSAL",
    "FOLLOW_UP",
)


class AcquisitionLead(Base):
    __tablename__ = "acquisition_leads"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    company_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    contact_name: Mapped[Optional[str]] = mapped_column(String(512))
    phone: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    phone_raw: Mapped[Optional[str]] = mapped_column(String(64))
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)

    source: Mapped[str] = mapped_column(String(64), default="excel_import", nullable=False)
    source_sheet: Mapped[Optional[str]] = mapped_column(String(128))
    source_customer_code: Mapped[Optional[str]] = mapped_column(String(64))

    historical_customer: Mapped[bool] = mapped_column(default=False, nullable=False)
    quotation_without_purchase: Mapped[bool] = mapped_column(default=False, nullable=False)
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    invoice_count: Mapped[int] = mapped_column(default=0, nullable=False)
    sales_representative: Mapped[Optional[str]] = mapped_column(String(255))

    segment: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False, index=True)
    segment_reason: Mapped[Optional[str]] = mapped_column(String(255))
    suggested_package: Mapped[Optional[str]] = mapped_column(String(50))

    lead_status: Mapped[str] = mapped_column(String(20), default="NEW", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(10), default="LOW", nullable=False, index=True)
    priority_score: Mapped[int] = mapped_column(default=0, nullable=False, index=True)
    priority_reason: Mapped[list] = mapped_column(JSON, default=list)

    outreach_status: Mapped[str] = mapped_column(String(30), default="NOT_STARTED", nullable=False)
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_followup_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    followup_count: Mapped[int] = mapped_column(default=0, nullable=False)
    followup_stage: Mapped[Optional[str]] = mapped_column(String(50))

    # WhatsApp conversation state (driven by the inbound webhook).
    opt_out: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    buying_signal: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    last_reply_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    intent: Mapped[Optional[str]] = mapped_column(String(30), index=True)

    notes: Mapped[Optional[str]] = mapped_column(Text)
    last_message: Mapped[Optional[str]] = mapped_column(Text)

    dedup_key: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    record_count: Mapped[int] = mapped_column(default=1, nullable=False)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    events: Mapped[list["LeadEvent"]] = relationship(
        "LeadEvent", back_populates="lead", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_acq_lead_status_priority", "lead_status", "priority_score"),
        Index("ix_acq_lead_followup", "next_followup_at", "lead_status"),
    )


class LeadEvent(Base):
    """Append-only log of everything that happens to a lead.

    Guarantees that no conversation, draft, note or status change is lost.
    """

    __tablename__ = "lead_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("acquisition_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status_before: Mapped[Optional[str]] = mapped_column(String(20))
    status_after: Mapped[Optional[str]] = mapped_column(String(20))
    channel: Mapped[Optional[str]] = mapped_column(String(20))
    message: Mapped[Optional[str]] = mapped_column(Text)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lead: Mapped["AcquisitionLead"] = relationship("AcquisitionLead", back_populates="events")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    batch_no: Mapped[int] = mapped_column(default=1, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="ready", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    leads: Mapped[list["CampaignLead"]] = relationship(
        "CampaignLead", back_populates="campaign", cascade="all, delete-orphan"
    )


class CampaignLead(Base):
    __tablename__ = "campaign_leads"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("acquisition_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    segment: Mapped[Optional[str]] = mapped_column(String(50))
    message_variant: Mapped[Optional[str]] = mapped_column(String(50))
    message_text: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="READY", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="leads")
    lead: Mapped["AcquisitionLead"] = relationship("AcquisitionLead")

    __table_args__ = (
        UniqueConstraint("campaign_id", "lead_id", name="uq_campaign_lead"),
    )
