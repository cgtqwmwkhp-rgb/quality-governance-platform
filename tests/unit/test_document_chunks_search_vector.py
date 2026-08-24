"""Unit tests for DocumentChunk tenancy + FTS search_vector foundation (PR1)."""

from __future__ import annotations

from pathlib import Path

from src.domain.models.document import DocumentChunk

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260905_document_chunks_search_vector.py"


def test_document_chunk_tenant_id_is_required() -> None:
    column = DocumentChunk.__table__.c.tenant_id
    assert column.nullable is False


def test_document_chunk_search_vector_column_exists() -> None:
    assert "search_vector" in DocumentChunk.__table__.c
    column = DocumentChunk.__table__.c.search_vector
    assert column.nullable is True
    assert DocumentChunk.__mapper__.get_property("search_vector").deferred is True


def test_document_chunk_fts_migration_is_postgres_only_and_chained() -> None:
    body = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "20260905_doc_chunk_fts"' in body
    assert 'down_revision: Union[str, Sequence[str], None] = "20260904_case_soft_del"' in body
    assert 'dialect.name != "postgresql"' in body
    assert "ix_document_chunks_tenant_document" in body
    assert "ix_{TABLE}_search_vector" in body or "ix_document_chunks_search_vector" in body
    assert "search_vector_trigger" in body
    assert "Skipping NOT NULL on document_chunks.tenant_id" in body
    assert "tenant_id = 1" not in body
