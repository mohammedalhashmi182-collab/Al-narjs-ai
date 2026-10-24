"""payments.invoice_emailed_at: marks the paid-invoice email as sent.

/api/payments/{id}/capture can be called more than once (reloads, retries);
the invoice email must go out once. Startup self-heal adds the same column.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("payments")}
    if "invoice_emailed_at" not in cols:
        op.add_column(
            "payments", sa.Column("invoice_emailed_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    op.drop_column("payments", "invoice_emailed_at")
