"""Add PostgreSQL full-text search with tsvector columns, GIN indexes, and triggers.

Revision ID: 20260222_full_text_search
Revises: 20260222_add_rls_policies
Create Date: 2026-02-22

Enables the pg_trgm extension for fuzzy matching, then adds a search_vector
(tsvector) column to incidents, complaints, risks, and near_misses.  Each
column is backed by a GIN index and kept up-to-date via a BEFORE INSERT/UPDATE
trigger that concatenates the relevant text fields.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260222_full_text_search"
down_revision: Union[str, None] = "20260222_add_rls_policies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = {
    "incidents": ("title", "description"),
    "complaints": ("title", "description"),
    "risks": ("title", "description"),
    "near_misses": ("location", "description"),
}


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    for table, (field_a, field_b) in TABLES.items():
        op.execute(
            f"ALTER TABLE {table} "
            f"ADD COLUMN IF NOT EXISTS search_vector tsvector"
        )

        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_{table}_search_vector "
            f"ON {table} USING gin(search_vector)"
        )

        tsvector_expr = (
            f"to_tsvector('english', "
            f"COALESCE(NEW.{field_a}, '') || ' ' || COALESCE(NEW.{field_b}, ''))"
        )
        op.execute(
            f"CREATE OR REPLACE FUNCTION {table}_search_vector_update() "
            f"RETURNS trigger AS $$ "
            f"BEGIN "
            f"  NEW.search_vector := {tsvector_expr}; "
            f"  RETURN NEW; "
            f"END; "
            f"$$ LANGUAGE plpgsql"
        )

        op.execute(
            f"DROP TRIGGER IF EXISTS {table}_search_vector_trigger ON {table}"
        )
        op.execute(
            f"CREATE TRIGGER {table}_search_vector_trigger "
            f"BEFORE INSERT OR UPDATE OF {field_a}, {field_b} "
            f"ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {table}_search_vector_update()"
        )

        backfill_expr = (
            f"to_tsvector('english', "
            f"COALESCE({field_a}, '') || ' ' || COALESCE({field_b}, ''))"
        )
        op.execute(
            f"UPDATE {table} SET search_vector = {backfill_expr}"
        )


def downgrade() -> None:
    for table in reversed(list(TABLES)):
        op.execute(
            f"DROP TRIGGER IF EXISTS {table}_search_vector_trigger ON {table}"
        )
        op.execute(
            f"DROP FUNCTION IF EXISTS {table}_search_vector_update()"
        )
        op.execute(
            f"DROP INDEX IF EXISTS ix_{table}_search_vector"
        )
        op.execute(
            f"ALTER TABLE {table} DROP COLUMN IF EXISTS search_vector"
        )

    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
