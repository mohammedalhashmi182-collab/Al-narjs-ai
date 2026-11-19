"""Revenue funnel tracking tables (SCHEMA - needs owner approval before production).

Additive only. Does not alter payments, lead_status, or existing rows.
Startup ``create_all`` creates the same tables. Do not run this against
production until the owner accepts the migration.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid():
    return sa.Uuid()


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "lead_identity_aliases" not in tables:
        op.create_table(
            "lead_identity_aliases",
            sa.Column("id", _uuid(), primary_key=True),
            sa.Column("lead_id", _uuid(), sa.ForeignKey("acquisition_leads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source", sa.String(40), nullable=False),
            sa.Column("external_key", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("source", "external_key", name="uq_lead_alias_source_key"),
        )
        op.create_index("ix_lead_identity_aliases_lead_id", "lead_identity_aliases", ["lead_id"])
    if "funnel_events" not in tables:
        op.create_table(
            "funnel_events",
            sa.Column("id", _uuid(), primary_key=True),
            sa.Column("lead_id", _uuid(), sa.ForeignKey("acquisition_leads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("event_type", sa.String(40), nullable=False),
            sa.Column("idempotency_key", sa.String(255), nullable=False),
            sa.Column("channel", sa.String(20), nullable=True),
            sa.Column("actor", sa.String(40), nullable=True),
            sa.Column("evidence_ref", sa.String(255), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("idempotency_key", name="uq_funnel_event_idempotency"),
        )
        op.create_index("ix_funnel_events_lead_id", "funnel_events", ["lead_id"])
    if "funnel_messages" not in tables:
        op.create_table(
            "funnel_messages",
            sa.Column("id", _uuid(), primary_key=True),
            sa.Column("lead_id", _uuid(), sa.ForeignKey("acquisition_leads.id", ondelete="SET NULL"), nullable=True),
            sa.Column("channel", sa.String(20), nullable=False),
            sa.Column("direction", sa.String(10), nullable=False),
            sa.Column("state", sa.String(20), nullable=False),
            sa.Column("proof_kind", sa.String(40), nullable=False),
            sa.Column("provider_message_id", sa.String(255), nullable=True),
            sa.Column("in_reply_to", sa.String(255), nullable=True),
            sa.Column("send_proof_ref", sa.String(255), nullable=True),
            sa.Column("delivery_proof_ref", sa.String(255), nullable=True),
            sa.Column("accept_ref", sa.String(255), nullable=True),
            sa.Column("error_code", sa.String(50), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("provider_message_id", name="uq_funnel_message_provider_id"),
        )
        op.create_index("ix_funnel_messages_state", "funnel_messages", ["state"])
        op.create_index("ix_funnel_messages_lead_id", "funnel_messages", ["lead_id"])
    if "funnel_replies" not in tables:
        op.create_table(
            "funnel_replies",
            sa.Column("id", _uuid(), primary_key=True),
            sa.Column("lead_id", _uuid(), sa.ForeignKey("acquisition_leads.id", ondelete="SET NULL"), nullable=True),
            sa.Column("message_row_id", _uuid(), nullable=True),
            sa.Column("classification", sa.String(20), nullable=False),
            sa.Column("evidence_ref", sa.String(255), nullable=False),
            sa.Column("evidence_hash", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("evidence_ref", name="uq_funnel_reply_evidence"),
        )
        op.create_index("ix_funnel_replies_lead_id", "funnel_replies", ["lead_id"])
    if "lead_consents" not in tables:
        op.create_table(
            "lead_consents",
            sa.Column("id", _uuid(), primary_key=True),
            sa.Column("lead_id", _uuid(), sa.ForeignKey("acquisition_leads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("channel", sa.String(20), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("evidence_ref", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_lead_consents_lead_id", "lead_consents", ["lead_id"])
    if "funnel_callbacks" not in tables:
        op.create_table(
            "funnel_callbacks",
            sa.Column("id", _uuid(), primary_key=True),
            sa.Column("lead_id", _uuid(), sa.ForeignKey("acquisition_leads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source", sa.String(40), nullable=False),
            sa.Column("next_step", sa.Text(), nullable=False),
            sa.Column("owner_agent", sa.String(100), nullable=False),
            sa.Column("work_kind", sa.String(30), nullable=False),
            sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("lead_id", name="uq_funnel_callback_lead"),
        )
    if "payment_lead_links" not in tables:
        op.create_table(
            "payment_lead_links",
            sa.Column("id", _uuid(), primary_key=True),
            sa.Column("payment_id", _uuid(), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("lead_id", _uuid(), sa.ForeignKey("acquisition_leads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("method", sa.String(30), nullable=False),
            sa.Column("evidence_ref", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("payment_id", name="uq_payment_lead_link_payment"),
        )
        op.create_index("ix_payment_lead_links_lead_id", "payment_lead_links", ["lead_id"])


def downgrade() -> None:
    for name in (
        "payment_lead_links",
        "funnel_callbacks",
        "lead_consents",
        "funnel_replies",
        "funnel_messages",
        "funnel_events",
        "lead_identity_aliases",
    ):
        op.drop_table(name)
