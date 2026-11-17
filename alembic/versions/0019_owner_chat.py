"""Owner chat profiles, conversations and messages (additive).

The owner console can chat with agents, add custom agents, and store
instruction overrides. Existing rows are untouched. Nothing is dropped
except on downgrade. Startup ``create_all`` creates the same tables.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "owner_agent_profiles" not in existing:
        op.create_table(
            "owner_agent_profiles",
            sa.Column("slug", sa.String(80), primary_key=True),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("name_ar", sa.String(80)),
            sa.Column("role_ar", sa.String(240)),
            sa.Column("instructions", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", TS, server_default=sa.func.now()),
            sa.Column("updated_at", TS, server_default=sa.func.now()),
        )
    if "owner_conversations" not in existing:
        op.create_table(
            "owner_conversations",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("participants", sa.JSON(), nullable=True),
            sa.Column("created_at", TS, server_default=sa.func.now()),
            sa.Column("updated_at", TS, server_default=sa.func.now()),
        )
    if "owner_chat_messages" not in existing:
        op.create_table(
            "owner_chat_messages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "conversation_id",
                sa.String(64),
                sa.ForeignKey("owner_conversations.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("role", sa.String(16), nullable=False),
            sa.Column("speaker_slug", sa.String(80)),
            sa.Column("speaker_name", sa.String(80)),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", TS, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("owner_chat_messages")
    op.drop_table("owner_conversations")
    op.drop_table("owner_agent_profiles")
