"""Tenant Reply Agent (per-project drafts, contacts, reply mode, encrypted
per-project WhatsApp token) and portal login (OTP / magic-link codes, session
revocation counter).

Additive and guarded: startup ``create_all`` creates the new tables and the
self-heal in ``src/db/session.py`` adds the columns with ADD COLUMN IF NOT EXISTS.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)

_COLS = [
    ("client_projects", "reply_mode", sa.String(10), "review"),
    ("client_projects", "wa_access_token_enc", sa.Text(), None),
    ("client_projects", "portal_token_version", sa.Integer(), "0"),
    ("automation_reply_drafts", "project_id", UUID, None),
    ("inbound_messages", "project_id", UUID, None),
]
_INDEXES = [
    ("ix_automation_reply_drafts_project_id", "automation_reply_drafts", "project_id"),
    ("ix_inbound_messages_project_id", "inbound_messages", "project_id"),
]


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    for table, name, type_, default in _COLS:
        if name in {c["name"] for c in insp.get_columns(table)}:
            continue
        if default is None:
            op.add_column(table, sa.Column(name, type_, nullable=True))
        else:
            op.add_column(table, sa.Column(name, type_, nullable=False, server_default=default))
    for ix, table, col in _INDEXES:
        if ix not in {i["name"] for i in insp.get_indexes(table)}:
            op.create_index(ix, table, [col])
    tables = set(insp.get_table_names())
    if "tenant_contacts" not in tables:
        op.create_table(
            "tenant_contacts",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("project_id", UUID, sa.ForeignKey("client_projects.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("channel", sa.String(20), nullable=False),
            sa.Column("contact", sa.String(64), nullable=False),
            sa.Column("display_name", sa.String(255)),
            sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_inbound_at", TS),
            sa.Column("last_text", sa.Text()),
            sa.Column("handoff_at", TS),
            sa.Column("handoff_reason", sa.String(50)),
            sa.Column("opt_out", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", TS, server_default=sa.func.now()),
            sa.UniqueConstraint("project_id", "channel", "contact", name="uq_tenant_contact"),
        )
    if "portal_login_codes" not in tables:
        op.create_table(
            "portal_login_codes",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("project_id", UUID, sa.ForeignKey("client_projects.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("kind", sa.String(10), nullable=False),
            sa.Column("identifier", sa.String(255), index=True),
            sa.Column("code_hash", sa.String(64), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("expires_at", TS, nullable=False),
            sa.Column("used_at", TS),
            sa.Column("created_at", TS, server_default=sa.func.now()),
        )
        op.create_index("ix_portal_login_ident_created", "portal_login_codes", ["identifier", "created_at"])


def downgrade() -> None:
    op.drop_table("portal_login_codes")
    op.drop_table("tenant_contacts")
    for ix, table, _c in _INDEXES:
        op.drop_index(ix, table_name=table)
    for table, name, _t, _d in reversed(_COLS):
        op.drop_column(table, name)
