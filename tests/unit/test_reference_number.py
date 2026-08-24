"""Tests for ReferenceNumberService – parse and generate."""

from datetime import datetime
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


class TestMintSerialisation:
    """PX-126 — concurrent minters must not both read the same MAX."""

    @pytest.mark.asyncio
    async def test_postgres_takes_a_transaction_lock_before_reading_the_sequence(self):
        db = MagicMock()
        db.get_bind.return_value.dialect.name = "postgresql"
        db.execute = AsyncMock()

        await ReferenceNumberService._serialize_minting(db, "COMP-2026-%")

        db.execute.assert_awaited_once()
        statement, params = db.execute.await_args.args
        assert "pg_advisory_xact_lock" in str(statement)
        assert params["key"] == ReferenceNumberService._advisory_lock_key("COMP-2026-%")

    @pytest.mark.asyncio
    async def test_other_dialects_are_left_alone(self):
        db = MagicMock()
        db.get_bind.return_value.dialect.name = "sqlite"
        db.execute = AsyncMock()

        await ReferenceNumberService._serialize_minting(db, "COMP-2026-%")

        db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_lock_that_cannot_be_taken_never_blocks_the_mint(self):
        db = MagicMock()
        db.get_bind.return_value.dialect.name = "postgresql"
        db.execute = AsyncMock(side_effect=RuntimeError("no lock for you"))

        await ReferenceNumberService._serialize_minting(db, "COMP-2026-%")

    def test_lock_keys_are_stable_and_prefix_specific(self):
        assert ReferenceNumberService._advisory_lock_key("COMP-2026-%") == ReferenceNumberService._advisory_lock_key(
            "COMP-2026-%"
        )
        assert ReferenceNumberService._advisory_lock_key("COMP-2026-%") != ReferenceNumberService._advisory_lock_key(
            "INC-2026-%"
        )

    def test_lock_keys_fit_a_signed_64_bit_postgres_argument(self):
        for pattern in ("COMP-2026-%", "INC-2026-%", "CAM-2026-%", "NM-1999-%"):
            key = ReferenceNumberService._advisory_lock_key(pattern)
            assert -(2**63) <= key < 2**63


class TestPortalMint:
    """PX-126 — portal intake draws from the same sequence as staff intake."""

    @pytest.mark.asyncio
    async def test_portal_complaint_reference_is_sequential(self):
        from src.api.routes.employee_portal import mint_portal_reference

        db = AsyncMock()
        with patch.object(ReferenceNumberService, "_next_sequence", new_callable=AsyncMock, return_value=7):
            reference = await mint_portal_reference(db, "COMP")

        assert reference == f"COMP-{datetime.now().year}-0007"

    @pytest.mark.asyncio
    async def test_every_portal_prefix_maps_to_its_register(self):
        from src.api.routes.employee_portal import mint_portal_reference

        db = AsyncMock()
        for prefix in ("INC", "COMP", "CMND", "SUGG", "FDBK", "RTA", "NM"):
            with patch.object(ReferenceNumberService, "_next_sequence", new_callable=AsyncMock, return_value=1):
                reference = await mint_portal_reference(db, prefix)
            assert reference == f"{prefix}-{datetime.now().year}-0001"

    @pytest.mark.asyncio
    async def test_a_submission_is_never_lost_when_the_sequence_is_unreadable(self):
        from src.api.routes.employee_portal import mint_portal_reference

        db = AsyncMock()
        with patch.object(
            ReferenceNumberService,
            "generate",
            new_callable=AsyncMock,
            side_effect=RuntimeError("sequence unavailable"),
        ):
            reference = await mint_portal_reference(db, "NM")

        assert reference.startswith(f"NM-{datetime.now().year}-")
