"""Add tenant_id + cost to the execution tracking tables.

Purely additive migration preparing the database for the architectural
middleware layer (tenant context isolation) and API cost tracking:

- ``workflow_executions``: + ``tenant_id`` (default ``system``), + ``cost`` (``0.0``)
- ``step_executions``:     + ``tenant_id`` (default ``system``), + ``cost`` (``0.0``)

No existing column, constraint, index or data is dropped, renamed or modified.

Revision ID: 0001
Revises:
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ADDITIVE_COLUMNS = [
    ("workflow_executions", "tenant_id", sa.String(64), "system"),
    ("workflow_executions", "cost", sa.Numeric(12, 4), "0"),
    ("step_executions", "tenant_id", sa.String(64), "system"),
    ("step_executions", "cost", sa.Numeric(12, 4), "0"),
]


def upgrade() -> None:
    for table, column, type_, default in ADDITIVE_COLUMNS:
        op.add_column(
            table,
            sa.Column(
                column,
                type_,
                nullable=False,
                server_default=sa.text(f"'{default}'"),
            ),
        )
    # Indexes mirror the ``index=True`` declarations on the models.
    op.create_index("ix_workflow_executions_tenant_id", "workflow_executions", ["tenant_id"])
    op.create_index("ix_step_executions_tenant_id", "step_executions", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_step_executions_tenant_id", table_name="step_executions")
    op.drop_index("ix_workflow_executions_tenant_id", table_name="workflow_executions")
    for table, column, _type_, _default in reversed(ADDITIVE_COLUMNS):
        op.drop_column(table, column)