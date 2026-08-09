"""Doc Graph WE-1: tenant-wide confirm queue behind the Knowledge Exceptions inbox.

Covers the queue's pending-only contract, honest truncation, library ACL
redaction of counterpart titles, and the master flag gate on the new route.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.routes import document_graph as document_graph_routes
from src.api.schemas.document_graph import PendingDocumentEdgeListResponse
from src.core.config import settings
from src.domain.exceptions import ValidationError
from src.domain.models.document_graph import DocumentEdgeMethod, DocumentEdgeStatus, DocumentEdgeType
from src.domain.services.document_graph_service import PENDING_EDGE_STATUSES, PENDING_QUEUE_LIMIT, DocumentGraphService

GRAPH_PREFIX = "/api/v1/document-graph"


def _edge(
    edge_id: int,
    *,
    edge_type: DocumentEdgeType = DocumentEdgeType.RELATED_TO,
    status: DocumentEdgeStatus = DocumentEdgeStatus.PROPOSED,
    src: int = 10,
    dst: int = 20,
    is_primary_parent: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=edge_id,
        tenant_id=1,
        src_document_id=src,
        dst_document_id=dst,
        src_pel_doc_ref="PEL-HSE-01-001",
        dst_pel_doc_ref="PEL-HSE-01-002",
        edge_type=edge_type,
        status=status,
        created_method=DocumentEdgeMethod.HEURISTIC,
        is_primary_parent=is_primary_parent,
        confidence=0.42,
        rationale="cited in section 3",
        created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )


def _doc(doc_id: int, *, title: str, access_level: str = "all_staff", category_id=None) -> SimpleNamespace:
    return SimpleNamespace(
        id=doc_id,
        title=title,
        pel_doc_ref=f"PEL-HSE-01-{doc_id:03d}",
        reference_number=f"DOC-2026-{doc_id:04d}",
        access_level=access_level,
        category_id=category_id,
    )


def _bound_values(query) -> set:
    """Flatten compiled bind params — ``IN`` binds expand to a list, not a scalar."""
    values: set = set()
    for value in query.compile().params.values():
        if isinstance(value, (list, tuple)):
            values.update(value)
        else:
            values.add(value)
    return values


def _service_with_edges(edges: list[SimpleNamespace], docs: dict[int, SimpleNamespace]) -> DocumentGraphService:
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = edges
    db.execute.return_value = result
    service = DocumentGraphService(db)
    service._documents_by_ids = AsyncMock(return_value=docs)  # type: ignore[method-assign]
    return service


# ---------------------------------------------------------------------------
# Queue contract: pending only, honest page
# ---------------------------------------------------------------------------


def test_pending_statuses_are_proposed_and_needs_review_only():
    assert PENDING_EDGE_STATUSES == (DocumentEdgeStatus.PROPOSED, DocumentEdgeStatus.NEEDS_REVIEW)
    assert DocumentEdgeStatus.CONFIRMED not in PENDING_EDGE_STATUSES
    assert DocumentEdgeStatus.REJECTED not in PENDING_EDGE_STATUSES


@pytest.mark.asyncio
async def test_pending_queue_filters_to_live_pending_edges_of_this_tenant():
    edges = [_edge(1)]
    service = _service_with_edges(edges, {10: _doc(10, title="Policy"), 20: _doc(20, title="Procedure")})

    payload = await service.list_pending_edges(tenant_id=1, viewer=SimpleNamespace(is_superuser=True))

    assert payload["returned"] == 1
    assert payload["truncated"] is False
    query = service.db.execute.await_args_list[0].args[0]
    sql = str(query)
    assert "document_edges.tenant_id = " in sql
    assert "document_edges.deleted_at IS NULL" in sql
    assert "document_edges.status IN " in sql
    bound = _bound_values(query)
    assert {DocumentEdgeStatus.PROPOSED, DocumentEdgeStatus.NEEDS_REVIEW} <= bound
    assert DocumentEdgeStatus.CONFIRMED not in bound


@pytest.mark.asyncio
async def test_pending_queue_reports_truncation_rather_than_implying_a_total():
    # Three rows come back for a two-row page: the extra row exists only to prove
    # the page was cut, and must not be served as if it fitted.
    edges = [_edge(1), _edge(2), _edge(3)]
    service = _service_with_edges(edges, {10: _doc(10, title="Policy"), 20: _doc(20, title="Procedure")})

    payload = await service.list_pending_edges(
        tenant_id=1,
        viewer=SimpleNamespace(is_superuser=True),
        limit=2,
    )

    assert payload["returned"] == 2
    assert payload["limit"] == 2
    assert payload["truncated"] is True
    assert [item["edge_id"] for item in payload["items"]] == [1, 2]


@pytest.mark.asyncio
async def test_pending_queue_clamps_limit_to_one_page():
    service = _service_with_edges([], {})

    payload = await service.list_pending_edges(
        tenant_id=1,
        viewer=SimpleNamespace(is_superuser=True),
        limit=10_000,
    )

    assert payload["limit"] == PENDING_QUEUE_LIMIT
    assert payload["returned"] == 0
    assert payload["truncated"] is False


@pytest.mark.asyncio
async def test_pending_queue_refuses_a_settled_status():
    service = _service_with_edges([], {})

    with pytest.raises(ValidationError) as exc_info:
        await service.list_pending_edges(
            tenant_id=1,
            viewer=SimpleNamespace(is_superuser=True),
            status=DocumentEdgeStatus.CONFIRMED,
        )

    assert exc_info.value.code == "DOCUMENT_GRAPH_NOT_PENDING_STATUS"
    service.db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_queue_accepts_needs_review_alone():
    service = _service_with_edges([_edge(4, status=DocumentEdgeStatus.NEEDS_REVIEW)], {})

    payload = await service.list_pending_edges(
        tenant_id=1,
        viewer=SimpleNamespace(is_superuser=True),
        status=DocumentEdgeStatus.NEEDS_REVIEW,
    )

    bound = _bound_values(service.db.execute.await_args_list[0].args[0])
    assert DocumentEdgeStatus.NEEDS_REVIEW in bound
    assert DocumentEdgeStatus.PROPOSED not in bound
    assert payload["items"][0]["status"] == "needs_review"


# ---------------------------------------------------------------------------
# Impact honesty (ADR-0021: AI/heuristic never auto-confirms impact-driving edges)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pending_queue_flags_impact_driving_edge_types():
    edges = [
        _edge(1, edge_type=DocumentEdgeType.IMPLEMENTS, is_primary_parent=True),
        _edge(2, edge_type=DocumentEdgeType.RELATED_TO),
    ]
    service = _service_with_edges(edges, {10: _doc(10, title="Policy"), 20: _doc(20, title="Procedure")})

    payload = await service.list_pending_edges(tenant_id=1, viewer=SimpleNamespace(is_superuser=True))

    by_id = {item["edge_id"]: item for item in payload["items"]}
    assert by_id[1]["impact_driving"] is True
    assert by_id[1]["is_primary_parent"] is True
    assert by_id[2]["impact_driving"] is False
    assert by_id[1]["created_method"] == "heuristic"
    assert by_id[1]["status"] == "proposed"


# ---------------------------------------------------------------------------
# Library ACL: a tenant-wide queue must not leak titles the by-id route refuses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pending_queue_withholds_titles_the_viewer_may_not_read():
    docs = {
        10: _doc(10, title="Readable policy"),
        20: _doc(20, title="Occupational health file", access_level="restricted", category_id=99),
    }
    service = _service_with_edges([_edge(1)], docs)
    # Restricted rows need a taxonomy lookup; this viewer holds no restricted grant.
    category_result = MagicMock()
    category_result.all.return_value = [(99, "02.08")]
    service.db.execute.side_effect = [service.db.execute.return_value, category_result]

    payload = await service.list_pending_edges(
        tenant_id=1,
        viewer=SimpleNamespace(is_superuser=False, has_permission=lambda perm: False),
    )

    item = payload["items"][0]
    assert item["src"]["readable"] is True
    assert item["src"]["title"] == "Readable policy"
    assert item["dst"]["readable"] is False
    assert item["dst"]["title"] is None
    assert item["dst"]["reference"] is None
    # The id and deep-link stay — the operator can still ask for access.
    assert item["dst"]["document_id"] == 20
    assert item["dst"]["href"] == "/documents/20"


@pytest.mark.asyncio
async def test_pending_queue_withholds_titles_for_documents_it_could_not_load():
    service = _service_with_edges([_edge(1)], {10: _doc(10, title="Readable policy")})

    payload = await service.list_pending_edges(tenant_id=1, viewer=SimpleNamespace(is_superuser=True))

    item = payload["items"][0]
    assert item["dst"]["readable"] is False
    assert item["dst"]["title"] is None


@pytest.mark.asyncio
async def test_pending_queue_payload_validates_against_the_response_schema():
    docs = {10: _doc(10, title="Policy"), 20: _doc(20, title="Procedure")}
    service = _service_with_edges([_edge(1)], docs)

    payload = await service.list_pending_edges(tenant_id=1, viewer=SimpleNamespace(is_superuser=True))
    model = PendingDocumentEdgeListResponse.model_validate(payload)

    assert model.returned == 1
    assert model.items[0].edge_type == DocumentEdgeType.RELATED_TO
    assert model.items[0].status == DocumentEdgeStatus.PROPOSED


# ---------------------------------------------------------------------------
# Flag gate: the queue is invisible while Doc Graph is closed
# ---------------------------------------------------------------------------


def test_pending_queue_route_404s_when_document_graph_is_off(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", False)
    response = client.get(f"{GRAPH_PREFIX}/edges/pending")
    assert response.status_code == 404
    body = response.json()
    detail = body.get("detail") or body.get("error", {}).get("message")
    assert detail == document_graph_routes.DISABLED_DETAIL


def test_pending_queue_route_is_served_under_document_graph(app):
    """Assert the endpoint the app actually serves, not the shape of a router object.

    A flat loop over ``router.routes`` is version-dependent: up to FastAPI 0.135
    ``include_router`` copied child routes onto the parent, and from 0.140 it
    appends one wrapper instead — so the same loop that saw the path locally saw a
    single empty path in CI. ``walk_mounted_app`` is the traversal the
    authorisation census already uses for exactly this reason.
    """
    from src.domain.authz.extraction import walk_mounted_app

    served = {(method, endpoint.path) for endpoint in walk_mounted_app(app).endpoints for method in endpoint.methods}
    assert ("GET", f"{GRAPH_PREFIX}/edges/pending") in served
    # The queue must not have quietly acquired a mutation route of its own —
    # confirm/reject stay on the existing edge endpoints.
    assert ("POST", f"{GRAPH_PREFIX}/edges/pending") not in served
