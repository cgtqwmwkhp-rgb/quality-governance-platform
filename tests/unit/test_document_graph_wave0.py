"""Doc Graph Wave 0: schema surface, cycle rejection, flag gate, confirm stamp."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.routes import document_graph as document_graph_routes
from src.core.config import settings
from src.domain.exceptions import ConflictError
from src.domain.models.document_graph import DocumentEdge, DocumentEdgeMethod, DocumentEdgeStatus, DocumentEdgeType
from src.domain.services.document_graph_service import DocumentGraphService, canonicalize_endpoints
from src.infrastructure.middleware.tenant_context import RLS_TABLES, TENANT_ISOLATION_PREDICATE

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic" / "versions" / "20261015_document_edges.py"
REVISION = "20261015_document_edges"
GRAPH_PREFIX = "/api/v1/document-graph"


def _load_migration(path: Path, module_name: str) -> ModuleType:
    import alembic

    if not hasattr(alembic, "op"):
        alembic.op = SimpleNamespace(get_bind=lambda: None)  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Model / migration surface
# ---------------------------------------------------------------------------


def test_document_edge_tablename_and_classification():
    assert DocumentEdge.__tablename__ == "document_edges"
    assert DocumentEdge.__data_classification__ == "C2_INTERNAL"


def test_tenant_id_not_null_and_document_fks():
    assert DocumentEdge.__table__.c.tenant_id.nullable is False
    assert DocumentEdge.__table__.c.src_document_id.nullable is False
    assert DocumentEdge.__table__.c.dst_document_id.nullable is False
    src_fks = {str(fk.target_fullname) for fk in DocumentEdge.__table__.c.src_document_id.foreign_keys}
    dst_fks = {str(fk.target_fullname) for fk in DocumentEdge.__table__.c.dst_document_id.foreign_keys}
    assert any(t.startswith("documents") for t in src_fks)
    assert any(t.startswith("documents") for t in dst_fks)


def test_authored_edge_types_exclude_lifecycle_derived():
    values = {m.value for m in DocumentEdgeType}
    assert values == {
        "implements",
        "requires_record",
        "references",
        "related_to",
        "conflicts_with",
    }
    assert "supersedes" not in values
    assert "derived_from" not in values


def test_partial_unique_live_index_declared():
    names = {idx.name for idx in DocumentEdge.__table__.indexes}
    assert "ux_document_edges_tenant_src_dst_type_live" in names
    live = next(
        idx for idx in DocumentEdge.__table__.indexes if idx.name == "ux_document_edges_tenant_src_dst_type_live"
    )
    assert live.unique is True
    assert live.dialect_options["postgresql"]["where"].text == "deleted_at IS NULL"
    assert live.dialect_options["sqlite"]["where"].text == "deleted_at IS NULL"


def test_migration_chains_from_doc_graph_pins_and_hardens_rls():
    migration = _load_migration(MIGRATION_PATH, "qgp_document_edges_migration")
    assert migration.revision == REVISION
    assert len(REVISION) <= 32
    assert migration.down_revision == "20261014_doc_graph_pins"
    assert migration.ADOPT_TABLES == ("document_edges",)
    assert migration.HARDENED_PREDICATE == TENANT_ISOLATION_PREDICATE
    assert "document_edges" in RLS_TABLES


def test_canonicalize_undirected_peer_types():
    assert canonicalize_endpoints(DocumentEdgeType.RELATED_TO, 9, 3) == (3, 9)
    assert canonicalize_endpoints(DocumentEdgeType.CONFLICTS_WITH, 2, 8) == (2, 8)
    assert canonicalize_endpoints(DocumentEdgeType.IMPLEMENTS, 9, 3) == (9, 3)


# ---------------------------------------------------------------------------
# Service: cycle rejection + confirm actor stamp
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_implements_rejects_cycle():
    db = AsyncMock()
    service = DocumentGraphService(db)
    service._get_document_or_404 = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda **kwargs: SimpleNamespace(
            id=kwargs["document_id"],
            pel_doc_ref=None,
        )
    )
    # No live row in the unique slot — cycle check is what must fire.
    service._find_live_edge_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.would_create_implements_cycle = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with pytest.raises(ConflictError) as exc_info:
        await service.create_edge(
            tenant_id=1,
            src_document_id=10,
            dst_document_id=20,
            edge_type=DocumentEdgeType.IMPLEMENTS,
            actor_id=5,
            commit=False,
        )

    assert exc_info.value.code == "DOCUMENT_GRAPH_IMPLEMENTS_CYCLE"
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_edge_rejects_live_duplicate():
    """A live (including rejected) row already occupies the unique slot → 409."""
    db = AsyncMock()
    service = DocumentGraphService(db)
    service._get_document_or_404 = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda **kwargs: SimpleNamespace(
            id=kwargs["document_id"],
            pel_doc_ref=None,
        )
    )
    service._find_live_edge_id = AsyncMock(return_value=99)  # type: ignore[method-assign]
    service.would_create_implements_cycle = AsyncMock(return_value=False)  # type: ignore[method-assign]

    with pytest.raises(ConflictError) as exc_info:
        await service.create_edge(
            tenant_id=1,
            src_document_id=10,
            dst_document_id=20,
            edge_type=DocumentEdgeType.REFERENCES,
            actor_id=5,
            commit=False,
        )

    assert exc_info.value.code == "DOCUMENT_GRAPH_EDGE_EXISTS"
    assert exc_info.value.details["edge_id"] == 99
    service.would_create_implements_cycle.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_would_create_implements_cycle_detects_ancestor_path():
    """A → B already exists; adding B → A must cycle."""
    db = MagicMock()
    service = DocumentGraphService(db)

    # First walk from dst=A(10): look for parents of 10 → finds B(20)
    # Then walk from 20: look for parents → empty
    parent_of_10 = MagicMock()
    parent_of_10.scalars.return_value.all.return_value = [20]
    parent_of_20 = MagicMock()
    parent_of_20.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[parent_of_10, parent_of_20])

    assert (
        await service.would_create_implements_cycle(
            tenant_id=1,
            src_document_id=20,
            dst_document_id=10,
        )
        is True
    )


@pytest.mark.asyncio
async def test_confirm_stamps_actor_and_timestamp():
    db = AsyncMock()
    edge = SimpleNamespace(
        id=7,
        tenant_id=1,
        status=DocumentEdgeStatus.PROPOSED,
        confirmed_by_id=None,
        confirmed_at=None,
        is_primary_parent=False,
        edge_type=DocumentEdgeType.REFERENCES,
        src_document_id=10,
        dst_document_id=20,
    )
    service = DocumentGraphService(db)
    service._get_edge_or_404 = AsyncMock(return_value=edge)  # type: ignore[method-assign]

    with patch(
        "src.domain.services.document_graph_service.record_audit_event",
        new_callable=AsyncMock,
    ):
        result = await service.confirm(tenant_id=1, edge_id=7, actor_id=42, commit=False)

    assert result.status == DocumentEdgeStatus.CONFIRMED
    assert result.confirmed_by_id == 42
    assert result.confirmed_at is not None
    db.flush.assert_awaited()


# ---------------------------------------------------------------------------
# Flag gate: 404 when document_graph_enabled is off
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_document_graph_enabled_404_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", False)
    with pytest.raises(HTTPException) as exc_info:
        await document_graph_routes.require_document_graph_enabled()
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == document_graph_routes.DISABLED_DETAIL


@pytest.mark.asyncio
async def test_require_document_graph_enabled_passes_when_flag_on(monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", True)
    await document_graph_routes.require_document_graph_enabled()


def test_flag_off_http_surface_returns_404(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", False)
    response = client.get(f"{GRAPH_PREFIX}/documents/1/edges")
    assert response.status_code == 404
    body = response.json()
    detail = body.get("detail") or body.get("error", {}).get("message")
    assert detail == document_graph_routes.DISABLED_DETAIL


def test_enums_exported_from_models_package():
    from src.domain.models import DocumentEdge as ExportedEdge
    from src.domain.models import DocumentEdgeMethod as ExportedMethod
    from src.domain.models import DocumentEdgeStatus as ExportedStatus
    from src.domain.models import DocumentEdgeType as ExportedType

    assert ExportedEdge is DocumentEdge
    assert ExportedType is DocumentEdgeType
    assert ExportedStatus is DocumentEdgeStatus
    assert ExportedMethod is DocumentEdgeMethod
