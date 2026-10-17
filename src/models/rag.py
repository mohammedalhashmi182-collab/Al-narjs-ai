"""RAG chunk index for knowledge-base documents (alembic 0011).

One row per (document chunk, embedding model). ``project_id`` is copied from
the document so every retrieval query filters on the tenant directly (lesson 5:
strict tenant isolation); NULL = Al-Narjis's own KB (site assistant).

``embedding`` (JSON list of floats) is always stored, so retrieval works on any
database (SQLite in tests: in-process cosine). On Postgres with the pgvector
extension the same vector is also written to ``embedding_vec`` (type
``vector``, added by migration 0011 / startup self-heal, not declared here so
SQLite never sees it) and similarity runs in the database.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class KnowledgeChunk(Base):
    __tablename__ = "agent_knowledge_chunks"
    __table_args__ = (Index("ix_kchunk_project_model", "project_id", "model"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    doc_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent_knowledge_docs.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_projects.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    doc_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")  # sha256(title+content) when indexed
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
