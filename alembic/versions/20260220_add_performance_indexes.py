"""Add indexes for common query patterns (tenant_id, status, created_at).

Revision ID: 20260220_perf_indexes
Revises: 20260220_token_blacklist
Create Date: 2026-02-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260220_perf_indexes"
down_revision: Union[str, None] = "20260220_token_blacklist"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = [
    "incidents",
    "risks",
    "audits",
    "complaints",
    "documents",
    "near_miss_reports",
]

_COLUMNS = ["tenant_id", "status", "created_at"]

_COL_EXISTS = sa.text(
    "SELECT EXISTS ("
    "  SELECT 1 FROM information_schema.columns"
    "  WHERE table_name = :t AND column_name = :c"
    ")"
)


def upgrade() -> None:
    conn = op.get_bind()
    for table in _TABLES:
        for column in _COLUMNS:
            if conn.execute(_COL_EXISTS, {"t": table, "c": column}).scalar():
                op.execute(
                    f"CREATE INDEX IF NOT EXISTS ix_{table}_{column} "
                    f"ON {table} ({column})"
                )


def downgrade() -> None:
    conn = op.get_bind()
    for table in reversed(_TABLES):
        for column in reversed(_COLUMNS):
            idx = f"ix_{table}_{column}"
            result = conn.execute(
                sa.text(
                    "SELECT EXISTS ("
                    "  SELECT 1 FROM pg_indexes"
                    "  WHERE indexname = :idx"
                    ")"
                ),
                {"idx": idx},
            )
            if result.scalar():
                op.drop_index(idx, table_name=table)
