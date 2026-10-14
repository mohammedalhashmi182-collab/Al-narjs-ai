"""Operations tables: weekly project reports (owner-reviewed) and the
WhatsApp message-template registry.

Strictly additive tables, created by ``create_all`` at startup like the other
additive models. An alembic mirror is pending owner approval (CLAUDE.md rule 6).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base

REPORT_STATUSES = ("draft", "approved", "sent", "rejected", "failed")
TEMPLATE_STATUSES = ("draft", "submitted", "approved", "rejected", "paused")


class WeeklyReport(Base):
    """One project's weekly summary. Nothing is sent before the owner approves it."""

    __tablename__ = "ops_weekly_reports"
    __table_args__ = (UniqueConstraint("project_id", "week_start", name="uq_weekly_report_week"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    week_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    week_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    final_text: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft", index=True)
    send_result: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class WhatsAppTemplate(Base):
    """A Meta-approved (or pending) message template used outside the 24h window."""

    __tablename__ = "wa_message_templates"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="ar")
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="UTILITY")
    purpose: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    param_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
