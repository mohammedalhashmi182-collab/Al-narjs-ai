"""Usage metering: monthly per-subscription counters and the raw usage events.

Strictly additive tables (created by ``create_all`` at startup; alembic 0007
mirrors them). A counter row is one subscription's one monthly usage window
(see ``services.usage.usage_window``); events dedupe conversations (24h per
contact) and Meta fees (once per provider message id).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base

USAGE_KINDS = ("conversation", "voice", "meta_fee")


class SubscriptionUsage(Base):
    __tablename__ = "subscription_usage"
    __table_args__ = (UniqueConstraint("project_id", "period_start", name="uq_subscription_usage_period"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    conversations: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    voice_seconds: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    meta_fees: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)  # halalas
    # Allowance snapshot for the window (plan + usage add-on packs).
    limit_conversations: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    limit_voice_minutes: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    limit_meta_cap: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)  # halalas
    # Over the allowance: service is never cut; the excess is recorded here
    # for add-on billing (packs for conversations/voice, at cost for Meta).
    over_limit: Mapped[bool] = mapped_column(default=False, server_default=text("false"), nullable=False)
    overage_conversations: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    overage_voice_minutes: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    overage_meta_fees: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)  # halalas
    alerts_sent: Mapped[list] = mapped_column(JSON, default=list)  # e.g. ["conversations:80"]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        Index("ix_usage_events_contact", "project_id", "kind", "contact_key", "occurred_at"),
        Index("ix_usage_events_ref", "project_id", "kind", "ref"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_projects.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    channel: Mapped[Optional[str]] = mapped_column(String(20))
    contact_key: Mapped[Optional[str]] = mapped_column(String(128))
    ref: Mapped[Optional[str]] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(default=1, server_default="1", nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
