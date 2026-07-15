"""Create failed_tasks DLQ table (was ORM-only).

Revision ID: 20260718_failed_tasks
Revises: 20260717_partner_api_tokens
Create Date: 2026-07-18

Idempotent: skips create when the table already exists (some envs may have
partially applied tenant backfills that assumed this table).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260718_failed_tasks"
down_revision: Union[str, Sequence[str], None] = "20260717_partner_api_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    if _inspector().has_table("failed_tasks"):
        return

    op.create_table(
        "failed_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("task_name", sa.String(length=255), nullable=False),
        sa.Column("task_id", sa.String(length=255), nullable=False),
        sa.Column("exception", sa.Text(), nullable=False),
        sa.Column("args", sa.Text(), nullable=True),
        sa.Column("kwargs", sa.Text(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=False),
        sa.Column("retried", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("retried_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_failed_tasks_tenant_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_failed_tasks_task_id"),
    )
    op.create_index("ix_failed_tasks_tenant_id", "failed_tasks", ["tenant_id"])
    op.create_index("ix_failed_tasks_retried", "failed_tasks", ["retried"])


def downgrade() -> None:
    if not _inspector().has_table("failed_tasks"):
        return
    op.drop_index("ix_failed_tasks_retried", table_name="failed_tasks")
    op.drop_index("ix_failed_tasks_tenant_id", table_name="failed_tasks")
    op.drop_table("failed_tasks")
