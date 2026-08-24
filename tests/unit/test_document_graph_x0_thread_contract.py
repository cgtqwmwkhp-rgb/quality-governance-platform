"""Doc Graph X-0: enriched thread hops, walk safety, AuditLog, programme flags."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.routes import document_graph as document_graph_routes
from src.api.schemas.document_graph import DocumentThreadHop
from src.core.config import Settings, settings
from src.domain.exceptions import ConflictError
from src.domain.features.catalogue import CLIENT_FEATURES_BY_KEY
from src.domain.models.document_graph import DocumentEdgeStatus, DocumentEdgeType
from src.domain.services.document_graph_service import DocumentGraphService, thread_walk_statuses

GRAPH_PREFIX = "/api/v1/document-graph"

PROGRAMME_FLAGS = (
    "document_graph_thread_ambient",
    "document_graph_map_view",
    "document_graph_dnd_propose",
    "document_graph_structure_map",
    "graph_coach",
    "entity_360",
    "entity_360_satellites",
    "job_lifecycle",
    "job_cell_links",
)


def _edge(
    *,
    edge_id: int,
    src: int,
    dst: int,
    status: DocumentEdgeStatus = DocumentEdgeStatus.CONFIRMED,
    is_primary: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=edge_id,
        src_document_id=src,
        dst_document_id=dst,
        status=status,
        is_primary_parent=is_primary,
        edge_type=DocumentEdgeType.IMPLEMENTS,
        deleted_at=None,
        rationale=None,
        confirmed_by_id=None,
        confirmed_at=None,
    )


def _doc(doc_id: int, *, title: str, reference: str | None = None, pel: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=doc_id,
        title=title,
        reference_number=reference or f"DOC-2026-{doc_id:04d}",
        pel_doc_ref=pel,
    )


# ---------------------------------------------------------------------------
# (a) Confirmed-only vs include_proposed
# ---------------------------------------------------------------------------


def test_thread_walk_statuses_confirmed_only_by_default():
    assert thread_walk_statuses(include_proposed=False) == (DocumentEdgeStatus.CONFIRMED,)
    assert DocumentEdgeStatus.PROPOSED not in thread_walk_statuses(include_proposed=False)
    assert DocumentEdgeStatus.NEEDS_REVIEW not in thread_walk_statuses(include_proposed=False)


def test_thread_walk_statuses_include_proposed_adds_pending():
    statuses = thread_walk_statuses(include_proposed=True)
    assert DocumentEdgeStatus.CONFIRMED in statuses
    assert DocumentEdgeStatus.PROPOSED in statuses
    assert DocumentEdgeStatus.NEEDS_REVIEW in statuses
    assert DocumentEdgeStatus.REJECTED not in statuses


@pytest.mark.asyncio
async def test_get_thread_excludes_proposed_parent_by_default():
    """Ambient thread must not surface PROPOSED primary parents unless opted in."""
    db = MagicMock()
    service = DocumentGraphService(db)
    service._get_document_or_404 = AsyncMock(return_value=_doc(10, title="Child"))  # type: ignore[method-assign]
    service._documents_by_ids = AsyncMock(  # type: ignore[method-assign]
        return_value={20: _doc(20, title="Parent Policy", pel="POL-001")}
    )

    proposed_parent = _edge(edge_id=1, src=10, dst=20, status=DocumentEdgeStatus.PROPOSED)
    confirmed_parent = _edge(edge_id=2, src=10, dst=30, status=DocumentEdgeStatus.CONFIRMED)

    # Ancestor query returns empty when statuses are confirmed-only (DB filtered).
    empty = MagicMock()
    empty.scalars.return_value.all.return_value = []
    # Descendant query likewise empty.
    db.execute = AsyncMock(return_value=empty)

    payload = await service.get_thread(tenant_id=1, document_id=10, include_proposed=False)
    assert payload["ancestors"] == []
    assert payload["descendants"] == []

    # With include_proposed, proposed parent is returned by the (mocked) query.
    parent_result = MagicMock()
    parent_result.scalars.return_value.all.return_value = [proposed_parent]
    child_empty = MagicMock()
    child_empty.scalars.return_value.all.return_value = []
    # After taking proposed parent, next ancestor level empty; then descendants empty.
    db.execute = AsyncMock(side_effect=[parent_result, empty, child_empty])
    service._documents_by_ids = AsyncMock(  # type: ignore[method-assign]
        return_value={20: _doc(20, title="Parent Policy", pel="POL-001")}
    )

    payload = await service.get_thread(tenant_id=1, document_id=10, include_proposed=True)
    assert len(payload["ancestors"]) == 1
    hop = payload["ancestors"][0]
    assert hop["document_id"] == 20
    assert hop["status"] == DocumentEdgeStatus.PROPOSED.value
    assert hop["title"] == "Parent Policy"
    assert hop["origin"] == "graph"
    _ = confirmed_parent  # reserved — documents the alternative status fixture


# ---------------------------------------------------------------------------
# (b) Second primary parent guard + deterministic ordering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_rejects_second_primary_implements_parent():
    db = AsyncMock()
    service = DocumentGraphService(db)
    service._get_document_or_404 = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda **kwargs: _doc(kwargs["document_id"], title=f"D{kwargs['document_id']}")
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
async def test_confirm_rejects_second_primary_implements_parent():
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
async def test_ancestor_walk_orders_primary_parents_deterministically():
    """If two primary parents exist (legacy), lowest edge id wins — never .first() alone."""
    db = MagicMock()
    service = DocumentGraphService(db)
    service._get_document_or_404 = AsyncMock(return_value=_doc(10, title="Child"))  # type: ignore[method-assign]
    service._documents_by_ids = AsyncMock(  # type: ignore[method-assign]
        return_value={
            20: _doc(20, title="Parent A", pel="POL-A"),
            30: _doc(30, title="Parent B", pel="POL-B"),
        }
    )

    # Unordered return; service must order by id asc and take the first.
    higher = _edge(edge_id=50, src=10, dst=30)
    lower = _edge(edge_id=40, src=10, dst=20)
    parent_result = MagicMock()
    parent_result.scalars.return_value.all.return_value = [higher, lower]
    next_empty = MagicMock()
    next_empty.scalars.return_value.all.return_value = []
    child_empty = MagicMock()
    child_empty.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(side_effect=[parent_result, next_empty, child_empty])

    payload = await service.get_thread(tenant_id=1, document_id=10)
    assert payload["ancestors"][0]["document_id"] == 20
    assert payload["ancestors"][0]["edge_id"] == 40


# ---------------------------------------------------------------------------
# (c) Cyclic graph terminates; each node once
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_descendant_walk_is_cycle_safe_and_dedupes():
    db = MagicMock()
    service = DocumentGraphService(db)
    service._get_document_or_404 = AsyncMock(return_value=_doc(1, title="Root"))  # type: ignore[method-assign]
    service._documents_by_ids = AsyncMock(  # type: ignore[method-assign]
        return_value={
            2: _doc(2, title="Child"),
            3: _doc(3, title="Grandchild"),
        }
    )

    # Ancestors empty.
    anc_empty = MagicMock()
    anc_empty.scalars.return_value.all.return_value = []

    # From 1: child 2. From 2: child 3. From 3: child 2 again (cycle) — must stop.
    e12 = _edge(edge_id=1, src=2, dst=1)
    e23 = _edge(edge_id=2, src=3, dst=2)
    e32_cycle = _edge(edge_id=3, src=2, dst=3)

    children_of_1 = MagicMock()
    children_of_1.scalars.return_value.all.return_value = [e12]
    children_of_2 = MagicMock()
    children_of_2.scalars.return_value.all.return_value = [e23]
    children_of_3 = MagicMock()
    children_of_3.scalars.return_value.all.return_value = [e32_cycle]

    db.execute = AsyncMock(side_effect=[anc_empty, children_of_1, children_of_2, children_of_3])

    payload = await service.get_thread(tenant_id=1, document_id=1, max_depth=4)
    descendant_ids = [h["document_id"] for h in payload["descendants"]]
    assert descendant_ids == [2, 3]
    assert len(descendant_ids) == len(set(descendant_ids))


# ---------------------------------------------------------------------------
# (d) Hops carry enriched fields
# ---------------------------------------------------------------------------


def test_document_thread_hop_schema_requires_enrichment_fields():
    hop = DocumentThreadHop(
        document_id=9,
        edge_id=3,
        depth=1,
        direction="parent",
        title="IM Policy",
        reference="POL-IM-001",
        href="/documents/9",
        origin="graph",
        status="confirmed",
    )
    assert hop.href == "/documents/9"
    assert hop.origin == "graph"
    assert hop.status == "confirmed"
    assert hop.title == "IM Policy"
    assert hop.reference == "POL-IM-001"


@pytest.mark.asyncio
async def test_get_thread_hops_carry_title_reference_href_origin_status():
    db = MagicMock()
    service = DocumentGraphService(db)
    service._get_document_or_404 = AsyncMock(return_value=_doc(10, title="SOP"))  # type: ignore[method-assign]
    service._documents_by_ids = AsyncMock(  # type: ignore[method-assign]
        return_value={20: _doc(20, title="IM Policy", pel="POL-IM-001", reference="DOC-2026-0020")}
    )

    parent = _edge(edge_id=5, src=10, dst=20, status=DocumentEdgeStatus.CONFIRMED)
    parent_result = MagicMock()
    parent_result.scalars.return_value.all.return_value = [parent]
    next_empty = MagicMock()
    next_empty.scalars.return_value.all.return_value = []
    child_empty = MagicMock()
    child_empty.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(side_effect=[parent_result, next_empty, child_empty])

    payload = await service.get_thread(tenant_id=1, document_id=10)
    hop = payload["ancestors"][0]
    assert hop["title"] == "IM Policy"
    assert hop["reference"] == "POL-IM-001"
    assert hop["href"] == "/documents/20"
    assert hop["origin"] == "graph"
    assert hop["status"] == "confirmed"
    assert hop["document_id"] == 20
    assert hop["edge_id"] == 5
    assert hop["depth"] == 1
    assert hop["direction"] == "parent"


# ---------------------------------------------------------------------------
# (e) confirm / reject / soft-delete write AuditLog
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_writes_audit_log():
    db = AsyncMock()
    edge = _edge(edge_id=7, src=10, dst=20, status=DocumentEdgeStatus.PROPOSED, is_primary=False)
    service = DocumentGraphService(db)
    service._get_edge_or_404 = AsyncMock(return_value=edge)  # type: ignore[method-assign]
    service._find_other_primary_parent_edge_id = AsyncMock(return_value=None)  # type: ignore[method-assign]

    with patch(
        "src.domain.services.document_graph_service.record_audit_event",
        new_callable=AsyncMock,
    ) as audit:
        await service.confirm(tenant_id=1, edge_id=7, actor_id=42, commit=False)
        audit.assert_awaited_once()
        kwargs = audit.await_args.kwargs
        assert kwargs["action"] == "confirm"
        assert kwargs["entity_type"] == "document_edge"
        assert kwargs["entity_id"] == "7"
        assert kwargs["tenant_id"] == 1
        assert kwargs["user_id"] == 42


@pytest.mark.asyncio
async def test_reject_writes_audit_log():
    db = AsyncMock()
    edge = _edge(edge_id=8, src=10, dst=20, status=DocumentEdgeStatus.PROPOSED)
    service = DocumentGraphService(db)
    service._get_edge_or_404 = AsyncMock(return_value=edge)  # type: ignore[method-assign]

    with patch(
        "src.domain.services.document_graph_service.record_audit_event",
        new_callable=AsyncMock,
    ) as audit:
        await service.reject(tenant_id=1, edge_id=8, actor_id=42, rationale="nope", commit=False)
        audit.assert_awaited_once()
        kwargs = audit.await_args.kwargs
        assert kwargs["action"] == "reject"
        assert kwargs["entity_type"] == "document_edge"
        assert kwargs["entity_id"] == "8"


@pytest.mark.asyncio
async def test_soft_delete_writes_audit_log():
    db = AsyncMock()
    edge = _edge(edge_id=9, src=10, dst=20, status=DocumentEdgeStatus.CONFIRMED)
    service = DocumentGraphService(db)
    service._get_edge_or_404 = AsyncMock(return_value=edge)  # type: ignore[method-assign]

    with patch(
        "src.domain.services.document_graph_service.record_audit_event",
        new_callable=AsyncMock,
    ) as audit:
        await service.soft_delete(tenant_id=1, edge_id=9, actor_id=42, commit=False)
        audit.assert_awaited_once()
        kwargs = audit.await_args.kwargs
        assert kwargs["action"] == "delete"
        assert kwargs["entity_type"] == "document_edge"
        assert kwargs["entity_id"] == "9"


# ---------------------------------------------------------------------------
# (f) Flag-off still 404s document-graph
# ---------------------------------------------------------------------------


def test_flag_off_still_404s_document_graph(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", False)
    response = client.get(f"{GRAPH_PREFIX}/documents/1/thread")
    assert response.status_code == 404
    body = response.json()
    detail = body.get("detail") or body.get("error", {}).get("message")
    assert detail == document_graph_routes.DISABLED_DETAIL


@pytest.mark.asyncio
async def test_require_document_graph_enabled_still_404_when_off(monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", False)
    with pytest.raises(HTTPException) as exc_info:
        await document_graph_routes.require_document_graph_enabled()
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Programme flags pre-registered default-off
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ui_key", PROGRAMME_FLAGS)
def test_programme_flag_registered_default_off(ui_key: str):
    feature = CLIENT_FEATURES_BY_KEY[ui_key]
    assert feature.settings_attr == f"{ui_key}_enabled"
    assert feature.settings_attr in Settings.model_fields
    assert Settings.model_fields[feature.settings_attr].default is False
    assert getattr(settings, feature.settings_attr) is False
