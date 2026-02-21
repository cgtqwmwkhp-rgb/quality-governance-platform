"""Add indexes for common query patterns (tenant_id, status, created_at).

Revision ID: 20260220_perf_indexes
Revises: 20260220_token_blacklist
Create Date: 2026-02-20
"""

from typing import Sequence, Union

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


def upgrade() -> None:
    for table in _TABLES:
        for column in _COLUMNS:
            try:
                op.create_index(
                    f"ix_{table}_{column}",
                    table,
                    [column],
                    if_not_exists=True,
                )
            except Exception:
                pass


def downgrade() -> None:
    for table in reversed(_TABLES):
        for column in reversed(_COLUMNS):
            try:
                op.drop_index(f"ix_{table}_{column}", table_name=table)
            except Exception:
                pass
