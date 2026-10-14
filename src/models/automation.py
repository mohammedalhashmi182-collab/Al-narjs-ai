"""Owner-gated customer automation: channel modes, reply drafts, lead pipeline, social drafts.

Strictly additive tables (created by ``create_all`` at startup; alembic 0003 mirrors them).
Nothing in here sends anything: senders read these rows only after the owner approves
a draft, or when the owner has explicitly flipped a channel to ``auto``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base

CHANNELS = ("whatsapp", "telegram", "messenger")
CHANNEL_MODES = ("off", "review", "auto")
DEFAULT_CHANNEL_MODE = "review"

DRAFT_STATUSES = ("pending", "sent", "rejected", "failed", "skipped")
DRAFT_KINDS = ("reply", "followup", "payment_link")

PIPELINE_STAGES = ("new", "qualified", "offer_sent", "payment_link_sent", "paid", "lost")
SOCIAL_PLATFORMS = ("instagram", "x", "linkedin", "tiktok", "snapchat", "facebook")


class ChannelSetting(Base):
    __tablename__ = "automation_channel_settings"

    channel: Mapped[str] = mapped_column(String(20), primary_key=True)
    mode: Mapped[str] = mapped_column(String(10), nullable=False, default=DEFAULT_CHANNEL_MODE)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReplyDraft(Base):
    """One outbound message waiting for (or past) the owner's decision."""

    __tablename__ = "automation_reply_drafts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    recipient: Mapped[str] = mapped_column(String(64), nullable=False)
    lead_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("acquisition_leads.id", ondelete="SET NULL"), index=True
    )
    # Set = a Tenant Reply Agent draft for this customer project (its own review
    # queue in the portal). NULL = Al-Narjis's own sales conversation.
    project_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_projects.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="reply")
    inbound_text: Mapped[Optional[str]] = mapped_column(Text)
    draft_text: Mapped[str] = mapped_column(Text, nullable=False)
    final_text: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending", index=True)
    plan_key: Mapped[Optional[str]] = mapped_column(String(20))
    meta: Mapped[Optional[dict]] = mapped_column(JSON)
    send_result: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_reply_draft_status_created", "status", "created_at"),)


class LeadPipeline(Base):
    """Sales stage for one lead (separate from the legacy ``lead_status`` CRM field)."""

    __tablename__ = "automation_lead_pipeline"

    lead_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("acquisition_leads.id", ondelete="CASCADE"), primary_key=True
    )
    channel: Mapped[Optional[str]] = mapped_column(String(20))
    recipient: Mapped[Optional[str]] = mapped_column(String(64))
    stage: Mapped[str] = mapped_column(String(20), nullable=False, default="new", index=True)
    plan_key: Mapped[Optional[str]] = mapped_column(String(20))
    payment_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    payment_url: Mapped[Optional[str]] = mapped_column(String(512))
    followups_sent: Mapped[int] = mapped_column(default=0, nullable=False)
    next_followup_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    lost_reason: Mapped[Optional[str]] = mapped_column(String(255))
    history: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SocialPostDraft(Base):
    __tablename__ = "automation_social_posts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    plan_key: Mapped[Optional[str]] = mapped_column(String(20))
    theme: Mapped[Optional[str]] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[list] = mapped_column(JSON, default=list)
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
