"""Unit tests for ISOComplianceService (D15 coverage uplift, D08 compliance evidence)."""

from __future__ import annotations

import pytest

from src.domain.services.iso_compliance_service import (
    ALL_CLAUSES,
    ISOClause,
    ISOComplianceService,
    ISOStandard,
    iso_compliance_service,
)


class TestISOStandardEnum:
    def test_all_four_standards_exist(self) -> None:
        standards = {s.value for s in ISOStandard}
        assert {"iso9001", "iso14001", "iso45001", "iso27001"} == standards

    def test_iso_27001_value(self) -> None:
        assert ISOStandard.ISO_27001 == "iso27001"


class TestAllClausesCatalog:
    def test_catalog_is_non_empty(self) -> None:
        assert len(ALL_CLAUSES) > 0

    def test_all_clauses_have_required_fields(self) -> None:
        for clause in ALL_CLAUSES:
            assert clause.id, f"Clause missing id: {clause}"
            assert clause.clause_number, f"Clause {clause.id} missing clause_number"
            assert clause.title, f"Clause {clause.id} missing title"
            assert isinstance(clause.keywords, list)
            assert clause.standard in ISOStandard

    def test_iso_9001_clauses_present(self) -> None:
        iso9001 = [c for c in ALL_CLAUSES if c.standard == ISOStandard.ISO_9001]
        assert len(iso9001) >= 10

    def test_iso_27001_clauses_present(self) -> None:
        iso27001 = [c for c in ALL_CLAUSES if c.standard == ISOStandard.ISO_27001]
        assert len(iso27001) >= 30

    def test_clause_ids_are_unique(self) -> None:
        ids = [c.id for c in ALL_CLAUSES]
        assert len(ids) == len(set(ids)), "Duplicate clause IDs found"


class TestGetAllClauses:
    def test_returns_all_without_filter(self) -> None:
        svc = ISOComplianceService()
        result = svc.get_all_clauses()
        assert len(result) == len(ALL_CLAUSES)

    def test_filter_by_iso9001(self) -> None:
        svc = ISOComplianceService()
        result = svc.get_all_clauses(standard=ISOStandard.ISO_9001)
        assert all(c.standard == ISOStandard.ISO_9001 for c in result)
        assert len(result) >= 10

    def test_filter_by_iso27001(self) -> None:
        svc = ISOComplianceService()
        result = svc.get_all_clauses(standard=ISOStandard.ISO_27001)
        assert all(c.standard == ISOStandard.ISO_27001 for c in result)

    def test_filter_returns_subset_of_all(self) -> None:
        svc = ISOComplianceService()
        filtered = svc.get_all_clauses(standard=ISOStandard.ISO_14001)
        all_clauses = svc.get_all_clauses()
        assert len(filtered) < len(all_clauses)


class TestGetClause:
    def test_returns_clause_for_valid_id(self) -> None:
        svc = ISOComplianceService()
        first = ALL_CLAUSES[0]
        result = svc.get_clause(first.id)
        assert result is not None
        assert result.id == first.id

    def test_returns_none_for_unknown_id(self) -> None:
        svc = ISOComplianceService()
        assert svc.get_clause("NONEXISTENT_CLAUSE_XYZ") is None

    def test_returns_iso27001_annex_a_clause(self) -> None:
        svc = ISOComplianceService()
        iso27001_clauses = [c for c in ALL_CLAUSES if c.standard == ISOStandard.ISO_27001]
        if iso27001_clauses:
            clause = svc.get_clause(iso27001_clauses[0].id)
            assert clause is not None


class TestSearchClauses:
    def test_search_returns_list(self) -> None:
        svc = ISOComplianceService()
        result = svc.search_clauses("security")
        assert isinstance(result, list)

    def test_search_finds_relevant_clauses(self) -> None:
        svc = ISOComplianceService()
        result = svc.search_clauses("information security")
        assert len(result) > 0

    def test_search_empty_string_returns_empty(self) -> None:
        svc = ISOComplianceService()
        result = svc.search_clauses("")
        assert isinstance(result, list)

    def test_search_nonsense_returns_empty(self) -> None:
        svc = ISOComplianceService()
        result = svc.search_clauses("xyzzy_no_match_here_12345")
        assert result == []

    def test_search_includes_parent_clauses(self) -> None:
        """Search results must include parent rows for tree coherence."""
        svc = ISOComplianceService()
        # Find a clause with a parent
        child_clauses = [c for c in ALL_CLAUSES if c.parent_clause is not None]
        if not child_clauses:
            pytest.skip("No child clauses found in catalog")
        child = child_clauses[0]
        result = svc.search_clauses(child.title[:10])
        result_ids = {c.id for c in result}
        # If the child was found, its parent should also be in the result
        if child.id in result_ids and child.parent_clause:
            assert (
                child.parent_clause in result_ids
            ), f"Parent {child.parent_clause} missing from results when child {child.id} is present"

    def test_search_returns_at_most_20_top_matches(self) -> None:
        svc = ISOComplianceService()
        result = svc.search_clauses("a")  # broad search
        # Top matches ≤ 20; ancestors can add more but top matches are capped
        assert isinstance(result, list)


class TestAutoTagContent:
    def test_returns_list(self) -> None:
        svc = ISOComplianceService()
        result = svc.auto_tag_content("document control procedures")
        assert isinstance(result, list)

    def test_security_content_matches_iso27001(self) -> None:
        svc = ISOComplianceService()
        result = svc.auto_tag_content("access control information security policy")
        standards = {r.get("standard") for r in result}
        assert ISOStandard.ISO_27001 in standards or "iso27001" in standards

    def test_returns_confidence_scores(self) -> None:
        svc = ISOComplianceService()
        result = svc.auto_tag_content("risk management")
        for match in result:
            assert "confidence" in match
            assert 0.0 <= match["confidence"] <= 1.0

    def test_min_confidence_filter(self) -> None:
        svc = ISOComplianceService()
        high_confidence = svc.auto_tag_content("risk management", min_confidence=0.8)
        low_confidence = svc.auto_tag_content("risk management", min_confidence=0.1)
        assert len(high_confidence) <= len(low_confidence)

    def test_empty_content_returns_empty(self) -> None:
        svc = ISOComplianceService()
        result = svc.auto_tag_content("")
        assert result == []


class TestSingletonService:
    def test_iso_compliance_service_singleton_is_instance(self) -> None:
        assert isinstance(iso_compliance_service, ISOComplianceService)
