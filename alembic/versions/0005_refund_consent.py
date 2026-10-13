"""Checkout refund consent: timestamp + policy version on payments.

Additive; startup also adds these columns with ADD COLUMN IF NOT EXISTS.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("payments")}
    if "refund_consent_at" not in cols:
        op.add_column("payments", sa.Column("refund_consent_at", sa.DateTime(timezone=True), nullable=True))
    if "refund_consent_version" not in cols:
        op.add_column("payments", sa.Column("refund_consent_version", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "refund_consent_version")
    op.drop_column("payments", "refund_consent_at")
