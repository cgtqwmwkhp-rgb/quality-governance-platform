"""Add deleted_at column for soft delete support.

Adds the deleted_at column to tables using SoftDeleteMixin:
users, incidents, risks, complaints.

Revision ID: 20260222_soft_delete
Revises: 20260222_full_text_search
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260222_soft_delete"
down_revision: Union[str, None] = "20260222_full_text_search"
branch_labels = None
depends_on = None

TABLES = ["users", "incidents", "risks", "complaints"]


def upgrade() -> None:
    inspector = op.get_bind().dialect.name != "postgresql" and sa.inspect(op.get_bind())
    if inspector:
        for table in TABLES:
            if inspector.has_table(table) and "deleted_at" not in {col["name"] for col in inspector.get_columns(table)}:
                op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        return

    for table in TABLES:
        op.execute(
            f"DO $$ BEGIN "
            f"  IF EXISTS ("
            f"    SELECT 1 FROM information_schema.tables "
            f"    WHERE table_name = '{table}'"
            f"  ) AND NOT EXISTS ("
            f"    SELECT 1 FROM information_schema.columns "
            f"    WHERE table_name = '{table}' AND column_name = 'deleted_at'"
            f"  ) THEN "
            f"    EXECUTE 'ALTER TABLE {table} "
            f"      ADD COLUMN deleted_at TIMESTAMPTZ'; "
            f"  END IF; "
            f"EXCEPTION WHEN OTHERS THEN "
            f"  RAISE NOTICE 'deleted_at skip for {table}: %', SQLERRM; "
            f"END $$"
        )


def downgrade() -> None:
    inspector = op.get_bind().dialect.name != "postgresql" and sa.inspect(op.get_bind())
    if inspector:
        for table in TABLES:
            if inspector.has_table(table) and "deleted_at" in {col["name"] for col in inspector.get_columns(table)}:
                op.drop_column(table, "deleted_at")
        return

    for table in TABLES:
        op.execute(
            f"DO $$ BEGIN "
            f"  EXECUTE 'ALTER TABLE {table} DROP COLUMN IF EXISTS deleted_at'; "
            f"EXCEPTION WHEN OTHERS THEN NULL; "
            f"END $$"
        )
