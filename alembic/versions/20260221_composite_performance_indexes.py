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

def _all_columns_exist(inspector: sa.Inspector, table: str, columns: list[str]) -> bool:
    """Return True only if every column in the list exists on the table."""
    if not inspector.has_table(table):
        return False
    existing_columns = {column["name"] for column in inspector.get_columns(table)}
    return all(column in existing_columns for column in columns)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in _TABLES:
        for suffix, columns in _COMPOSITE_INDEXES:
            if _all_columns_exist(inspector, table, columns):
                idx_name = f"ix_{table}_{suffix}"
                col_list = ", ".join(columns)
                op.execute(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} "
                    f"ON {table} ({col_list})"
                )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in reversed(_TABLES):
        if not inspector.has_table(table):
            continue
        existing_indexes = {index["name"] for index in inspector.get_indexes(table)}
        for suffix, _columns in reversed(_COMPOSITE_INDEXES):
            idx_name = f"ix_{table}_{suffix}"
            if idx_name in existing_indexes:
                op.drop_index(idx_name, table_name=table)
