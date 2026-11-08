"""Durable, project-scoped fulfillment journal for the DocPack service pilot.

This records *non-financial* internal work only. Customer delivery and paid
activation must remain disabled pending a separate, approved payment design.
Artifacts are encrypted in the DB, not kept on Render disk.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ServiceOffer(Base):
    __tablename__ = "service_offers"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    service_slug: Mapped[str] = mapped_column(String(80), nullable=False, default="docpack")
    # Never persist the customer's raw request as plaintext.
    brief_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    formats: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    scope: Mapped[dict] = mapped_column(JSON, nullable=False)
    terms_version: Mapped[str] = mapped_column(String(80), nullable=False, default="internal-preview-v1")
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_session_project: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ServiceJob(Base):
    __tablename__ = "service_jobs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    offer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("service_offers.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="queued", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_token: Mapped[str | None] = mapped_column(String(64))
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    qa_digest: Mapped[str | None] = mapped_column(String(64))
    last_error: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint("project_id", "idempotency_key", name="uq_service_job_project_request"),
    )


class ServiceArtifact(Base):
    __tablename__ = "service_artifacts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("service_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(160), nullable=False)
    media_type: Mapped[str] = mapped_column(String(160), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    byte_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("job_id", "filename", name="uq_service_artifact_job_file"),)


class ServiceJournalEvent(Base):
    __tablename__ = "service_journal_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("service_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    event_key: Mapped[str] = mapped_column(String(140), unique=True, nullable=False)
    event_name: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_service_event_job_created", "job_id", "created_at"),)


class ServiceStepCheckpoint(Base):
    """Encrypted output of an individually completed, restartable team step."""

    __tablename__ = "service_step_checkpoints"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("service_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("client_projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    step_id: Mapped[str] = mapped_column(String(80), nullable=False)
    agent_slug: Mapped[str] = mapped_column(String(80), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_output: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("job_id", "step_id", name="uq_service_checkpoint_job_step"),)
