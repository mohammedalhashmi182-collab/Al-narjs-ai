"""Customer CEO briefs (additive).

Startup ``create_all`` creates the same table. Does not alter payments,
lead_status, or existing rows.

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid():
    return sa.Uuid()


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "customer_engagements" in tables:
        return
    op.create_table(
        "customer_engagements",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("public_token", sa.String(64), nullable=False),
        sa.Column("lead_id", _uuid(), sa.ForeignKey("acquisition_leads.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stage", sa.String(30), nullable=False),
        sa.Column("locale", sa.String(5), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=True),
        sa.Column("brief", sa.JSON(), nullable=True),
        sa.Column("deliverables", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_customer_engagements_public_token", "customer_engagements", ["public_token"], unique=True)
    op.create_index("ix_customer_engagements_lead_id", "customer_engagements", ["lead_id"])
    op.create_index("ix_customer_engagements_stage", "customer_engagements", ["stage"])
    op.create_index("ix_customer_engagements_stage_created", "customer_engagements", ["stage", "created_at"])


def downgrade() -> None:
    op.drop_table("customer_engagements")
