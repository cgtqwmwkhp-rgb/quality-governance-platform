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
    for idx_name, table, column in INDEXES:
        conn.execute(
            sa.text(
                f"DO $$ BEGIN "
                f"  IF EXISTS (SELECT 1 FROM information_schema.tables "
                f"    WHERE table_name = '{table}') "
                f"  AND EXISTS (SELECT 1 FROM information_schema.columns "
                f"    WHERE table_name = '{table}' AND column_name = '{column}') "
                f"  AND NOT EXISTS (SELECT 1 FROM pg_indexes "
                f"    WHERE indexname = '{idx_name}') THEN "
                f"    EXECUTE 'CREATE INDEX {idx_name} ON {table} ({column})'; "
                f"  END IF; "
                f"EXCEPTION WHEN OTHERS THEN "
                f"  RAISE NOTICE 'skip {idx_name}: %', SQLERRM; "
                f"END $$"
            )
        )


def downgrade() -> None:
    for idx_name, _, _ in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {idx_name}")
