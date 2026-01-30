"""
Unit Tests for ETL Transformers - Quality Governance Platform
Stage 10: Data Foundation
"""

import pytest
from scripts.etl.transformers import (
    parse_date,
    map_incident_type,
    map_severity,
    map_status,
    sanitize_text,
    TransformError,
    get_transformer,
)


class TestParseDate:
    """Tests for date parsing."""

    def test_iso_format(self):
        """Should parse ISO format."""
        result = parse_date("2026-01-15")
        assert result == "2026-01-15"

    def test_uk_format(self):
        """Should parse UK date format."""
        result = parse_date("15/01/2026")
        assert result == "2026-01-15"

    def test_empty_returns_none(self):
        """Empty value should return None."""
        assert parse_date("") is None
        assert parse_date(None) is None

    def test_invalid_date_raises(self):
        """Invalid date should raise TransformError."""
        with pytest.raises(TransformError):
            parse_date("not-a-date", "test_field")


class TestMapIncidentType:
    """Tests for incident type mapping."""

    def test_direct_match(self):
        """Direct match should work."""
        assert map_incident_type("safety") == "safety"
        assert map_incident_type("quality") == "quality"

    def test_case_insensitive(self):
        """Mapping should be case insensitive."""
        assert map_incident_type("SAFETY") == "safety"
        assert map_incident_type("Quality") == "quality"

    def test_near_miss_variants(self):
        """Near miss variants should map correctly."""
        assert map_incident_type("near miss") == "near_miss"
        assert map_incident_type("nearmiss") == "near_miss"
        assert map_incident_type("near-miss") == "near_miss"

    def test_unknown_returns_other(self):
        """Unknown value should return 'other'."""
        assert map_incident_type("unknown_type") == "other"
        assert map_incident_type("") == "other"


class TestMapSeverity:
    """Tests for severity mapping."""

    def test_text_values(self):
        """Text severity should map correctly."""
        assert map_severity("critical") == "critical"
        assert map_severity("high") == "high"
        assert map_severity("medium") == "medium"
        assert map_severity("low") == "low"

    def test_numeric_values(self):
        """Numeric severity should map correctly."""
        assert map_severity("1") == "critical"
        assert map_severity("2") == "high"
        assert map_severity("3") == "medium"
        assert map_severity("4") == "low"


class TestSanitizeText:
    """Tests for text sanitization."""

    def test_trims_whitespace(self):
        """Should trim whitespace."""
        assert sanitize_text("  hello  ") == "hello"

    def test_normalizes_whitespace(self):
        """Should normalize internal whitespace."""
        assert sanitize_text("hello   world") == "hello world"

    def test_truncates_with_ellipsis(self):
        """Should truncate long text with ellipsis."""
        result = sanitize_text("a" * 100, max_length=50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_none_returns_none(self):
        """None input should return None."""
        assert sanitize_text(None) is None


class TestGetTransformer:
    """Tests for transformer registry."""

    def test_valid_transformer(self):
        """Should return valid transformer."""
        transformer = get_transformer("parse_date")
        assert callable(transformer)

    def test_invalid_transformer_raises(self):
        """Invalid transformer should raise ValueError."""
        with pytest.raises(ValueError):
            get_transformer("nonexistent")
