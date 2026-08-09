"""Library WK-1 / L-47 — framework evidence packs match frozen fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.domain.services.framework_evidence_pack_builder import (
    PACK_VERSION,
    build_iso9001_evidence_pack,
    build_planet_mark_evidence_pack,
    build_uvdb_b2_evidence_pack,
    row_matches_framework,
)

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "specs" / "governance-library" / "fixtures" / "evidence-packs"

# WI-1 conflict paths — this slice must never touch them.
_FORBIDDEN_PATH_MARKERS = (
    "compliance_evidence.py",
    "20261030_lib_wi1",
    "clause_catalogue_seed.py",
)


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("input_name", "fixture_name", "builder"),
    [
        ("iso9001.input-rows.json", "iso9001.pack.fixture.json", build_iso9001_evidence_pack),
        ("uvdb-b2.input-rows.json", "uvdb-b2.pack.fixture.json", build_uvdb_b2_evidence_pack),
        (
            "planet-mark.input-rows.json",
            "planet-mark.pack.fixture.json",
            build_planet_mark_evidence_pack,
        ),
    ],
)
def test_framework_pack_matches_fixture(input_name: str, fixture_name: str, builder) -> None:
    payload = _load(input_name)
    expected = _load(fixture_name)
    actual = builder(
        payload["rows"],
        generated_at=payload["generated_at"],
        exported_by=payload["exported_by"],
        organization_name=payload["organization_name"],
        include_nonconformity=False,
    )
    assert actual == expected
    assert actual["pack_version"] == PACK_VERSION
    assert actual["provenance_policy"]["no_coverage_twin_tables"] is True


def test_iso9001_excludes_operational_nc_by_default() -> None:
    payload = _load("iso9001.input-rows.json")
    pack = build_iso9001_evidence_pack(
        payload["rows"],
        generated_at=payload["generated_at"],
        exported_by=payload["exported_by"],
        organization_name=payload["organization_name"],
    )
    exported_ids = {row["id"] for row in pack["evidence_links"]}
    assert "cel-9001-nc" not in exported_ids
    assert {row["id"] for row in pack["operational_signals"]} == {"cel-9001-nc"}
    assert pack["counts"]["matched_rows"] == 3
    assert "cel-uvdb-noise" not in exported_ids


def test_framework_filter_ignores_cross_scheme_noise() -> None:
    assert row_matches_framework({"scheme": "iso9001"}, "iso9001")
    assert not row_matches_framework({"scheme": "uvdb_b2"}, "iso9001")
    assert row_matches_framework({"standard": "PLANET_MARK"}, "planet_mark")


def test_current_issue_count_includes_live_and_published_synonyms() -> None:
    """Portal badge maps LIVE/PUBLISHED → CURRENT; pack counts must match."""
    from src.domain.services.framework_evidence_pack_builder import is_current_issue_state

    assert is_current_issue_state("CURRENT")
    assert is_current_issue_state("live")
    assert is_current_issue_state("Published")
    assert not is_current_issue_state("SUPERSEDED")
    assert not is_current_issue_state(None)

    rows = [
        {
            "id": "a",
            "entity_type": "document",
            "entity_id": "1",
            "clause_id": "9001-4.1",
            "scheme": "iso9001",
            "signal_type": "evidence",
            "document_issue_state": "LIVE",
        },
        {
            "id": "b",
            "entity_type": "document",
            "entity_id": "2",
            "clause_id": "9001-4.2",
            "scheme": "iso9001",
            "signal_type": "evidence",
            "document_issue_state": "PUBLISHED",
        },
        {
            "id": "c",
            "entity_type": "document",
            "entity_id": "3",
            "clause_id": "9001-4.3",
            "scheme": "iso9001",
            "signal_type": "evidence",
            "document_issue_state": "SUPERSEDED",
        },
    ]
    pack = build_iso9001_evidence_pack(
        rows,
        generated_at="2026-08-09T00:00:00Z",
        exported_by="test",
        organization_name="Org",
    )
    assert pack["counts"]["current_issue_links"] == 2
    assert pack["counts"]["exported_evidence_links"] == 3


def test_cover_kind_default_and_coexistence_shape() -> None:
    """WI-1 cover_kind is carried through; covers+evidences may coexist on same clause."""
    payload = _load("iso9001.input-rows.json")
    pack = build_iso9001_evidence_pack(
        payload["rows"],
        generated_at=payload["generated_at"],
        exported_by=payload["exported_by"],
        organization_name=payload["organization_name"],
    )
    kinds = {(row["clause_id"], row["cover_kind"]) for row in pack["evidence_links"]}
    assert ("9001-7.5.3", "covers") in kinds
    assert ("9001-7.5.3", "evidences") in kinds


def test_wk1_prep_does_not_edit_wi1_conflict_files() -> None:
    """Sanity: builder stays NEW-file only and does not import WI-1 conflict modules."""
    builder_path = (
        Path(__file__).resolve().parents[2] / "src" / "domain" / "services" / "framework_evidence_pack_builder.py"
    )
    text = builder_path.read_text(encoding="utf-8")
    for marker in _FORBIDDEN_PATH_MARKERS:
        assert marker not in text
    assert "from src.api.routes.compliance" not in text
    assert "from src.domain.models.compliance_evidence" not in text
    assert "from src.domain.services.governed_knowledge" not in text
    assert "import alembic" not in text
