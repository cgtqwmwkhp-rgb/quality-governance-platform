from unittest.mock import AsyncMock

import pytest

from src.domain.services.search_service import SearchResultItem, SearchService


@pytest.mark.asyncio
async def test_search_service_aggregates_new_governance_modules(monkeypatch):
    service = SearchService(None)  # type: ignore[arg-type]

    monkeypatch.setattr("src.domain.services.search_service.track_metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_search_incidents", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_search_rtas", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_search_complaints", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_search_risks", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        service,
        "_search_audits",
        AsyncMock(
            return_value=[
                SearchResultItem(
                    id="AUD-1",
                    type="audit",
                    title="Supplier audit finding",
                    description="Document control gap",
                    module="Audits",
                    status="open",
                    date="2026-03-01T10:00:00Z",
                    relevance=82,
                    highlights=["audit"],
                )
            ]
        ),
    )
    monkeypatch.setattr(
        service,
        "_search_actions",
        AsyncMock(
            return_value=[
                SearchResultItem(
                    id="ACT-1",
                    type="action",
                    title="Update approval workflow",
                    description="Corrective action for document governance",
                    module="Actions",
                    status="in_progress",
                    date="2026-03-02T10:00:00Z",
                    relevance=81,
                    highlights=["workflow"],
                )
            ]
        ),
    )
    monkeypatch.setattr(
        service,
        "_search_documents",
        AsyncMock(
            return_value=[
                SearchResultItem(
                    id="DOC-1",
                    type="document",
                    title="Controlled policy",
                    description="Documented approval process",
                    module="Documents",
                    status="approved",
                    date="2026-03-03T10:00:00Z",
                    relevance=90,
                    highlights=["policy"],
                )
            ]
        ),
    )

    result = await service.search(query="policy", tenant_id=1, request_id="req-1")

    assert [item["module"] for item in result["results"]] == ["Documents", "Audits", "Actions"]
    assert result["facets"]["modules"] == {
        "Audits": 1,
        "Actions": 1,
        "Documents": 1,
    }


@pytest.mark.asyncio
async def test_search_service_module_filter_supports_documents(monkeypatch):
    service = SearchService(None)  # type: ignore[arg-type]

    monkeypatch.setattr("src.domain.services.search_service.track_metric", lambda *args, **kwargs: None)
    empty = AsyncMock(return_value=[])
    monkeypatch.setattr(service, "_search_incidents", empty)
    monkeypatch.setattr(service, "_search_rtas", empty)
    monkeypatch.setattr(service, "_search_complaints", empty)
    monkeypatch.setattr(service, "_search_risks", empty)
    monkeypatch.setattr(service, "_search_audits", empty)
    monkeypatch.setattr(service, "_search_actions", empty)
    monkeypatch.setattr(
        service,
        "_search_documents",
        AsyncMock(
            return_value=[
                SearchResultItem(
                    id="DOC-1",
                    type="document",
                    title="Controlled policy",
                    description="Documented approval process",
                    module="Documents",
                    status="approved",
                    date="2026-03-03T10:00:00Z",
                    relevance=90,
                    highlights=["policy"],
                )
            ]
        ),
    )

    result = await service.search(query="policy", tenant_id=1, module="Documents", request_id="req-2")

    assert result["total"] == 1
    assert result["results"][0]["module"] == "Documents"
