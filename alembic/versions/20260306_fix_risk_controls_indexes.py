"""Add missing FK indexes on risk_controls table.

Revision ID: 20260306_rc_idx
Revises: 20260306_ck_lower
Create Date: 2026-03-06

The 20260221_add_foreign_key_indexes migration referenced the wrong table name
(risk_mitigations instead of risk_controls), so these indexes were never created.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260306_rc_idx"
down_revision: Union[str, None] = "20260306_ck_lower"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXES = [
    ("ix_risk_controls_risk_id", "risk_controls", "risk_id"),
    ("ix_risk_controls_owner_id", "risk_controls", "owner_id"),
]


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for idx_name, table, column in INDEXES:
        if not inspector.has_table(table):
            continue
        if column not in {col["name"] for col in inspector.get_columns(table)}:
            continue
        if idx_name in {index["name"] for index in inspector.get_indexes(table)}:
            continue
        conn.execute(sa.text(f"CREATE INDEX {idx_name} ON {table} ({column})"))


def downgrade() -> None:
    for idx_name, _, _ in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {idx_name}")
