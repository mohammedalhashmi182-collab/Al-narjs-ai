"""ops_funnel_events + ops_error_events (SCHEMA - needs owner approval before merge).

Additive only. Startup ``create_all`` creates the same tables; this mirror
keeps alembic in step. Neither table stores message text, raw IPs, request
bodies, headers or payment data.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "ops_funnel_events" not in tables:
        op.create_table(
            "ops_funnel_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("event", sa.String(40), nullable=False),
            sa.Column("session_hash", sa.String(32), nullable=True),
            sa.Column("props", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_ops_funnel_events_event", "ops_funnel_events", ["event"])
        op.create_index("ix_ops_funnel_events_session_hash", "ops_funnel_events", ["session_hash"])
        op.create_index("ix_ops_funnel_events_created_at", "ops_funnel_events", ["created_at"])
    if "ops_error_events" not in tables:
        op.create_table(
            "ops_error_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
            sa.Column("source", sa.String(40), nullable=False),
            sa.Column("route", sa.String(160), nullable=True),
            sa.Column("error_type", sa.String(80), nullable=False),
            sa.Column("message", sa.String(300), nullable=True),
            sa.Column("last_request_id", sa.String(64), nullable=True),
            sa.Column("environment", sa.String(20), nullable=True),
            sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_ops_error_events_source", "ops_error_events", ["source"])
        op.create_index("ix_ops_error_events_last_seen", "ops_error_events", ["last_seen"])


def downgrade() -> None:
    op.drop_table("ops_error_events")
    op.drop_table("ops_funnel_events")
