"""RAG chunk index (agent_knowledge_chunks) + optional pgvector column.

The table is also created by startup ``create_all``. The ``vector`` extension
and the ``embedding_vec`` column are best-effort: when pgvector is not
available on the database, retrieval falls back to in-process cosine over the
JSON ``embedding`` column (same results, slower on very large KBs).

Revision ID: 0011
Revises: 0009
Create Date: 2026-10-14

0010 is reserved for the store-integrations migration on the Salla/Zid branch.
This revision stays 0011 so the two files never share an Alembic id.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "agent_knowledge_chunks" not in insp.get_table_names():
        op.create_table(
            "agent_knowledge_chunks",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("doc_id", UUID, sa.ForeignKey("agent_knowledge_docs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("project_id", UUID, sa.ForeignKey("client_projects.id", ondelete="CASCADE"), nullable=True),
            sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("title", sa.String(255), nullable=False, server_default=""),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("doc_hash", sa.String(64), nullable=False, server_default=""),
            sa.Column("model", sa.String(120), nullable=False),
            sa.Column("dim", sa.Integer(), nullable=False),
            sa.Column("embedding", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_agent_knowledge_chunks_doc_id", "agent_knowledge_chunks", ["doc_id"])
        op.create_index("ix_agent_knowledge_chunks_project_id", "agent_knowledge_chunks", ["project_id"])
        op.create_index("ix_kchunk_project_model", "agent_knowledge_chunks", ["project_id", "model"])
    if bind.dialect.name == "postgresql":
        # Savepoint so a missing extension never aborts the migration.
        with op.get_context().autocommit_block():
            try:
                bind.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
                bind.exec_driver_sql("ALTER TABLE agent_knowledge_chunks ADD COLUMN IF NOT EXISTS embedding_vec vector")
            except Exception:  # noqa: BLE001 - pgvector unavailable: JSON + in-process cosine
                pass


def downgrade() -> None:
    op.drop_table("agent_knowledge_chunks")
