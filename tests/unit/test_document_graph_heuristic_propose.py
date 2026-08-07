"""Doc Graph Wave 1 PR-E: heuristic propose + quote_hash citation staleness."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.routes import document_graph as document_graph_routes
from src.core.config import settings
from src.domain.exceptions import ValidationError
from src.domain.models.document_graph import DocumentEdgeMethod, DocumentEdgeStatus, DocumentEdgeType
from src.domain.services.document_graph_citation import (
    CitationStaleness,
    compute_quote_hash,
    evaluate_citation_staleness,
    extract_citation_matches,
)
from src.domain.services.document_graph_heuristic_propose import (
    IMPACT_DRIVING_EDGE_TYPES,
    DocumentGraphHeuristicProposeService,
    _pel_family_prefix,
)
from src.domain.services.document_graph_service import DocumentGraphService

GRAPH_PREFIX = "/api/v1/document-graph"


# ---------------------------------------------------------------------------
# Pure citation helpers
# ---------------------------------------------------------------------------


def test_compute_quote_hash_is_sha256_hex():
    digest = compute_quote_hash("DOC-2026-0042")
    assert len(digest) == 64
    assert digest == compute_quote_hash("DOC-2026-0042")
    assert digest != compute_quote_hash("DOC-2026-0043")


def test_extract_citation_matches_doc_pel_and_path():
    text = "See DOC-2026-0042 and PEL-IMS-POL-0001 via /documents/99?tab=relationships"
    matches = extract_citation_matches(text)
    kinds = {m.kind for m in matches}
    assert kinds == {"doc_ref", "pel_ref", "document_path"}
    path = next(m for m in matches if m.kind == "document_path")
    assert path.resolved_document_id == 99


def test_citation_staleness_unchanged_moved_text_changed_not_found():
    quote = "DOC-2026-0042"
    digest = compute_quote_hash(quote)
    content = f"Preface {quote} trailing"

    assert (
        evaluate_citation_staleness(
            quote_hash=digest,
            citation_text=quote,
            char_start=content.index(quote),
            char_end=content.index(quote) + len(quote),
            chunk_content=content,
        )
        is CitationStaleness.UNCHANGED
    )

    moved = f"{quote} now at the front"
    assert (
        evaluate_citation_staleness(
            quote_hash=digest,
            citation_text=quote,
            char_start=8,
            char_end=8 + len(quote),
            chunk_content=moved,
        )
        is CitationStaleness.MOVED
    )

    changed = "Preface DOC-2026-9999 trailing"
    assert (
        evaluate_citation_staleness(
            quote_hash=digest,
            citation_text=quote,
            char_start=8,
            char_end=8 + len(quote),
            chunk_content=changed,
        )
        is CitationStaleness.TEXT_CHANGED
    )

    assert (
        evaluate_citation_staleness(
            quote_hash=digest,
            citation_text=quote,
            char_start=0,
            char_end=len(quote),
            chunk_content=None,
        )
        is CitationStaleness.NOT_FOUND
    )


def test_pel_family_prefix():
    assert _pel_family_prefix("PEL-IMS-POL-0001") == "PEL-IMS-POL"
    assert _pel_family_prefix("PEL-X") is None


# ---------------------------------------------------------------------------
# Service guards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_edge_rejects_heuristic_auto_confirm_impact_driving():
    db = AsyncMock()
    service = DocumentGraphService(db)
    service._get_document_or_404 = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda **kwargs: SimpleNamespace(id=kwargs["document_id"], pel_doc_ref=None)
    )
    service._find_live_edge_id = AsyncMock(return_value=None)  # type: ignore[method-assign]

    with pytest.raises(ValidationError) as exc_info:
        await service.create_edge(
            tenant_id=1,
            src_document_id=10,
            dst_document_id=20,
            edge_type=DocumentEdgeType.IMPLEMENTS,
            created_method=DocumentEdgeMethod.HEURISTIC,
            status=DocumentEdgeStatus.CONFIRMED,
            actor_id=5,
            commit=False,
        )

    assert exc_info.value.code == "DOCUMENT_GRAPH_HEURISTIC_NO_AUTO_CONFIRM"
    assert DocumentEdgeType.IMPLEMENTS in IMPACT_DRIVING_EDGE_TYPES
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_propose_logs_ai_decision_auto_applied_false():
    db = AsyncMock()
    graph = DocumentGraphService(db)
    graph._get_document_or_404 = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            id=10,
            title="Incident Management Policy",
            ai_summary=None,
            category_id=None,
            category=None,
            pel_doc_ref=None,
            description=None,
        )
    )
    service = DocumentGraphHeuristicProposeService(db, graph=graph)

    with (
        patch.object(service, "_category_and_pel_siblings", AsyncMock(return_value=[])),
        patch.object(service, "_shared_cel_peers", AsyncMock(return_value=[])),
        patch.object(service, "_vector_or_ilike_peers", AsyncMock(return_value=[])),
        patch.object(service, "_regex_citation_proposals", AsyncMock(return_value=[])),
    ):
        result = await service.propose_for_document(tenant_id=1, document_id=10, actor_id=3, commit=False)

    assert result.created == []
    assert db.add.call_count == 1
    log_row = db.add.call_args.args[0]
    assert log_row.action == "document_graph_heuristic_propose"
    assert log_row.auto_applied is False
    assert log_row.entity_type == "document"
    assert log_row.entity_id == "10"
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_propose_creates_related_to_from_category_sibling():
    db = AsyncMock()
    graph = DocumentGraphService(db)
    graph._get_document_or_404 = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            id=10,
            title="Policy",
            ai_summary=None,
            category_id=7,
            category="IMS",
            pel_doc_ref=None,
            description=None,
        )
    )
    created = SimpleNamespace(
        id=501,
        edge_type=DocumentEdgeType.RELATED_TO,
        status=DocumentEdgeStatus.PROPOSED,
        created_method=DocumentEdgeMethod.HEURISTIC,
        confidence=0.55,
    )
    graph.create_edge = AsyncMock(return_value=created)  # type: ignore[method-assign]
    graph._find_live_edge_id = AsyncMock(return_value=None)  # type: ignore[method-assign]

    service = DocumentGraphHeuristicProposeService(db, graph=graph)
    with (
        patch.object(
            service,
            "_category_and_pel_siblings",
            AsyncMock(return_value=[(20, 0.55, "Same library category as source document")]),
        ),
        patch.object(service, "_shared_cel_peers", AsyncMock(return_value=[])),
        patch.object(service, "_vector_or_ilike_peers", AsyncMock(return_value=[])),
        patch.object(service, "_regex_citation_proposals", AsyncMock(return_value=[])),
    ):
        result = await service.propose_for_document(tenant_id=1, document_id=10, actor_id=3, commit=False)

    assert len(result.created) == 1
    assert result.sources["category_pel_siblings"] == 1
    graph.create_edge.assert_awaited()
    kwargs = graph.create_edge.await_args.kwargs
    assert kwargs["edge_type"] == DocumentEdgeType.RELATED_TO
    assert kwargs["status"] == DocumentEdgeStatus.PROPOSED
    assert kwargs["created_method"] == DocumentEdgeMethod.HEURISTIC


@pytest.mark.asyncio
async def test_citation_staleness_for_edge_uses_chunk():
    db = MagicMock()
    edge = SimpleNamespace(
        id=9,
        quote_hash=compute_quote_hash("DOC-2026-0042"),
        citation_text="DOC-2026-0042",
        char_start=0,
        char_end=13,
        chunk_id=3,
    )
    graph = DocumentGraphService(db)
    graph._get_edge_or_404 = AsyncMock(return_value=edge)  # type: ignore[method-assign]

    chunk_result = MagicMock()
    chunk_result.scalar_one_or_none.return_value = "DOC-2026-0042 remains"
    db.execute = AsyncMock(return_value=chunk_result)

    service = DocumentGraphHeuristicProposeService(db, graph=graph)
    payload = await service.citation_staleness_for_edge(tenant_id=1, edge_id=9)
    assert payload["status"] == CitationStaleness.UNCHANGED.value
    assert payload["edge_id"] == 9


# ---------------------------------------------------------------------------
# Flag gates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heuristic_flag_404_when_off(monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", True)
    monkeypatch.setattr(settings, "document_graph_heuristic_propose_enabled", False)
    with pytest.raises(HTTPException) as exc_info:
        await document_graph_routes.require_document_graph_heuristic_propose_enabled()
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == document_graph_routes.HEURISTIC_DISABLED_DETAIL


@pytest.mark.asyncio
async def test_heuristic_flag_requires_master_gate(monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", False)
    monkeypatch.setattr(settings, "document_graph_heuristic_propose_enabled", True)
    with pytest.raises(HTTPException) as exc_info:
        await document_graph_routes.require_document_graph_heuristic_propose_enabled()
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == document_graph_routes.DISABLED_DETAIL


def test_propose_http_404_when_heuristic_flag_off(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", True)
    monkeypatch.setattr(settings, "document_graph_heuristic_propose_enabled", False)
    response = client.post(f"{GRAPH_PREFIX}/documents/1/propose")
    assert response.status_code == 404


def test_citation_staleness_http_404_when_graph_off(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", False)
    response = client.get(f"{GRAPH_PREFIX}/edges/1/citation-staleness")
    assert response.status_code == 404
