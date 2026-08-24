"""Doc Graph Wave 1 PR-F: ISO reverse freshness (clause → documents)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.routes import document_graph as document_graph_routes
from src.core.config import settings
from src.domain.services.cel_version_freshness import classify_cel_version_freshness
from src.domain.services.document_graph_iso_reverse import DocumentGraphIsoReverseService


@pytest.mark.parametrize(
    "pinned,tip,expected",
    [
        (None, 10, "unpinned"),
        (None, None, "unpinned"),
        (10, 10, "current"),
        (10, 11, "stale"),
        (10, None, "unknown"),
    ],
)
def test_classify_cel_version_freshness(pinned, tip, expected):
    assert (
        classify_cel_version_freshness(
            pinned_document_version_id=pinned,
            tip_document_version_id=tip,
        )
        == expected
    )


@pytest.mark.asyncio
async def test_list_documents_for_clause_composes_freshness():
    link_current = SimpleNamespace(
        id=1,
        entity_id="42",
        document_version_id=100,
        status=SimpleNamespace(value="confirmed"),
        title="Pinned title",
        created_at=None,
    )
    link_stale = SimpleNamespace(
        id=2,
        entity_id="42",
        document_version_id=99,
        status="needs_review",
        title=None,
        created_at=None,
    )
    link_unpinned = SimpleNamespace(
        id=3,
        entity_id="7",
        document_version_id=None,
        status="confirmed",
        title=None,
        created_at=None,
    )

    scalars = MagicMock()
    scalars.all.return_value = [link_current, link_stale, link_unpinned]
    result_links = MagicMock()
    result_links.scalars.return_value = scalars

    result_titles = MagicMock()
    result_titles.all.return_value = [(42, "Incident Management Policy"), (7, "SOP")]

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[result_links, result_titles])

    tip_42 = SimpleNamespace(id=100, version_number="2.0")
    tip_7 = SimpleNamespace(id=200, version_number="1.0")

    async def resolve_tip(_db, *, document_id, tenant_id):
        assert tenant_id == 1
        return {42: tip_42, 7: tip_7}.get(document_id)

    service = DocumentGraphIsoReverseService(db)
    with patch(
        "src.domain.services.document_graph_iso_reverse.document_version_service.resolve_tip_library_version",
        new=AsyncMock(side_effect=resolve_tip),
    ):
        payload = await service.list_documents_for_clause(tenant_id=1, clause_id="9001-7.5")

    assert payload["clause_id"] == "9001-7.5"
    assert payload["total"] == 3
    by_link = {d["evidence_link_id"]: d for d in payload["documents"]}
    assert by_link[1]["freshness"] == "current"
    assert by_link[1]["title"] == "Incident Management Policy"
    assert by_link[1]["tip_version_number"] == "2.0"
    assert by_link[2]["freshness"] == "stale"
    assert by_link[3]["freshness"] == "unpinned"
    assert by_link[3]["document_id"] == 7


@pytest.mark.asyncio
async def test_clause_documents_route_404_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", False)
    with pytest.raises(HTTPException) as exc:
        await document_graph_routes.require_document_graph_enabled()
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_list_clause_documents_route_delegates(monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", True)
    fake_payload = {
        "clause_id": "9001-7.5",
        "documents": [
            {
                "document_id": 42,
                "title": "Policy",
                "evidence_link_id": 1,
                "link_status": "confirmed",
                "pinned_document_version_id": 100,
                "tip_document_version_id": 100,
                "tip_version_number": "2.0",
                "freshness": "current",
            }
        ],
        "total": 1,
    }
    mock_service = MagicMock()
    mock_service.list_documents_for_clause = AsyncMock(return_value=fake_payload)

    user = SimpleNamespace(id=1, tenant_id=9)
    db = MagicMock()

    with patch(
        "src.api.routes.document_graph.DocumentGraphIsoReverseService",
        return_value=mock_service,
    ):
        response = await document_graph_routes.list_clause_documents(
            clause_id="9001-7.5",
            db=db,
            current_user=user,
        )

    assert response.clause_id == "9001-7.5"
    assert response.total == 1
    assert response.documents[0].freshness == "current"
    mock_service.list_documents_for_clause.assert_awaited_once_with(
        tenant_id=9,
        clause_id="9001-7.5",
    )
