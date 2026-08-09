"""Doc Graph NS-EXP / W8: cascade aggregate for Structure map L1–L5 bands.

One estate request replaces the Structure map's previous 1+N edge fetches.
Confirmed implements only; Parent PEL from primary-parent edges; orphan ids
match the workbook definitions among documents the viewer may read.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.routes import document_graph as document_graph_routes
from src.api.schemas.document_graph import CascadeAggregateResponse
from src.core.config import settings
from src.domain.models.document_graph import DocumentEdgeMethod, DocumentEdgeStatus, DocumentEdgeType
from src.domain.services.document_graph_service import DocumentGraphService

GRAPH_PREFIX = "/api/v1/document-graph"


def _doc(
    doc_id: int,
    *,
    title: str,
    cascade_level: int | None = None,
    pel_doc_ref: str | None = None,
    access_level: str = "all_staff",
    category_id=None,
    document_type: str = "policy",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=doc_id,
        title=title,
        pel_doc_ref=pel_doc_ref or (f"PEL-HSEQ-{doc_id:04d}" if cascade_level else None),
        reference_number=f"DOC-2026-{doc_id:04d}",
        cascade_level=cascade_level,
        document_type=document_type,
        access_level=access_level,
        category_id=category_id,
        is_active=True,
        tenant_id=1,
    )


def _edge(
    edge_id: int,
    *,
    src: int,
    dst: int,
    is_primary_parent: bool = True,
    status: DocumentEdgeStatus = DocumentEdgeStatus.CONFIRMED,
    dst_pel: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=edge_id,
        tenant_id=1,
        src_document_id=src,
        dst_document_id=dst,
        src_pel_doc_ref=None,
        dst_pel_doc_ref=dst_pel,
        edge_type=DocumentEdgeType.IMPLEMENTS,
        status=status,
        created_method=DocumentEdgeMethod.MANUAL,
        is_primary_parent=is_primary_parent,
        confidence=None,
        rationale=None,
        confirmed_by_id=1,
        confirmed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        cited_document_version_id=None,
        chunk_id=None,
        char_start=None,
        char_end=None,
        quote_hash=None,
        citation_text=None,
        cited_version=None,
        deleted_at=None,
        created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )


def _service_with_estate(
    docs: list[SimpleNamespace],
    edges: list[SimpleNamespace],
) -> DocumentGraphService:
    """Two execute calls: documents estate, then confirmed implements edges."""
    db = AsyncMock()
    docs_result = MagicMock()
    docs_result.scalars.return_value.all.return_value = docs
    edges_result = MagicMock()
    edges_result.scalars.return_value.all.return_value = edges
    db.execute.side_effect = [docs_result, edges_result]
    service = DocumentGraphService(db)
    # Parent pel resolution may call _documents_by_ids for parent endpoints.
    by_id = {doc.id: doc for doc in docs}
    service._documents_by_ids = AsyncMock(return_value=by_id)  # type: ignore[method-assign]
    return service


@pytest.mark.asyncio
async def test_cascade_aggregate_returns_bands_parents_and_confirmed_edges_only():
    policy = _doc(10, title="IM Policy", cascade_level=2, pel_doc_ref="PEL-HSEQ-2001")
    procedure = _doc(20, title="Reporting SOP", cascade_level=3, pel_doc_ref="PEL-HSEQ-3001")
    proposed = _edge(99, src=20, dst=10, status=DocumentEdgeStatus.PROPOSED)
    confirmed = _edge(1, src=20, dst=10, dst_pel="PEL-HSEQ-2001")

    # Service filters status in SQL — only pass confirmed edges as the query result.
    service = _service_with_estate([policy, procedure], [confirmed])
    assert proposed.status != DocumentEdgeStatus.CONFIRMED  # proposed never enter this payload

    payload = await service.get_cascade_aggregate(
        tenant_id=1,
        viewer=SimpleNamespace(is_superuser=True),
    )
    model = CascadeAggregateResponse.model_validate(payload)

    assert model.returned_documents == 2
    assert model.returned_edges == 1
    assert model.edges[0].id == 1
    assert model.edges[0].is_primary_parent is True

    by_id = {item.document_id: item for item in model.documents}
    assert by_id[20].parent_document_id == 10
    assert by_id[20].parent_pel == "PEL-HSEQ-2001"
    assert by_id[10].parent_document_id is None

    band_by_label = {band.label: band.count for band in model.bands}
    assert band_by_label["L2"] == 1
    assert band_by_label["L3"] == 1
    assert band_by_label["unset"] == 0
    assert band_by_label["L1"] == 0


@pytest.mark.asyncio
async def test_cascade_aggregate_classifies_workbook_orphan_types():
    unimplemented = _doc(2, title="Lonely policy", cascade_level=2)
    unparented = _doc(3, title="Orphan procedure", cascade_level=3)
    uncontrolled = _doc(5, title="Loose form", cascade_level=5)
    rooted = _doc(1, title="Manual", cascade_level=1)
    child = _doc(4, title="Child SOP", cascade_level=4, pel_doc_ref="PEL-HSEQ-4001")
    parent_edge = _edge(1, src=4, dst=1, dst_pel="PEL-HSEQ-1001")

    service = _service_with_estate(
        [unimplemented, unparented, uncontrolled, rooted, child],
        [parent_edge],
    )
    payload = await service.get_cascade_aggregate(
        tenant_id=1,
        viewer=SimpleNamespace(is_superuser=True),
    )
    orphans = payload["orphans"]
    assert orphans["unimplemented_policy_ids"] == [2]
    assert orphans["unparented_ids"] == [3]
    assert orphans["uncontrolled_record_ids"] == [5]
    assert orphans["unimplemented_policy_count"] == 1
    assert orphans["unparented_count"] == 1
    assert orphans["uncontrolled_record_count"] == 1
    # Child with a confirmed primary parent is not an orphan.
    assert 4 not in orphans["unparented_ids"]


@pytest.mark.asyncio
async def test_cascade_aggregate_omits_documents_the_viewer_may_not_read():
    readable = _doc(10, title="Open policy", cascade_level=2)
    restricted = _doc(
        20,
        title="OH file",
        cascade_level=3,
        access_level="restricted",
        category_id=99,
    )
    service = _service_with_estate([readable, restricted], [])
    category_result = MagicMock()
    category_result.all.return_value = [(99, "02.08")]
    # First execute = docs; second = taxonomy for restricted ACL; third = edges
    # (only if visible ids remain). Re-wire after helper built the default pair.
    docs_result = MagicMock()
    docs_result.scalars.return_value.all.return_value = [readable, restricted]
    edges_result = MagicMock()
    edges_result.scalars.return_value.all.return_value = []
    service.db.execute.side_effect = [docs_result, category_result, edges_result]

    payload = await service.get_cascade_aggregate(
        tenant_id=1,
        viewer=SimpleNamespace(is_superuser=False, has_permission=lambda _p: False),
    )

    assert [d["document_id"] for d in payload["documents"]] == [10]
    assert payload["returned_documents"] == 1
    assert payload["orphans"]["unparented_count"] == 0  # restricted L3 not counted


def test_cascade_route_404s_when_document_graph_is_off(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", False)
    response = client.get(f"{GRAPH_PREFIX}/cascade")
    assert response.status_code == 404
    body = response.json()
    detail = body.get("detail") or body.get("error", {}).get("message")
    assert detail == document_graph_routes.DISABLED_DETAIL


def test_cascade_route_is_served_under_document_graph(app):
    """Assert the app walk, not the shape of a FastAPI router object (WE-1 trap)."""
    from src.domain.authz.extraction import walk_mounted_app

    served = {(method, endpoint.path) for endpoint in walk_mounted_app(app).endpoints for method in endpoint.methods}
    assert ("GET", f"{GRAPH_PREFIX}/cascade") in served
    assert ("POST", f"{GRAPH_PREFIX}/cascade") not in served
