"""Customer brief the virtual CEO confirms before specialists draft work.

Additive. Startup ``create_all`` creates the table. Alembic 0020 mirrors it.
The row is the customer's view of one idea: intake, clarification, a brief
they confirm, then specialist drafts. It does not replace ``AcquisitionLead``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base

ENGAGEMENT_STAGES = (
    "intake",
    "clarification",
    "brief_pending",
    "producing",
    "ready",
)


class CustomerEngagement(Base):
    __tablename__ = "customer_engagements"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    lead_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("acquisition_leads.id", ondelete="SET NULL"), index=True
    )
    stage: Mapped[str] = mapped_column(String(30), default="intake", nullable=False, index=True)
    locale: Mapped[str] = mapped_column(String(5), default="ar", nullable=False)
    messages: Mapped[list] = mapped_column(JSON, default=list)
    brief: Mapped[dict] = mapped_column(JSON, default=dict)
    deliverables: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_customer_engagements_stage_created", "stage", "created_at"),
    )
