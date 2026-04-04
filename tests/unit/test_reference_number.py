"""Tests for ReferenceNumberService – parse and generate."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.reference_number import ReferenceNumberService


class TestParse:
    def test_parse_valid_reference(self):
        result = ReferenceNumberService.parse("INC-2026-0042")
        assert result["prefix"] == "INC"
        assert result["year"] == 2026
        assert result["sequence"] == 42

    def test_parse_rsk_reference(self):
        result = ReferenceNumberService.parse("RSK-2025-0001")
        assert result["prefix"] == "RSK"
        assert result["year"] == 2025
        assert result["sequence"] == 1

    def test_parse_comp_reference(self):
        result = ReferenceNumberService.parse("COMP-2024-1234")
        assert result["prefix"] == "COMP"
        assert result["year"] == 2024
        assert result["sequence"] == 1234

    def test_parse_capa_reference(self):
        result = ReferenceNumberService.parse("CAPA-2026-0005")
        assert result == {"prefix": "CAPA", "year": 2026, "sequence": 5}

    def test_parse_invalid_format_returns_nones(self):
        result = ReferenceNumberService.parse("INVALID")
        assert result["prefix"] is None
        assert result["year"] is None
        assert result["sequence"] is None

    def test_parse_empty_string(self):
        result = ReferenceNumberService.parse("")
        assert result["prefix"] is None

    def test_parse_non_numeric_year(self):
        result = ReferenceNumberService.parse("INC-ABCD-0001")
        assert result["prefix"] is None

    def test_parse_non_numeric_sequence(self):
        result = ReferenceNumberService.parse("INC-2026-ABCD")
        assert result["prefix"] is None


class TestPrefixes:
    def test_all_expected_prefixes_defined(self):
        expected_types = [
            "audit_template",
            "audit_run",
            "audit_finding",
            "audit_import",
            "risk",
            "incident",
            "rta",
            "complaint",
            "near_miss",
            "policy",
            "incident_action",
            "rta_action",
            "complaint_action",
            "capa",
        ]
        for record_type in expected_types:
            assert record_type in ReferenceNumberService.PREFIXES

    def test_prefixes_are_uppercase_strings(self):
        for key, prefix in ReferenceNumberService.PREFIXES.items():
            assert prefix == prefix.upper()
            assert isinstance(prefix, str)
            assert len(prefix) >= 2


class TestRefColumn:
    def test_ref_column_with_reference_number(self):
        model = SimpleNamespace(reference_number="col_ref")
        result = ReferenceNumberService._ref_column(model)
        assert result == "col_ref"

    def test_ref_column_with_reference(self):
        model = type("Model", (), {"reference": "col_ref"})
        result = ReferenceNumberService._ref_column(model)
        assert result == "col_ref"

    def test_ref_column_missing_raises(self):
        model = type("Model", (), {})
        with pytest.raises(AttributeError, match="has neither"):
            ReferenceNumberService._ref_column(model)

    def test_ref_column_prefers_reference_number(self):
        model = type("Model", (), {"reference_number": "primary", "reference": "secondary"})
        result = ReferenceNumberService._ref_column(model)
        assert result == "primary"


@pytest.mark.asyncio
async def test_generate_produces_correct_format():
    """Test that generate returns PREFIX-YYYY-####."""
    mock_db = AsyncMock()

    with patch.object(ReferenceNumberService, "_next_sequence", new_callable=AsyncMock, return_value=1):
        ref = await ReferenceNumberService.generate(mock_db, "incident", MagicMock(), year=2026)

    assert ref == "INC-2026-0001"


@pytest.mark.asyncio
async def test_generate_increments_sequence():
    """Test that sequence increments from existing max."""
    mock_db = AsyncMock()

    with patch.object(ReferenceNumberService, "_next_sequence", new_callable=AsyncMock, return_value=6):
        ref = await ReferenceNumberService.generate(mock_db, "incident", MagicMock(), year=2026)

    assert ref == "INC-2026-0006"


@pytest.mark.asyncio
async def test_generate_unknown_record_type_uses_ref():
    """Unknown record types should fall back to 'REF' prefix."""
    mock_db = AsyncMock()

    with patch.object(ReferenceNumberService, "_next_sequence", new_callable=AsyncMock, return_value=1):
        ref = await ReferenceNumberService.generate(mock_db, "unknown_type", MagicMock(), year=2026)

    assert ref.startswith("REF-2026-")


@pytest.mark.asyncio
async def test_generate_formats_sequence_with_padding():
    """Sequence numbers should be zero-padded to 4 digits."""
    mock_db = AsyncMock()

    with patch.object(ReferenceNumberService, "_next_sequence", new_callable=AsyncMock, return_value=42):
        ref = await ReferenceNumberService.generate(mock_db, "risk", MagicMock(), year=2026)

    assert ref == "RSK-2026-0042"


@pytest.mark.asyncio
async def test_generate_uses_all_prefix_types():
    """All known record types should produce the correct prefix."""
    mock_db = AsyncMock()

    for record_type, prefix in ReferenceNumberService.PREFIXES.items():
        with patch.object(ReferenceNumberService, "_next_sequence", new_callable=AsyncMock, return_value=1):
            ref = await ReferenceNumberService.generate(mock_db, record_type, MagicMock(), year=2026)
        assert ref.startswith(f"{prefix}-2026-")
