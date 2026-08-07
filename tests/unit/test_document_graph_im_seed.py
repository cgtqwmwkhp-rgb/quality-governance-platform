"""Doc Graph Wave 1 PR-G: Incident Management demo seed + flag gate."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.routes import document_graph as document_graph_routes
from src.core.config import settings
from src.domain.models.document_graph import DocumentEdgeMethod, DocumentEdgeStatus, DocumentEdgeType
from src.domain.models.enums import DocumentType
from src.domain.services.document_graph_im_seed import (
    IM_SEED_DOC_SPECS,
    IM_SEED_EDGE_SPECS,
    SEED_MARKER,
    DocumentGraphImSeedService,
    ImSeedResult,
)

GRAPH_PREFIX = "/api/v1/document-graph"
SEED_PATH = f"{GRAPH_PREFIX}/demo/incident-management/seed"


def test_im_seed_specs_match_locked_vertical():
    roles = {spec.role for spec in IM_SEED_DOC_SPECS}
    assert roles == {
        "im_policy",
        "im_procedure",
        "im_sop",
        "im_form",
        "risk_register",
        "risk_policy",
    }
    types = {spec.role: spec.document_type for spec in IM_SEED_DOC_SPECS}
    assert types["im_policy"] == DocumentType.POLICY
    assert types["im_procedure"] == DocumentType.PROCEDURE
    assert types["im_sop"] == DocumentType.SOP
    assert types["im_form"] == DocumentType.FORM
    assert types["risk_register"] == DocumentType.REGISTER
    assert types["risk_policy"] == DocumentType.POLICY

    edge_pairs = {(e.src_role, e.dst_role, e.edge_type) for e in IM_SEED_EDGE_SPECS}
    assert (
        "im_policy",
        "im_procedure",
        DocumentEdgeType.IMPLEMENTS,
    ) in edge_pairs
    assert (
        "im_procedure",
        "im_sop",
        DocumentEdgeType.IMPLEMENTS,
    ) in edge_pairs
    assert (
        "im_policy",
        "im_form",
        DocumentEdgeType.REQUIRES_RECORD,
    ) in edge_pairs
    assert (
        "im_policy",
        "risk_register",
        DocumentEdgeType.REQUIRES_RECORD,
    ) in edge_pairs
    assert (
        "im_policy",
        "risk_policy",
        DocumentEdgeType.RELATED_TO,
    ) in edge_pairs
    assert all(SEED_MARKER in spec.description for spec in IM_SEED_DOC_SPECS)


@pytest.mark.asyncio
async def test_im_seed_reuses_existing_docs_and_edges():
    db = AsyncMock()
    db.commit = AsyncMock()
    service = DocumentGraphImSeedService(db)

    docs_by_title = {
        spec.title: SimpleNamespace(id=100 + i, title=spec.title) for i, spec in enumerate(IM_SEED_DOC_SPECS)
    }

    async def find_by_title(**kwargs):
        return docs_by_title[kwargs["title"]]

    service._find_by_title = AsyncMock(side_effect=find_by_title)  # type: ignore[method-assign]
    service._create_stub_document = AsyncMock()  # type: ignore[method-assign]

    async def ensure_edge(**kwargs):
        return (900 + kwargs["src_document_id"], False)

    service._ensure_confirmed_edge = AsyncMock(side_effect=ensure_edge)  # type: ignore[method-assign]

    result = await service.seed(tenant_id=7, actor_id=3)

    assert result.documents_created == 0
    assert result.documents_reused == len(IM_SEED_DOC_SPECS)
    assert result.edges_created == 0
    assert result.edges_reused == len(IM_SEED_EDGE_SPECS)
    service._create_stub_document.assert_not_called()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_im_seed_creates_missing_docs_and_confirmed_auto_edges():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    service = DocumentGraphImSeedService(db)
    service._find_by_title = AsyncMock(return_value=None)  # type: ignore[method-assign]

    created_ids = {"n": 0}

    async def create_stub(**kwargs):
        created_ids["n"] += 1
        spec = kwargs["spec"]
        return SimpleNamespace(id=created_ids["n"], title=spec.title)

    service._create_stub_document = AsyncMock(side_effect=create_stub)  # type: ignore[method-assign]

    graph = service.graph
    graph._find_live_edge_id = AsyncMock(return_value=None)  # type: ignore[method-assign]

    created_edges: list[dict] = []

    async def create_edge(**kwargs):
        created_edges.append(kwargs)
        return SimpleNamespace(id=500 + len(created_edges))

    graph.create_edge = AsyncMock(side_effect=create_edge)  # type: ignore[method-assign]

    result = await service.seed(tenant_id=1, actor_id=9)

    assert result.documents_created == len(IM_SEED_DOC_SPECS)
    assert result.edges_created == len(IM_SEED_EDGE_SPECS)
    assert len(created_edges) == len(IM_SEED_EDGE_SPECS)
    for kwargs in created_edges:
        assert kwargs["status"] == DocumentEdgeStatus.CONFIRMED
        assert kwargs["created_method"] == DocumentEdgeMethod.AUTO
        assert kwargs["commit"] is False
        assert kwargs["actor_id"] == 9


@pytest.mark.asyncio
async def test_im_seed_skips_doc_create_when_disabled():
    db = AsyncMock()
    db.commit = AsyncMock()
    service = DocumentGraphImSeedService(db)
    service._find_by_title = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service._create_stub_document = AsyncMock()  # type: ignore[method-assign]
    service._ensure_confirmed_edge = AsyncMock()  # type: ignore[method-assign]

    result = await service.seed(tenant_id=1, create_missing_documents=False)

    assert result.documents_created == 0
    assert result.documents == []
    assert result.edges == []
    service._create_stub_document.assert_not_called()
    service._ensure_confirmed_edge.assert_not_called()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_seed_route_dependency_404_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", False)
    with pytest.raises(HTTPException) as exc_info:
        await document_graph_routes.require_document_graph_enabled()
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == document_graph_routes.DISABLED_DETAIL


def test_seed_http_surface_404_when_flag_off(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", False)
    response = client.post(SEED_PATH)
    assert response.status_code == 404
    body = response.json()
    detail = body.get("detail") or body.get("error", {}).get("message")
    assert detail == document_graph_routes.DISABLED_DETAIL


@pytest.mark.asyncio
async def test_seed_route_invokes_service_when_flag_on(monkeypatch):
    monkeypatch.setattr(settings, "document_graph_enabled", True)

    fake_result = ImSeedResult(
        documents_created=1,
        documents_reused=5,
        edges_created=2,
        edges_reused=3,
    )
    fake_result.documents = []
    fake_result.edges = []

    class FakeSeedService:
        def __init__(self, db):
            self.db = db

        async def seed(self, **kwargs):
            assert kwargs["tenant_id"] == 42
            assert kwargs["actor_id"] == 7
            return fake_result

    monkeypatch.setattr(document_graph_routes, "DocumentGraphImSeedService", FakeSeedService)
    monkeypatch.setattr(
        document_graph_routes,
        "require_tenant_id",
        lambda tenant_id: tenant_id,
    )

    user = SimpleNamespace(id=7, tenant_id=42)
    response = await document_graph_routes.seed_incident_management_vertical(
        db=AsyncMock(),
        current_user=user,
    )
    assert response.documents_created == 1
    assert response.edges_reused == 3
