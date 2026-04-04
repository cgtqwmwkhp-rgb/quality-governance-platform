"""Tests for src.domain.services.search_service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.search_service import SearchResultItem, SearchService

# ---------------------------------------------------------------------------
# SearchResultItem
# ---------------------------------------------------------------------------


class TestSearchResultItem:
    def test_to_dict_contains_all_fields(self):
        item = SearchResultItem(
            id="INC-1",
            type="incident",
            title="Fire alarm",
            description="False alarm in building A",
            module="Incidents",
            status="Open",
            date="2026-01-01",
            relevance=85.0,
            highlights=["fire"],
        )
        d = item.to_dict()
        assert d["id"] == "INC-1"
        assert d["type"] == "incident"
        assert d["title"] == "Fire alarm"
        assert d["module"] == "Incidents"
        assert d["relevance"] == 85.0
        assert d["highlights"] == ["fire"]

    def test_to_dict_defaults_highlights_to_empty_list(self):
        item = SearchResultItem(
            id="X-1",
            type="t",
            title="T",
            description="D",
            module="M",
            status="S",
            date="D",
            relevance=50.0,
        )
        assert item.highlights == []
        assert item.to_dict()["highlights"] == []

    def test_slots_prevent_arbitrary_attrs(self):
        item = SearchResultItem(
            id="X-1",
            type="t",
            title="T",
            description="D",
            module="M",
            status="S",
            date="D",
            relevance=50.0,
        )
        with pytest.raises(AttributeError):
            item.extra = "nope"


# ---------------------------------------------------------------------------
# Static / pure helpers
# ---------------------------------------------------------------------------


class TestSearchServiceStaticHelpers:
    def test_is_short_query_true(self):
        assert SearchService._is_short_query("ab") is True
        assert SearchService._is_short_query("abc") is True

    def test_is_short_query_false(self):
        assert SearchService._is_short_query("abcd") is False
        assert SearchService._is_short_query("hello world") is False

    def test_is_short_query_with_whitespace(self):
        assert SearchService._is_short_query("  a ") is True

    def test_highlight_words_basic(self):
        words = SearchService._highlight_words("fire alarm", "The fire was a false alarm", None)
        assert "fire" in words
        assert "alarm" in words

    def test_highlight_words_no_match(self):
        words = SearchService._highlight_words("xyz", "nothing here")
        assert words == []

    def test_highlight_words_none_values(self):
        words = SearchService._highlight_words("test", None, None)
        assert words == []

    def test_simple_relevance_exact_match(self):
        score = SearchService._simple_relevance("fire", "fire drill report")
        assert score >= 75.0

    def test_simple_relevance_no_match(self):
        score = SearchService._simple_relevance("zzz", "nothing related")
        assert 55.0 <= score <= 70.0

    def test_simple_relevance_capped_at_95(self):
        score = SearchService._simple_relevance("fire", "fire fire fire fire fire fire fire fire fire fire")
        assert score <= 95.0

    def test_simple_relevance_multiple_values(self):
        score = SearchService._simple_relevance("fire", "fire", "alarm fire", "fire drill")
        assert score >= 55.0


# ---------------------------------------------------------------------------
# search() orchestration
# ---------------------------------------------------------------------------


class TestSearchServiceSearch:
    @pytest.fixture
    def service(self):
        db = AsyncMock()
        return SearchService(db)

    @pytest.mark.asyncio
    @patch("src.domain.services.search_service.track_metric")
    async def test_search_returns_dict_structure(self, mock_metric, service):
        for method in (
            "_search_incidents",
            "_search_rtas",
            "_search_complaints",
            "_search_risks",
            "_search_audits",
            "_search_actions",
            "_search_documents",
        ):
            setattr(service, method, AsyncMock(return_value=[]))

        result = await service.search(query="fire", tenant_id=1)

        assert "results" in result
        assert "total" in result
        assert "query" in result
        assert "facets" in result
        assert result["query"] == "fire"
        assert result["total"] == 0

    @pytest.mark.asyncio
    @patch("src.domain.services.search_service.track_metric")
    async def test_search_filters_by_module(self, mock_metric, service):
        items = [
            SearchResultItem(
                id="1",
                type="incident",
                title="T",
                description="D",
                module="Incidents",
                status="Open",
                date="",
                relevance=80.0,
            ),
            SearchResultItem(
                id="2",
                type="risk",
                title="T2",
                description="D2",
                module="Risks",
                status="Open",
                date="",
                relevance=70.0,
            ),
        ]
        for method in (
            "_search_incidents",
            "_search_rtas",
            "_search_complaints",
            "_search_risks",
            "_search_audits",
            "_search_actions",
            "_search_documents",
        ):
            setattr(service, method, AsyncMock(return_value=[]))
        service._search_incidents = AsyncMock(return_value=items)

        result = await service.search(query="test", tenant_id=1, module="Risks")
        assert result["total"] == 1
        assert result["results"][0]["module"] == "Risks"

    @pytest.mark.asyncio
    @patch("src.domain.services.search_service.track_metric")
    async def test_search_filters_by_status(self, mock_metric, service):
        items = [
            SearchResultItem(
                id="1",
                type="incident",
                title="T",
                description="D",
                module="Incidents",
                status="Open",
                date="",
                relevance=80.0,
            ),
            SearchResultItem(
                id="2",
                type="incident",
                title="T2",
                description="D2",
                module="Incidents",
                status="Closed",
                date="",
                relevance=70.0,
            ),
        ]
        for method in (
            "_search_incidents",
            "_search_rtas",
            "_search_complaints",
            "_search_risks",
            "_search_audits",
            "_search_actions",
            "_search_documents",
        ):
            setattr(service, method, AsyncMock(return_value=[]))
        service._search_incidents = AsyncMock(return_value=items)

        result = await service.search(query="test", tenant_id=1, status_filter="closed")
        assert result["total"] == 1

    @pytest.mark.asyncio
    @patch("src.domain.services.search_service.track_metric")
    async def test_search_pagination(self, mock_metric, service):
        items = [
            SearchResultItem(
                id=str(i),
                type="incident",
                title=f"T{i}",
                description="D",
                module="Incidents",
                status="Open",
                date="",
                relevance=float(100 - i),
            )
            for i in range(5)
        ]
        for method in (
            "_search_incidents",
            "_search_rtas",
            "_search_complaints",
            "_search_risks",
            "_search_audits",
            "_search_actions",
            "_search_documents",
        ):
            setattr(service, method, AsyncMock(return_value=[]))
        service._search_incidents = AsyncMock(return_value=items)

        result = await service.search(query="t", tenant_id=1, page=1, page_size=2)
        assert result["total"] == 5
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    @patch("src.domain.services.search_service.track_metric")
    async def test_search_sorts_by_relevance_desc(self, mock_metric, service):
        items = [
            SearchResultItem(
                id="low",
                type="t",
                title="Low",
                description="D",
                module="M",
                status="S",
                date="",
                relevance=10.0,
            ),
            SearchResultItem(
                id="high",
                type="t",
                title="High",
                description="D",
                module="M",
                status="S",
                date="",
                relevance=90.0,
            ),
        ]
        for method in (
            "_search_incidents",
            "_search_rtas",
            "_search_complaints",
            "_search_risks",
            "_search_audits",
            "_search_actions",
            "_search_documents",
        ):
            setattr(service, method, AsyncMock(return_value=[]))
        service._search_incidents = AsyncMock(return_value=items)

        result = await service.search(query="t", tenant_id=1)
        assert result["results"][0]["id"] == "high"

    @pytest.mark.asyncio
    @patch("src.domain.services.search_service.track_metric")
    async def test_search_facets_module_counts(self, mock_metric, service):
        items = [
            SearchResultItem(
                id="1",
                type="t",
                title="T",
                description="D",
                module="Incidents",
                status="S",
                date="",
                relevance=50.0,
            ),
            SearchResultItem(
                id="2",
                type="t",
                title="T",
                description="D",
                module="Incidents",
                status="S",
                date="",
                relevance=50.0,
            ),
            SearchResultItem(
                id="3",
                type="t",
                title="T",
                description="D",
                module="Risks",
                status="S",
                date="",
                relevance=50.0,
            ),
        ]
        for method in (
            "_search_incidents",
            "_search_rtas",
            "_search_complaints",
            "_search_risks",
            "_search_audits",
            "_search_actions",
            "_search_documents",
        ):
            setattr(service, method, AsyncMock(return_value=[]))
        service._search_incidents = AsyncMock(return_value=items)

        result = await service.search(query="t", tenant_id=1)
        assert result["facets"]["modules"]["Incidents"] == 2
        assert result["facets"]["modules"]["Risks"] == 1

    @pytest.mark.asyncio
    @patch("src.domain.services.search_service.track_metric")
    async def test_search_tracks_metrics(self, mock_metric, service):
        for method in (
            "_search_incidents",
            "_search_rtas",
            "_search_complaints",
            "_search_risks",
            "_search_audits",
            "_search_actions",
            "_search_documents",
        ):
            setattr(service, method, AsyncMock(return_value=[]))

        await service.search(query="test", tenant_id=1)
        assert mock_metric.call_count >= 2
