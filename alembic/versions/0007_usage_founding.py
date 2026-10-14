"""Usage metering (monthly counters + events), usage add-on packs, founding offer.

Additive. Startup ``create_all`` creates the two tables and the self-heal adds
the columns with ADD COLUMN IF NOT EXISTS, so every step here is guarded.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)

_PAYMENT_COLS = [
    ("addon_conversation_packs", sa.Integer(), "0"),
    ("addon_voice_packs", sa.Integer(), "0"),
    ("founding", sa.Boolean(), sa.false()),
]
_PROJECT_COLS = [
    ("addon_conversation_packs", sa.Integer(), "0"),
    ("addon_voice_packs", sa.Integer(), "0"),
    ("founding", sa.Boolean(), sa.false()),
    ("founding_at", TS, None),
    ("founding_locked_until", TS, None),
    ("founding_commitment_until", TS, None),
    ("founding_revoked_at", TS, None),
    ("wa_phone_number_id", sa.String(64), None),
]


def _add_columns(table: str, cols) -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    for name, type_, default in cols:
        if name in have:
            continue
        if default is None:
            op.add_column(table, sa.Column(name, type_, nullable=True))
        else:
            op.add_column(table, sa.Column(name, type_, nullable=False, server_default=default))


def upgrade() -> None:
    _add_columns("payments", _PAYMENT_COLS)
    _add_columns("client_projects", _PROJECT_COLS)
    insp = sa.inspect(op.get_bind())
    if "ix_client_projects_wa_phone_number_id" not in {i["name"] for i in insp.get_indexes("client_projects")}:
        op.create_index("ix_client_projects_wa_phone_number_id", "client_projects", ["wa_phone_number_id"])
    tables = set(insp.get_table_names())
    if "subscription_usage" not in tables:
        op.create_table(
            "subscription_usage",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("project_id", UUID, sa.ForeignKey("client_projects.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("period_start", TS, nullable=False),
            sa.Column("period_end", TS, nullable=False),
            sa.Column("conversations", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("voice_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("meta_fees", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("limit_conversations", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("limit_voice_minutes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("limit_meta_cap", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("over_limit", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("overage_conversations", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("overage_voice_minutes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("overage_meta_fees", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("alerts_sent", sa.JSON()),
            sa.Column("created_at", TS, server_default=sa.func.now()),
            sa.Column("updated_at", TS, server_default=sa.func.now()),
            sa.UniqueConstraint("project_id", "period_start", name="uq_subscription_usage_period"),
        )
    if "usage_events" not in tables:
        op.create_table(
            "usage_events",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("project_id", UUID, sa.ForeignKey("client_projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("channel", sa.String(20)),
            sa.Column("contact_key", sa.String(128)),
            sa.Column("ref", sa.String(255)),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("meta", sa.JSON()),
            sa.Column("occurred_at", TS, nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_usage_events_contact", "usage_events", ["project_id", "kind", "contact_key", "occurred_at"])
        op.create_index("ix_usage_events_ref", "usage_events", ["project_id", "kind", "ref"])


def downgrade() -> None:
    op.drop_table("usage_events")
    op.drop_table("subscription_usage")
    op.drop_index("ix_client_projects_wa_phone_number_id", table_name="client_projects")
    for name, _t, _d in reversed(_PROJECT_COLS):
        op.drop_column("client_projects", name)
    for name, _t, _d in reversed(_PAYMENT_COLS):
        op.drop_column("payments", name)
