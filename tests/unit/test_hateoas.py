"""Tests for HATEOAS link builder."""
from src.api.utils.hateoas import build_links


class TestBuildLinks:
    def test_default_base_url(self):
        links = build_links("incidents", 123)
        assert links["self"] == "/api/v1/incidents/123"
        assert links["collection"] == "/api/v1/incidents"

    def test_custom_base_url(self):
        links = build_links("risks", 5, base_url="/api/v2")
        assert links["self"] == "/api/v2/risks/5"
        assert links["collection"] == "/api/v2/risks"
