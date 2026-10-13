"""PayPal charge record: currency + minor-unit amount actually charged (USD).

Additive; startup also adds these columns with ADD COLUMN IF NOT EXISTS.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("payments")}
    if "charge_currency" not in cols:
        op.add_column("payments", sa.Column("charge_currency", sa.String(3), nullable=True))
    if "charge_amount" not in cols:
        op.add_column("payments", sa.Column("charge_amount", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "charge_amount")
    op.drop_column("payments", "charge_currency")
