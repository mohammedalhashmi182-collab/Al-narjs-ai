"""Tenant Reply Agent + portal login tables. Additive; created by ``create_all``,
mirrored by alembic 0008.

``TenantContact`` is a customer's own end-customer (one row per project and
WhatsApp contact). It is deliberately separate from ``AcquisitionLead``: a
subscriber's customers are never Al-Narjis sales leads (PDPL: the subscriber is
the controller of that data).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class TenantContact(Base):
    __tablename__ = "tenant_contacts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="whatsapp")
    contact: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_inbound_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_text: Mapped[Optional[str]] = mapped_column(Text)
    # Human handoff: while set, the agent stays silent and the customer's staff reply.
    handoff_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    handoff_reason: Mapped[Optional[str]] = mapped_column(String(50))
    opt_out: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("project_id", "channel", "contact", name="uq_tenant_contact"),)


class PortalLoginCode(Base):
    """One-time portal login secret: a 6-digit OTP or a magic-link nonce (hashed)."""

    __tablename__ = "portal_login_codes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # otp | magic
    identifier: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_portal_login_ident_created", "identifier", "created_at"),)
