"""ZATCA phase-1 tax invoices, credit notes and collections bookkeeping.

Strictly additive tables (startup ``create_all`` creates them; alembic 0008
mirrors them).

- ``invoice_sequences``: one counter row per series ("INV", "CRN"). Numbers are
  allocated inside the issuing transaction with a row lock, and
  ``tax_invoices.invoice_number`` is UNIQUE, so a number is never reused.
- ``tax_invoices``: an issued simplified tax invoice (kind ``invoice``) or a
  credit note (kind ``credit_note``, pointing at the original). Lines, totals,
  seller snapshot and the TLV QR are frozen at issue time.
- ``collection_reminders``: one row per (payment, stage) so each step of the
  reminder sequence and each overage bill happens exactly once.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class InvoiceSequence(Base):
    __tablename__ = "invoice_sequences"

    series: Mapped[str] = mapped_column(String(10), primary_key=True)
    last_value: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)


class TaxInvoice(Base):
    __tablename__ = "tax_invoices"
    __table_args__ = (UniqueConstraint("payment_id", "kind", "credit_seq", name="uq_tax_invoice_payment_kind"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    invoice_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), default="invoice", nullable=False)  # invoice | credit_note
    credit_seq: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    payment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    original_invoice_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    seller: Mapped[dict] = mapped_column(JSON, nullable=False)
    buyer_name: Mapped[Optional[str]] = mapped_column(String(255))
    lines: Mapped[list] = mapped_column(JSON, nullable=False)
    subtotal: Mapped[int] = mapped_column(nullable=False)   # halalas, excl. VAT
    vat_total: Mapped[int] = mapped_column(nullable=False)  # halalas
    total: Mapped[int] = mapped_column(nullable=False)      # halalas, incl. VAT
    qr_tlv: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CollectionReminder(Base):
    __tablename__ = "collection_reminders"
    __table_args__ = (UniqueConstraint("payment_id", "stage", name="uq_collection_stage"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    payment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    stage: Mapped[str] = mapped_column(String(40), nullable=False)  # d-5, d-1, d0, d+3, recovery, overage:<date>
    channels: Mapped[dict] = mapped_column(JSON, default=dict)      # channel -> sent|draft|queued_template|skipped
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
