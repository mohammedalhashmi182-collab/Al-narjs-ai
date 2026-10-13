"""Billing periods, add-on agents and subscription renewals.

Purely additive:

- ``payments``:        + ``billing_period`` (default ``monthly``), + ``addon_agents`` (0),
                       + ``is_renewal`` (false)
- ``client_projects``: + ``billing_period`` (default ``monthly``), + ``addon_agents`` (0),
                       + ``current_period_end`` (nullable, indexed),
                       + ``last_payment_id``, + ``renewal_payment_id`` (nullable UUIDs)

Existing rows keep ``current_period_end = NULL``, which the renewal job treats
as "activated before renewals existed": no invoice, no expiry. Nothing is
dropped, renamed or modified. ``src/db/session.py`` applies the same columns
idempotently at startup (``ADD COLUMN IF NOT EXISTS``).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("payments", "client_projects"):
        op.add_column(table, sa.Column("billing_period", sa.String(10), nullable=False, server_default="monthly"))
        op.add_column(table, sa.Column("addon_agents", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("payments", sa.Column("is_renewal", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("client_projects", sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True))
    op.add_column("client_projects", sa.Column("last_payment_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("client_projects", sa.Column("renewal_payment_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_client_projects_current_period_end", "client_projects", ["current_period_end"])


def downgrade() -> None:
    op.drop_index("ix_client_projects_current_period_end", table_name="client_projects")
    for column in ("renewal_payment_id", "last_payment_id", "current_period_end"):
        op.drop_column("client_projects", column)
    op.drop_column("payments", "is_renewal")
    for table in ("client_projects", "payments"):
        op.drop_column(table, "addon_agents")
        op.drop_column(table, "billing_period")
