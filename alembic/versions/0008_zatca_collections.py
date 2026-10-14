"""ZATCA phase-1 tax invoices/credit notes, invoice sequences, collection reminders.

Additive; startup ``create_all`` creates the same tables, so every step is guarded.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "invoice_sequences" not in tables:
        op.create_table(
            "invoice_sequences",
            sa.Column("series", sa.String(10), primary_key=True),
            sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        )
    if "tax_invoices" not in tables:
        op.create_table(
            "tax_invoices",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("invoice_number", sa.String(32), nullable=False, unique=True),
            sa.Column("kind", sa.String(20), nullable=False, server_default="invoice"),
            sa.Column("credit_seq", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("payment_id", UUID, sa.ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("original_invoice_id", UUID),
            sa.Column("issued_at", TS, nullable=False),
            sa.Column("seller", sa.JSON(), nullable=False),
            sa.Column("buyer_name", sa.String(255)),
            sa.Column("lines", sa.JSON(), nullable=False),
            sa.Column("subtotal", sa.Integer(), nullable=False),
            sa.Column("vat_total", sa.Integer(), nullable=False),
            sa.Column("total", sa.Integer(), nullable=False),
            sa.Column("qr_tlv", sa.Text(), nullable=False),
            sa.Column("reason", sa.Text()),
            sa.Column("created_at", TS, server_default=sa.func.now()),
            sa.UniqueConstraint("payment_id", "kind", "credit_seq", name="uq_tax_invoice_payment_kind"),
        )
    if "collection_reminders" not in tables:
        op.create_table(
            "collection_reminders",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("project_id", UUID, sa.ForeignKey("client_projects.id", ondelete="CASCADE"), index=True),
            sa.Column("payment_id", UUID, nullable=False),
            sa.Column("stage", sa.String(40), nullable=False),
            sa.Column("channels", sa.JSON()),
            sa.Column("created_at", TS, server_default=sa.func.now()),
            sa.UniqueConstraint("payment_id", "stage", name="uq_collection_stage"),
        )


def downgrade() -> None:
    op.drop_table("collection_reminders")
    op.drop_table("tax_invoices")
    op.drop_table("invoice_sequences")
