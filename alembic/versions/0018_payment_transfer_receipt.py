"""payments transfer receipt columns (additive).

A guest may attach a transfer receipt. The bytes stay on the payment row so
they survive a redeploy. Existing rows stay NULL. Nothing is dropped.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("payments")}
    if "transfer_receipt" not in cols:
        op.add_column("payments", sa.Column("transfer_receipt", sa.LargeBinary(), nullable=True))
    if "transfer_receipt_filename" not in cols:
        op.add_column("payments", sa.Column("transfer_receipt_filename", sa.String(120), nullable=True))
    if "transfer_receipt_mime" not in cols:
        op.add_column("payments", sa.Column("transfer_receipt_mime", sa.String(80), nullable=True))
    if "transfer_receipt_at" not in cols:
        op.add_column("payments", sa.Column("transfer_receipt_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "transfer_receipt_at")
    op.drop_column("payments", "transfer_receipt_mime")
    op.drop_column("payments", "transfer_receipt_filename")
    op.drop_column("payments", "transfer_receipt")
