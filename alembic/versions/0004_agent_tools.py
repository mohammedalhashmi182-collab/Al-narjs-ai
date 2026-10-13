"""Agent tools: uploaded data files + knowledge-base documents.

Additive; ``create_all`` at startup creates the same tables, so this is a no-op on a live DB.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "agent_data_files" not in existing:
        op.create_table(
            "agent_data_files",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("project_id", UUID, sa.ForeignKey("client_projects.id", ondelete="CASCADE"),
                      nullable=False, index=True),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("kind", sa.String(10), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("summary", sa.JSON()),
            sa.Column("created_at", TS, server_default=sa.func.now()),
        )
    if "agent_knowledge_docs" not in existing:
        op.create_table(
            "agent_knowledge_docs",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("project_id", UUID, sa.ForeignKey("client_projects.id", ondelete="CASCADE"), index=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("source", sa.String(10), nullable=False, server_default="text"),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", TS, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("agent_knowledge_docs")
    op.drop_table("agent_data_files")
