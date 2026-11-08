"""Internal-only durable service journal; no billing or customer delivery.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-08

Additive tables only. Customer requests and deliverable bytes must be encrypted
by the application before inserting either column.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "service_offers" not in existing:
        op.create_table(
            "service_offers",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("client_projects.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("service_slug", sa.String(80), nullable=False),
            sa.Column("brief_encrypted", sa.LargeBinary(), nullable=False),
            sa.Column("formats", sa.JSON(), nullable=False),
            sa.Column("scope", sa.JSON(), nullable=False),
            sa.Column("terms_version", sa.String(80), nullable=False),
            sa.Column("digest", sa.String(64), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True)),
            sa.Column("accepted_session_project", sa.String(64)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_service_offers_project_id", "service_offers", ["project_id"])
    if "service_jobs" not in existing:
        op.create_table(
            "service_jobs",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("offer_id", sa.Uuid(), sa.ForeignKey("service_offers.id", ondelete="RESTRICT"), unique=True, nullable=False),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("client_projects.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("status", sa.String(40), nullable=False, server_default="queued"),
            sa.Column("idempotency_key", sa.String(100), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("lease_token", sa.String(64)),
            sa.Column("leased_until", sa.DateTime(timezone=True)),
            sa.Column("qa_digest", sa.String(64)),
            sa.Column("last_error", sa.String(255)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("project_id", "idempotency_key", name="uq_service_job_project_request"),
        )
        op.create_index("ix_service_jobs_project_id", "service_jobs", ["project_id"])
        op.create_index("ix_service_jobs_status", "service_jobs", ["status"])
    if "service_artifacts" not in existing:
        op.create_table(
            "service_artifacts",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("job_id", sa.Uuid(), sa.ForeignKey("service_jobs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("client_projects.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("filename", sa.String(160), nullable=False),
            sa.Column("media_type", sa.String(160), nullable=False),
            sa.Column("sha256", sa.String(64), nullable=False),
            sa.Column("encrypted_bytes", sa.LargeBinary(), nullable=False),
            sa.Column("byte_count", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("job_id", "filename", name="uq_service_artifact_job_file"),
        )
        op.create_index("ix_service_artifacts_job_id", "service_artifacts", ["job_id"])
        op.create_index("ix_service_artifacts_project_id", "service_artifacts", ["project_id"])
    if "service_journal_events" not in existing:
        op.create_table(
            "service_journal_events",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("job_id", sa.Uuid(), sa.ForeignKey("service_jobs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("project_id", sa.Uuid(), sa.ForeignKey("client_projects.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("event_key", sa.String(140), nullable=False, unique=True),
            sa.Column("event_name", sa.String(80), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_service_journal_events_job_id", "service_journal_events", ["job_id"])
        op.create_index("ix_service_journal_events_project_id", "service_journal_events", ["project_id"])
        op.create_index("ix_service_event_job_created", "service_journal_events", ["job_id", "created_at"])


def downgrade() -> None:
    # Intentionally conservative; no automatic customer data loss.
    raise RuntimeError("Destructive service journal downgrade requires an explicit backup and migration plan")
