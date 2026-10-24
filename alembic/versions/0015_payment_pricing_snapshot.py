"""payments.pricing_snapshot: server-computed price frozen at order creation.

JSON with the expected total (halalas), currency, package, add-ons, promo code
and discount. Verification compares against it instead of current promo
settings. NULL for existing rows, which keep the legacy recompute. Idempotent:
skips the column if the startup self-heal already added it.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("payments")}
    if "pricing_snapshot" not in cols:
        op.add_column("payments", sa.Column("pricing_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("payments")}
    if "pricing_snapshot" in cols:
        op.drop_column("payments", "pricing_snapshot")
