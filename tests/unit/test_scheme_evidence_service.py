"""Loaded scheme Evidence trees (CE / CE+ / IiP) — own axis, no invented EXACT."""

from src.domain.services.iso_compliance_service import EvidenceLink
from src.domain.services.scheme_evidence_service import (
    LOADED_SCHEME_EVIDENCE_IDS,
    loaded_scheme_id,
    merge_scheme_into_iso_coverage,
    scheme_clause_by_id,
    scheme_clause_records,
    scheme_coverage_payload,
    scheme_standard_coverage,
)


def test_loaded_scheme_ids_exclude_provisional_and_specialist() -> None:
    assert LOADED_SCHEME_EVIDENCE_IDS == frozenset({"ce", "cep", "iip"})
    assert loaded_scheme_id("ce") == "ce"
    assert loaded_scheme_id("CHAS") is None
    assert loaded_scheme_id("ssip") is None
    assert loaded_scheme_id("pm") is None
    assert loaded_scheme_id("uvdb") is None
    assert loaded_scheme_id("iso9001") is None


def test_ce_axis_has_five_ncsc_controls() -> None:
    rows = scheme_clause_records("ce")
    numbers = {row["clause_number"] for row in rows}
    assert numbers == {
        "firewalls",
        "secure_configuration",
        "user_access_control",
        "malware_protection",
        "patch_management",
    }
    assert all(row["id"].startswith("ce-") for row in rows)
    assert scheme_clause_by_id("ce-firewalls")["title"] == "Firewalls"


def test_iip_axis_has_nine_indicators() -> None:
    rows = scheme_clause_records("iip")
    assert len(rows) == 9
    assert {row["clause_number"] for row in rows} == {f"IIP {n}" for n in range(1, 10)}


def test_scheme_coverage_is_all_gaps_without_cel() -> None:
    payload = scheme_coverage_payload([])
    assert payload["by_standard"]["ce"]["total"] == 5
    assert payload["by_standard"]["ce"]["covered"] == 0
    assert payload["by_standard"]["iip"]["total"] == 9
    assert payload["gaps"] == 5 + 5 + 9


def test_scheme_coverage_counts_only_matching_catalogue_keys() -> None:
    links = [
        EvidenceLink(
            id="1",
            entity_type="document",
            entity_id="DOC-1",
            clause_id="ce-firewalls",
            linked_by="manual",
            signal_type="evidence",
        ),
        EvidenceLink(
            id="2",
            entity_type="document",
            entity_id="DOC-2",
            clause_id="9001-7.5",
            linked_by="manual",
            signal_type="evidence",
        ),
        EvidenceLink(
            id="3",
            entity_type="audit",
            entity_id="AUD-1",
            clause_id="ce-firewalls",
            linked_by="manual",
            signal_type="evidence",
        ),
    ]
    cov = scheme_standard_coverage(links, "ce")
    assert cov["covered"] == 1
    assert cov["partial_coverage"] == 0
    assert cov["total"] == 5


def test_iso_coverage_merge_does_not_drop_iso_keys() -> None:
    iso = {
        "total_clauses": 10,
        "by_standard": {"iso9001": {"total": 37, "covered": 1, "partial_coverage": 0, "percentage": 2.7}},
    }
    merged = merge_scheme_into_iso_coverage(iso, [])
    assert merged["by_standard"]["iso9001"]["total"] == 37
    assert merged["by_standard"]["ce"]["total"] == 5
    assert "chas" not in merged["by_standard"]
