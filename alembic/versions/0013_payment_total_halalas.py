"""payments.total_halalas: the SAR total billed, frozen at creation.

Existing rows were billed at the then-hardcoded 15% VAT, so they are
backfilled with amount + round(amount * 0.15). Startup self-heal does the same.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("total_halalas", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE payments SET total_halalas = amount + CAST(ROUND(amount * 0.15) AS INTEGER) "
        "WHERE total_halalas IS NULL"
    )


def downgrade() -> None:
    op.drop_column("payments", "total_halalas")
