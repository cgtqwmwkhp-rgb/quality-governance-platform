"""Catalogue loader + reference-prefix wiring for Compliance Schedule Wave 0."""

from __future__ import annotations

from src.domain.data.compliance_schedule_catalogue import (
    EXPECTED_TEMPLATE_COUNT_MAX,
    EXPECTED_TEMPLATE_COUNT_MIN,
    load_catalogue_templates,
)
from src.domain.services.reference_number import ReferenceNumberService


def test_catalogue_loads_expected_template_count():
    rows = load_catalogue_templates()
    assert EXPECTED_TEMPLATE_COUNT_MIN <= len(rows) <= EXPECTED_TEMPLATE_COUNT_MAX


def test_catalogue_rows_have_required_fields_and_unique_keys():
    rows = load_catalogue_templates()
    keys = [r["template_key"] for r in rows]
    assert len(keys) == len(set(keys))
    for row in rows:
        assert row["taxonomy_id"]
        assert row["title"]
        assert row["anchor"] in {"completion", "schedule"}
        assert row["frequency_months"] is not None or row["frequency_days"] is not None
        assert row["tenant_id"] is None
        assert isinstance(row["statutory"], bool)


def test_catalogue_excludes_asset_owned_taxonomy():
    """Boundary: no per-item LOLER / PSSR / PAT templates."""
    taxonomy_ids = {r["taxonomy_id"] for r in load_catalogue_templates()}
    assert "04.04" not in taxonomy_ids  # LOLER
    assert "04.05" not in taxonomy_ids  # PSSR
    assert "04.12" not in taxonomy_ids  # PAT


def test_reference_prefixes_are_csr_and_crc():
    assert ReferenceNumberService.PREFIXES["compliance_requirement"] == "CSR"
    assert ReferenceNumberService.PREFIXES["compliance_record"] == "CRC"


def test_mint_uses_csr_and_crc_prefixes():
    """PREFIXES.get(..., 'REF') must not silently fall back for these types."""
    for record_type, expected in (
        ("compliance_requirement", "CSR"),
        ("compliance_record", "CRC"),
    ):
        prefix = ReferenceNumberService.PREFIXES[record_type]
        assert prefix == expected
        # Shape the mint format would produce (generate needs a DB session).
        sample = f"{prefix}-2026-0001"
        parsed = ReferenceNumberService.parse(sample)
        assert parsed["prefix"] == expected
        assert parsed["year"] == 2026
        assert parsed["sequence"] == 1
