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

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for table in _TABLES:
        if not inspector.has_table(table):
            continue
        table_columns = {column["name"] for column in inspector.get_columns(table)}
        for column in _COLUMNS:
            if column in table_columns:
                op.execute(
                    f"CREATE INDEX IF NOT EXISTS ix_{table}_{column} "
                    f"ON {table} ({column})"
                )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for table in reversed(_TABLES):
        if not inspector.has_table(table):
            continue
        existing_indexes = {index["name"] for index in inspector.get_indexes(table)}
        for column in reversed(_COLUMNS):
            idx = f"ix_{table}_{column}"
            if idx in existing_indexes:
                op.drop_index(idx, table_name=table)
