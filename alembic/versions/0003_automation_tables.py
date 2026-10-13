"""Owner-gated automation: channel modes, reply drafts, lead pipeline, social drafts.

Purely additive (new tables only). ``create_all`` at startup creates the same
tables, so this migration exists for environments that run alembic.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


_TABLES = {"automation_channel_settings", "automation_reply_drafts", "automation_lead_pipeline", "automation_social_posts"}


def upgrade() -> None:
    # The app creates these with create_all at startup; on a live DB they
    # already exist, so this revision becomes a no-op instead of failing.
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if _TABLES <= existing:
        return
    if _TABLES & existing:
        raise RuntimeError(
            f"partial automation schema {sorted(_TABLES & existing)}: inspect manually, then `alembic stamp 0003`"
        )
    op.create_table(
        "automation_channel_settings",
        sa.Column("channel", sa.String(20), primary_key=True),
        sa.Column("mode", sa.String(10), nullable=False, server_default="review"),
        sa.Column("updated_at", TS, server_default=sa.func.now()),
    )
    op.create_table(
        "automation_reply_drafts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("channel", sa.String(20), nullable=False, index=True),
        sa.Column("recipient", sa.String(64), nullable=False),
        sa.Column("lead_id", UUID, sa.ForeignKey("acquisition_leads.id", ondelete="SET NULL"), index=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="reply"),
        sa.Column("inbound_text", sa.Text()),
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("final_text", sa.Text()),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending", index=True),
        sa.Column("plan_key", sa.String(20)),
        sa.Column("meta", sa.JSON()),
        sa.Column("send_result", sa.JSON()),
        sa.Column("created_at", TS, server_default=sa.func.now()),
        sa.Column("decided_at", TS),
    )
    op.create_index("ix_reply_draft_status_created", "automation_reply_drafts", ["status", "created_at"])
    op.create_table(
        "automation_lead_pipeline",
        sa.Column("lead_id", UUID, sa.ForeignKey("acquisition_leads.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("channel", sa.String(20)),
        sa.Column("recipient", sa.String(64)),
        sa.Column("stage", sa.String(20), nullable=False, server_default="new", index=True),
        sa.Column("plan_key", sa.String(20)),
        sa.Column("payment_id", UUID),
        sa.Column("payment_url", sa.String(512)),
        sa.Column("followups_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_followup_at", TS, index=True),
        sa.Column("lost_reason", sa.String(255)),
        sa.Column("history", sa.JSON()),
        sa.Column("updated_at", TS, server_default=sa.func.now()),
    )
    op.create_table(
        "automation_social_posts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("plan_key", sa.String(20)),
        sa.Column("theme", sa.String(64)),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("hashtags", sa.JSON()),
        sa.Column("scheduled_for", TS, index=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="draft", index=True),
        sa.Column("created_at", TS, server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in ("automation_social_posts", "automation_lead_pipeline", "automation_reply_drafts",
                  "automation_channel_settings"):
        op.drop_table(table)
