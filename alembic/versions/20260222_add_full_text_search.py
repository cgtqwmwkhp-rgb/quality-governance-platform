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
    op.execute(
        "DO $$ BEGIN "
        "  EXECUTE 'CREATE EXTENSION IF NOT EXISTS pg_trgm'; "
        "EXCEPTION WHEN OTHERS THEN "
        "  RAISE NOTICE 'pg_trgm extension not available: %', SQLERRM; "
        "END $$"
    )

    for table, (field_a, field_b) in TABLES.items():
        tsvector_expr = (
            f"to_tsvector(''english'', "
            f"COALESCE(NEW.{field_a}, '''') || '' '' || COALESCE(NEW.{field_b}, ''''))"
        )
        backfill_expr = (
            f"to_tsvector(''english'', "
            f"COALESCE({field_a}, '''') || '' '' || COALESCE({field_b}, ''''))"
        )
        op.execute(
            f"DO $$ BEGIN "
            f"  IF EXISTS (SELECT 1 FROM information_schema.tables "
            f"    WHERE table_name = '{table}') THEN "
            f"    EXECUTE 'ALTER TABLE {table} "
            f"      ADD COLUMN IF NOT EXISTS search_vector tsvector'; "
            f"    EXECUTE 'CREATE INDEX IF NOT EXISTS ix_{table}_search_vector "
            f"      ON {table} USING gin(search_vector)'; "
            f"    EXECUTE 'CREATE OR REPLACE FUNCTION {table}_search_vector_update() "
            f"      RETURNS trigger AS $fn$ "
            f"      BEGIN "
            f"        NEW.search_vector := {tsvector_expr}; "
            f"        RETURN NEW; "
            f"      END; "
            f"      $fn$ LANGUAGE plpgsql'; "
            f"    EXECUTE 'DROP TRIGGER IF EXISTS {table}_search_vector_trigger "
            f"      ON {table}'; "
            f"    EXECUTE 'CREATE TRIGGER {table}_search_vector_trigger "
            f"      BEFORE INSERT OR UPDATE OF {field_a}, {field_b} "
            f"      ON {table} "
            f"      FOR EACH ROW EXECUTE FUNCTION {table}_search_vector_update()'; "
            f"    EXECUTE 'UPDATE {table} SET search_vector = {backfill_expr}'; "
            f"  END IF; "
            f"EXCEPTION WHEN OTHERS THEN "
            f"  RAISE NOTICE 'FTS skip for {table}: %', SQLERRM; "
            f"END $$"
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
