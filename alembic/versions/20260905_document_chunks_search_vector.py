"""Harden document_chunks tenancy and add FTS search_vector (PR1 foundation).

Revision ID: 20260905_doc_chunk_fts
Revises: 20260904_case_soft_del
Create Date: 2026-09-05

Chunks already store full text for RAG, but Global Search never queries them.
This migration is foundation only — no SearchService wiring, no RLS on
document_chunks (paired later with Celery GUC binding):

1. Backfill tenant_id from parent documents
2. Delete orphan chunks (no parent row; FK CASCADE should make this rare)
3. Guarded NOT NULL on tenant_id when residual NULLs are zero
4. Add nullable search_vector tsvector + GIN index + maintain trigger
5. Batch backfill search_vector by id range
6. Composite index (tenant_id, document_id) for tenant-scoped retrieval
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260905_doc_chunk_fts"
down_revision: Union[str, Sequence[str], None] = "20260904_case_soft_del"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

TABLE = "document_chunks"
SEARCH_VECTOR_BATCH = 5000


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        logger.info("Skipping %s (non-PostgreSQL)", revision)
        return

    # 1) Backfill tenant_id from parent documents
    op.execute(sa.text("""
            UPDATE document_chunks AS c
            SET tenant_id = d.tenant_id
            FROM documents AS d
            WHERE d.id = c.document_id
              AND c.tenant_id IS NULL
              AND d.tenant_id IS NOT NULL
            """))
    logger.info("Backfilled document_chunks.tenant_id from documents")

    # 2) Delete orphan chunks with no parent (should be rare; FK CASCADE)
    orphan_count = int(op.get_bind().execute(sa.text("""
                SELECT COUNT(*)
                FROM document_chunks AS c
                WHERE NOT EXISTS (
                    SELECT 1 FROM documents AS d WHERE d.id = c.document_id
                )
                """)).scalar() or 0)
    if orphan_count:
        op.execute(sa.text("""
                DELETE FROM document_chunks AS c
                WHERE NOT EXISTS (
                    SELECT 1 FROM documents AS d WHERE d.id = c.document_id
                )
                """))
    logger.info("Deleted %s orphan document_chunks row(s)", orphan_count)
    print(f"Deleted {orphan_count} orphan document_chunks row(s)")

    # 3) Guarded NOT NULL — only when zero NULLs remain (house-style DO $$)
    op.execute(sa.text("""
            DO $$
            DECLARE
                null_count integer;
            BEGIN
                SELECT COUNT(*) INTO null_count
                FROM document_chunks
                WHERE tenant_id IS NULL;

                IF null_count = 0 THEN
                    EXECUTE 'ALTER TABLE document_chunks ALTER COLUMN tenant_id SET NOT NULL';
                    RAISE NOTICE 'Enforced NOT NULL on document_chunks.tenant_id';
                ELSE
                    RAISE NOTICE
                        'Skipping NOT NULL on document_chunks.tenant_id: % nulls remain',
                        null_count;
                END IF;
            END $$
            """))

    # 4–6) search_vector column, GIN index, maintain trigger
    # IMPORTANT: do not nest named dollar-quotes ($fn$) inside a DO $$ block when
    # running under asyncpg/SQLAlchemy — `$fn` is parsed as a bind parameter and the
    # whole DO block fails into EXCEPTION WHEN OTHERS (silent skip). Use top-level
    # statements with anonymous $$ only, matching a safe subset of 20260222 FTS.
    op.execute(sa.text(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS search_vector tsvector"))
    op.execute(sa.text(f"CREATE INDEX IF NOT EXISTS ix_{TABLE}_search_vector " f"ON {TABLE} USING gin(search_vector)"))
    op.execute(sa.text(f"""
            CREATE OR REPLACE FUNCTION {TABLE}_search_vector_update()
            RETURNS trigger AS $$
            BEGIN
              NEW.search_vector := to_tsvector(
                'english',
                COALESCE(NEW.heading, '') || ' ' || COALESCE(NEW.content, '')
              );
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """))
    op.execute(sa.text(f"DROP TRIGGER IF EXISTS {TABLE}_search_vector_trigger ON {TABLE}"))
    op.execute(sa.text(f"""
            CREATE TRIGGER {TABLE}_search_vector_trigger
            BEFORE INSERT OR UPDATE OF heading, content
            ON {TABLE}
            FOR EACH ROW EXECUTE FUNCTION {TABLE}_search_vector_update()
            """))

    # 7) Backfill search_vector in id-range batches
    bind = op.get_bind()
    bounds = bind.execute(sa.text(f"SELECT MIN(id), MAX(id) FROM {TABLE}")).one()
    min_id, max_id = bounds[0], bounds[1]
    if min_id is not None and max_id is not None:
        lo = int(min_id)
        hi_bound = int(max_id)
        batches = 0
        backfill_sql = (
            f"UPDATE {TABLE} SET search_vector = to_tsvector('english', "
            f"COALESCE(heading, '') || ' ' || COALESCE(content, '')) "
            f"WHERE id >= :lo AND id <= :hi AND search_vector IS NULL"
        )
        while lo <= hi_bound:
            hi = lo + SEARCH_VECTOR_BATCH - 1
            bind.execute(sa.text(backfill_sql), {"lo": lo, "hi": hi})
            batches += 1
            lo = hi + 1
        logger.info(
            "Backfilled %s.search_vector in %s id-range batch(es) (%s..%s)",
            TABLE,
            batches,
            min_id,
            max_id,
        )
        print(f"Backfilled {TABLE}.search_vector in {batches} id-range batch(es)")
    else:
        logger.info("No %s rows to backfill for search_vector", TABLE)

    # 8) Composite tenant/document index for scoped retrieval
    op.execute(sa.text("""
            CREATE INDEX IF NOT EXISTS ix_document_chunks_tenant_document
            ON document_chunks (tenant_id, document_id)
            """))


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        logger.info("Skipping %s downgrade (non-PostgreSQL)", revision)
        return

    op.execute(sa.text("DROP INDEX IF EXISTS ix_document_chunks_tenant_document"))
    op.execute(sa.text(f"DROP TRIGGER IF EXISTS {TABLE}_search_vector_trigger ON {TABLE}"))
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {TABLE}_search_vector_update()"))
    op.execute(sa.text(f"DROP INDEX IF EXISTS ix_{TABLE}_search_vector"))
    op.execute(sa.text(f"ALTER TABLE {TABLE} DROP COLUMN IF EXISTS search_vector"))

    # Restore nullable tenant_id (inverse of guarded NOT NULL)
    op.execute(sa.text("""
            DO $$ BEGIN
              EXECUTE 'ALTER TABLE document_chunks ALTER COLUMN tenant_id DROP NOT NULL';
            EXCEPTION WHEN OTHERS THEN
              RAISE NOTICE 'document_chunks.tenant_id DROP NOT NULL skip: %', SQLERRM;
            END $$
            """))
