"""Per-tenant Salla/Zid connection, store policy, and webhook idempotency.

Tokens are Fernet ciphertext (same helper as the tenant WhatsApp token). Rows are
created by ``create_all`` on boot and mirrored by alembic 0010. Webhook payloads
are never stored — only a hash — so a retry cannot duplicate work and customer
PII from the platform never lands in this table.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class StoreConnection(Base):
    __tablename__ = "store_connections"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(10), nullable=False)  # salla | zid
    # Platform store id (Salla store id, Zid store id). Not a customer phone.
    merchant_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    # Second identifier when the platform sends both (Zid store uuid).
    store_ref: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    store_name: Mapped[Optional[str]] = mapped_column(String(255))
    access_token_enc: Mapped[Optional[str]] = mapped_column(Text)
    refresh_token_enc: Mapped[Optional[str]] = mapped_column(Text)
    # Zid's separate Authorization token. Null for Salla.
    authorization_enc: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active | uninstalled
    uninstalled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("project_id", "platform", name="uq_store_connection_project_platform"),)


class StorePolicy(Base):
    """Shipping / returns / payment text the merchant wrote. The bot may quote this and nothing else."""

    __tablename__ = "store_policies"

    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_projects.id", ondelete="CASCADE"), primary_key=True)
    shipping: Mapped[Optional[str]] = mapped_column(Text)
    returns_text: Mapped[Optional[str]] = mapped_column(Text)
    payment: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class StoreWebhookEvent(Base):
    __tablename__ = "store_webhook_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    platform: Mapped[str] = mapped_column(String(10), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    event_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    merchant_id: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("platform", "dedupe_key", name="uq_store_webhook_dedupe"),)
