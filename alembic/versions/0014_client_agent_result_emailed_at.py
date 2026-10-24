"""client_agents.result_emailed_at: when an agent result was emailed to the client.

NULL means the result was never confirmed sent. Idempotent: skips the column if
the startup self-heal already added it.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("client_agents")}
    if "result_emailed_at" not in cols:
        op.add_column("client_agents", sa.Column("result_emailed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("client_agents")}
    if "result_emailed_at" in cols:
        op.drop_column("client_agents", "result_emailed_at")
