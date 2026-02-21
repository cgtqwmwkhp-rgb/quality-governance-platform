"""Add composite indexes for common multi-column query patterns.

Revision ID: 20260221_composite_idx
Revises: 20260220_capa_actions
Create Date: 2026-02-21

Adds composite indexes on (tenant_id, created_at) and (tenant_id, status)
for high-traffic tables to speed up paginated list queries with tenant
isolation.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260221_composite_idx"
down_revision: Union[str, None] = "20260220_capa_actions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = [
    "incidents",
    "risks",
    "audit_templates",
    "audit_runs",
    "complaints",
    "documents",
    "policies",
]

_COMPOSITE_INDEXES: list[tuple[str, list[str]]] = [
    ("tenant_id_created_at", ["tenant_id", "created_at"]),
    ("tenant_id_status", ["tenant_id", "status"]),
]

_COL_EXISTS = sa.text(
    "SELECT EXISTS ("
    "  SELECT 1 FROM information_schema.columns"
    "  WHERE table_name = :t AND column_name = :c"
    ")"
)


def _all_columns_exist(conn, table: str, columns: list[str]) -> bool:
    """Return True only if every column in the list exists on the table."""
    return all(
        conn.execute(_COL_EXISTS, {"t": table, "c": col}).scalar()
        for col in columns
    )


def upgrade() -> None:
    conn = op.get_bind()
    for table in _TABLES:
        for suffix, columns in _COMPOSITE_INDEXES:
            if _all_columns_exist(conn, table, columns):
                idx_name = f"ix_{table}_{suffix}"
                col_list = ", ".join(columns)
                op.execute(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} "
                    f"ON {table} ({col_list})"
                )


def downgrade() -> None:
    conn = op.get_bind()
    for table in reversed(_TABLES):
        for suffix, _columns in reversed(_COMPOSITE_INDEXES):
            idx_name = f"ix_{table}_{suffix}"
            result = conn.execute(
                sa.text(
                    "SELECT EXISTS ("
                    "  SELECT 1 FROM pg_indexes"
                    "  WHERE indexname = :idx"
                    ")"
                ),
                {"idx": idx_name},
            )
            if result.scalar():
                op.drop_index(idx_name, table_name=table)
