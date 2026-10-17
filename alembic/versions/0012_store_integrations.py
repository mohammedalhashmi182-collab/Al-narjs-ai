"""Per-tenant Salla/Zid connections, store policy, webhook idempotency, OAuth nonces.

Additive. Startup ``create_all`` creates the same tables.

Revision 0012 revises 0011 (``0011_rag_chunks.py`` on main). Revision 0010
is unused. With both files present, ``alembic heads`` is 0012 only.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "store_connections" not in existing:
        op.create_table(
            "store_connections",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("project_id", UUID, sa.ForeignKey("client_projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("platform", sa.String(10), nullable=False),
            sa.Column("merchant_id", sa.String(64)),
            sa.Column("store_ref", sa.String(64)),
            sa.Column("store_name", sa.String(255)),
            sa.Column("access_token_enc", sa.Text()),
            sa.Column("refresh_token_enc", sa.Text()),
            sa.Column("authorization_enc", sa.Text()),
            sa.Column("expires_at", TS),
            sa.Column("scopes", sa.String(500)),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("uninstalled_at", TS),
            sa.Column("created_at", TS, server_default=sa.func.now()),
            sa.Column("updated_at", TS, server_default=sa.func.now()),
            sa.UniqueConstraint("project_id", "platform", name="uq_store_connection_project_platform"),
        )
        op.create_index("ix_store_connections_project_id", "store_connections", ["project_id"])
        op.create_index("ix_store_connections_merchant_id", "store_connections", ["merchant_id"])
        op.create_index("ix_store_connections_store_ref", "store_connections", ["store_ref"])
    if "store_policies" not in existing:
        op.create_table(
            "store_policies",
            sa.Column("project_id", UUID, sa.ForeignKey("client_projects.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("shipping", sa.Text()),
            sa.Column("returns_text", sa.Text()),
            sa.Column("payment", sa.Text()),
            sa.Column("updated_at", TS, server_default=sa.func.now()),
        )
    if "store_webhook_events" not in existing:
        op.create_table(
            "store_webhook_events",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("platform", sa.String(10), nullable=False),
            sa.Column("dedupe_key", sa.String(64), nullable=False),
            sa.Column("event_name", sa.String(80), nullable=False, server_default=""),
            sa.Column("merchant_id", sa.String(64)),
            sa.Column("created_at", TS, server_default=sa.func.now()),
            sa.UniqueConstraint("platform", "dedupe_key", name="uq_store_webhook_dedupe"),
        )
    if "store_oauth_nonces" not in existing:
        op.create_table(
            "store_oauth_nonces",
            sa.Column("nonce", sa.String(64), primary_key=True),
            sa.Column("project_id", UUID, sa.ForeignKey("client_projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("platform", sa.String(10), nullable=False),
            sa.Column("portal_token_version", sa.Integer(), nullable=False),
            sa.Column("auth_kind", sa.String(8), nullable=False),
            sa.Column("expires_at", TS, nullable=False),
            sa.Column("used_at", TS),
            sa.Column("created_at", TS, server_default=sa.func.now()),
        )
        op.create_index("ix_store_oauth_nonces_project_id", "store_oauth_nonces", ["project_id"])


def downgrade() -> None:
    op.drop_table("store_oauth_nonces")
    op.drop_table("store_webhook_events")
    op.drop_table("store_policies")
    op.drop_table("store_connections")
