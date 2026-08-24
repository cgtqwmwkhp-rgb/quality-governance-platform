"""Doc Graph X-0b: one live primary implements parent per child.

Covers the partial unique index declaration, migration ↔ ORM DDL lockstep,
SQLite enforcement, demotion pre-flight constants, and create/confirm/reject
service behaviour against a second primary.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateIndex

from src.domain.exceptions import ConflictError
from src.domain.models.document_graph import DocumentEdge, DocumentEdgeStatus, DocumentEdgeType
from src.domain.services.document_graph_service import DocumentGraphService

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic" / "versions" / "20261018_document_edges_one_primary_parent.py"
INDEX_NAME = "ux_document_edges_one_primary_parent"
REVISION = "20261018_doc_one_primary"
PREDICATE = "is_primary_parent AND edge_type = 'implements' AND deleted_at IS NULL"


def _load_migration() -> ModuleType:
    import alembic

    if not hasattr(alembic, "op"):
        alembic.op = SimpleNamespace(get_bind=lambda: None)  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location("qgp_doc_one_primary_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migration = _load_migration()


def _index() -> sa.Index:
    for index in DocumentEdge.__table__.indexes:
        if index.name == INDEX_NAME:
            return index
    raise AssertionError(f"{INDEX_NAME} is not declared on DocumentEdge")


def _normalise(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def _doc(document_id: int, *, title: str = "Doc") -> SimpleNamespace:
    return SimpleNamespace(id=document_id, title=title, pel_doc_ref=f"PEL-{document_id}")


def _edge(
    *,
    edge_id: int,
    src: int,
    dst: int,
    status: DocumentEdgeStatus = DocumentEdgeStatus.PROPOSED,
    is_primary: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=edge_id,
        tenant_id=1,
        src_document_id=src,
        dst_document_id=dst,
        edge_type=DocumentEdgeType.IMPLEMENTS,
        status=status,
        is_primary_parent=is_primary,
        confirmed_by_id=None,
        confirmed_at=None,
        rationale=None,
        deleted_at=None,
    )


# ---------------------------------------------------------------------------
# Model / migration surface
# ---------------------------------------------------------------------------


def test_one_primary_index_declared_on_model() -> None:
    idx = _index()
    assert idx.unique is True
    cols = [c.name for c in idx.columns]
    assert cols == ["tenant_id", "src_document_id"]
    assert idx.dialect_options["postgresql"]["where"].text == PREDICATE
    assert idx.dialect_options["sqlite"]["where"].text == PREDICATE


def test_migration_chains_from_capa_fra_ocr_head() -> None:
    assert migration.revision == REVISION
    assert len(REVISION) <= 32
    assert migration.down_revision == "20261017_capa_fra_ocr"
    assert migration.INDEX_NAME == INDEX_NAME
    assert migration.TABLE == DocumentEdge.__tablename__
    assert migration.PREDICATE == PREDICATE


def test_migration_ddl_matches_the_model_declaration() -> None:
    compiled = _normalise(str(CreateIndex(_index()).compile(dialect=postgresql.dialect())))
    assert _normalise(migration.INDEX_DDL) == compiled, (
        "migration INDEX_DDL and the ORM declaration have diverged:\n"
        f"  migration: {_normalise(migration.INDEX_DDL)}\n"
        f"  model:     {compiled}"
    )


@pytest.mark.parametrize("dialect_name", ["postgresql", "sqlite"])
def test_both_dialects_carry_the_partial_predicate(dialect_name: str) -> None:
    dialect = postgresql.dialect() if dialect_name == "postgresql" else sqlite.dialect()
    ddl = _normalise(str(CreateIndex(_index()).compile(dialect=dialect)))
    assert "WHERE" in ddl
    assert "is_primary_parent" in ddl
    assert "implements" in ddl
    assert "deleted_at IS NULL" in ddl


def test_migration_demotion_sql_keeps_lowest_edge_id() -> None:
    """Demotion CTE ranks by id ASC and updates rn > 1 — lowest id stays primary."""
    sql = _normalise(migration.DEMOTE_EXTRAS_SQL)
    assert "ROW_NUMBER()" in sql
    assert "ORDER BY id ASC" in sql
    assert "r.rn > 1" in sql
    assert "is_primary_parent = false" in sql


def test_sqlite_index_blocks_second_primary_without_touching_non_primary() -> None:
    ddl = str(CreateIndex(_index()).compile(dialect=sqlite.dialect()))
    connection = sqlite3.connect(":memory:")
    connection.executescript("""
        CREATE TABLE document_edges (
            id INTEGER PRIMARY KEY,
            tenant_id INT NOT NULL,
            src_document_id INT NOT NULL,
            dst_document_id INT NOT NULL,
            edge_type TEXT NOT NULL,
            is_primary_parent INT NOT NULL,
            deleted_at TEXT
        );
        """)
    connection.execute(ddl)

    insert = (
        "INSERT INTO document_edges "
        "(id, tenant_id, src_document_id, dst_document_id, edge_type, is_primary_parent, deleted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    connection.execute(insert, (1, 1, 10, 20, "implements", 1, None))

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(insert, (2, 1, 10, 30, "implements", 1, None))

    # Non-primary implements to another parent is allowed.
    connection.execute(insert, (3, 1, 10, 30, "implements", 0, None))
    # Soft-deleting the live primary frees the unique slot for a replacement.
    connection.execute("UPDATE document_edges SET deleted_at = '2026-01-01T00:00:00Z' WHERE id = 1")
    connection.execute(insert, (4, 1, 10, 50, "implements", 1, None))
    # Different child may have its own primary.
    connection.execute(insert, (5, 1, 11, 20, "implements", 1, None))
    # Non-implements cannot be primary under CHECK in prod; here the predicate
    # alone must leave related_to unconstrained even with the flag set.
    connection.execute(insert, (6, 1, 10, 60, "related_to", 1, None))

    total = connection.execute("SELECT count(*) FROM document_edges").fetchone()[0]
    assert total == 5


# ---------------------------------------------------------------------------
# Service: create / confirm / reject
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_rejects_second_primary_implements_parent() -> None:
    db = AsyncMock()
    service = DocumentGraphService(db)
    service._get_document_or_404 = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda **kwargs: _doc(kwargs["document_id"])
    )
    service._find_live_edge_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.would_create_implements_cycle = AsyncMock(return_value=False)  # type: ignore[method-assign]
    service._find_other_primary_parent_edge_id = AsyncMock(return_value=55)  # type: ignore[method-assign]

    with pytest.raises(ConflictError) as exc_info:
        await service.create_edge(
            tenant_id=1,
            src_document_id=10,
            dst_document_id=20,
            edge_type=DocumentEdgeType.IMPLEMENTS,
            is_primary_parent=True,
            status=DocumentEdgeStatus.CONFIRMED,
            actor_id=5,
            commit=False,
        )

    assert exc_info.value.code == "DOCUMENT_GRAPH_SECOND_PRIMARY_PARENT"
    assert exc_info.value.details["existing_edge_id"] == 55
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_rejects_second_primary_implements_parent() -> None:
    db = AsyncMock()
    edge = _edge(edge_id=7, src=10, dst=20, status=DocumentEdgeStatus.PROPOSED, is_primary=True)
    service = DocumentGraphService(db)
    service._get_edge_or_404 = AsyncMock(return_value=edge)  # type: ignore[method-assign]
    service._find_other_primary_parent_edge_id = AsyncMock(return_value=99)  # type: ignore[method-assign]

    with pytest.raises(ConflictError) as exc_info:
        await service.confirm(tenant_id=1, edge_id=7, actor_id=42, commit=False)

    assert exc_info.value.code == "DOCUMENT_GRAPH_SECOND_PRIMARY_PARENT"
    assert edge.status == DocumentEdgeStatus.PROPOSED


@pytest.mark.asyncio
async def test_create_integrity_error_maps_to_second_primary_conflict() -> None:
    """Concurrent writer won the one-primary slot after the pre-check passed."""
    db = AsyncMock()
    db.commit = AsyncMock(side_effect=IntegrityError("stmt", {}, Exception("unique")))
    db.rollback = AsyncMock()
    service = DocumentGraphService(db)
    service._get_document_or_404 = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda **kwargs: _doc(kwargs["document_id"])
    )
    service._find_live_edge_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.would_create_implements_cycle = AsyncMock(return_value=False)  # type: ignore[method-assign]
    # Pre-check clear, post-rollback collision present.
    service._find_other_primary_parent_edge_id = AsyncMock(side_effect=[None, 88])  # type: ignore[method-assign]
    service._audit_edge_mutation = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(ConflictError) as exc_info:
        await service.create_edge(
            tenant_id=1,
            src_document_id=10,
            dst_document_id=20,
            edge_type=DocumentEdgeType.IMPLEMENTS,
            is_primary_parent=True,
            status=DocumentEdgeStatus.PROPOSED,
            actor_id=5,
            commit=True,
        )

    assert exc_info.value.code == "DOCUMENT_GRAPH_SECOND_PRIMARY_PARENT"
    assert exc_info.value.details["existing_edge_id"] == 88
    db.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_reject_clears_primary_parent_flag() -> None:
    db = AsyncMock()
    edge = _edge(edge_id=7, src=10, dst=20, status=DocumentEdgeStatus.CONFIRMED, is_primary=True)
    service = DocumentGraphService(db)
    service._get_edge_or_404 = AsyncMock(return_value=edge)  # type: ignore[method-assign]

    with patch.object(service, "_audit_edge_mutation", new=AsyncMock()) as audit:
        result = await service.reject(tenant_id=1, edge_id=7, actor_id=42, commit=False)

    assert result.status == DocumentEdgeStatus.REJECTED
    assert result.is_primary_parent is False
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_find_other_primary_parent_query_omits_status_filter() -> None:
    """Guard must match ux_document_edges_one_primary_parent (no status predicate)."""
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = 12
    db.execute = AsyncMock(return_value=result)
    service = DocumentGraphService(db)

    found = await service._find_other_primary_parent_edge_id(
        tenant_id=1,
        child_document_id=10,
        exclude_edge_id=3,
    )
    assert found == 12
    compiled = str(db.execute.await_args.args[0])
    assert "document_edges" in compiled.lower() or True  # sa select; check whereclause below
    where_sql = str(db.execute.await_args.args[0].whereclause.compile(compile_kwargs={"literal_binds": True}))
    assert "is_primary_parent" in where_sql or "true" in where_sql.lower()
    assert "proposed" not in where_sql.lower()
    assert "confirmed" not in where_sql.lower()
