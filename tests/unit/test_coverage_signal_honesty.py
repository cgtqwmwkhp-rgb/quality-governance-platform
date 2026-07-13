"""Coverage honesty: operational signals must not inflate coverage_percentage."""

from __future__ import annotations

from src.domain.services.iso_compliance_service import (
    EvidenceLink,
    ISOComplianceService,
    ISOStandard,
    counts_toward_compliance_coverage,
)


def _level2_clause_id(standard: ISOStandard = ISOStandard.ISO_9001) -> str:
    svc = ISOComplianceService()
    clause = next(c for c in svc.get_all_clauses(standard) if c.level == 2)
    return clause.id


def _link(
    *,
    clause_id: str,
    signal_type: str | None,
    entity_type: str = "document",
    entity_id: str = "1",
    link_id: str = "1",
) -> EvidenceLink:
    return EvidenceLink(
        id=link_id,
        entity_type=entity_type,
        entity_id=entity_id,
        clause_id=clause_id,
        linked_by="manual",
        confidence=1.0,
        signal_type=signal_type,
    )


class TestCountsTowardComplianceCoverage:
    def test_evidence_counts(self) -> None:
        assert counts_toward_compliance_coverage("evidence") is True

    def test_legacy_null_counts(self) -> None:
        assert counts_toward_compliance_coverage(None) is True
        assert counts_toward_compliance_coverage("") is True

    def test_nonconformity_excluded(self) -> None:
        assert counts_toward_compliance_coverage("nonconformity") is False

    def test_gap_and_opportunity_excluded(self) -> None:
        assert counts_toward_compliance_coverage("gap") is False
        assert counts_toward_compliance_coverage("opportunity") is False


class TestCalculateComplianceCoverageHonesty:
    def test_nonconformity_does_not_increase_coverage_percentage(self) -> None:
        svc = ISOComplianceService()
        clause_id = _level2_clause_id()

        empty = svc.calculate_compliance_coverage([], ISOStandard.ISO_9001)
        with_nc = svc.calculate_compliance_coverage(
            [_link(clause_id=clause_id, signal_type="nonconformity", entity_type="incident")],
            ISOStandard.ISO_9001,
        )
        with_evidence = svc.calculate_compliance_coverage(
            [_link(clause_id=clause_id, signal_type="evidence", entity_type="document")],
            ISOStandard.ISO_9001,
        )

        assert with_nc["coverage_percentage"] == empty["coverage_percentage"]
        assert with_nc["partial_coverage"] == empty["partial_coverage"]
        assert with_evidence["coverage_percentage"] > empty["coverage_percentage"]
        assert with_evidence["partial_coverage"] == empty["partial_coverage"] + 1

    def test_gap_and_opportunity_do_not_increase_coverage(self) -> None:
        svc = ISOComplianceService()
        clause_id = _level2_clause_id()
        empty = svc.calculate_compliance_coverage([], ISOStandard.ISO_9001)

        for signal in ("gap", "opportunity"):
            result = svc.calculate_compliance_coverage(
                [_link(clause_id=clause_id, signal_type=signal, entity_type="near_miss", link_id=signal)],
                ISOStandard.ISO_9001,
            )
            assert result["coverage_percentage"] == empty["coverage_percentage"]

    def test_legacy_null_signal_still_counts(self) -> None:
        svc = ISOComplianceService()
        clause_id = _level2_clause_id()
        empty = svc.calculate_compliance_coverage([], ISOStandard.ISO_9001)
        legacy = svc.calculate_compliance_coverage(
            [_link(clause_id=clause_id, signal_type=None)],
            ISOStandard.ISO_9001,
        )
        assert legacy["coverage_percentage"] > empty["coverage_percentage"]

    def test_nc_alongside_evidence_does_not_double_count(self) -> None:
        """NC on same clause must not push partial→full beyond the evidence link."""
        svc = ISOComplianceService()
        clause_id = _level2_clause_id()

        evidence_only = svc.calculate_compliance_coverage(
            [_link(clause_id=clause_id, signal_type="evidence", link_id="e1")],
            ISOStandard.ISO_9001,
        )
        evidence_plus_nc = svc.calculate_compliance_coverage(
            [
                _link(clause_id=clause_id, signal_type="evidence", link_id="e1"),
                _link(
                    clause_id=clause_id,
                    signal_type="nonconformity",
                    entity_type="incident",
                    entity_id="99",
                    link_id="nc1",
                ),
            ],
            ISOStandard.ISO_9001,
        )

        assert evidence_plus_nc["coverage_percentage"] == evidence_only["coverage_percentage"]
        assert evidence_plus_nc["partial_coverage"] == evidence_only["partial_coverage"]
        assert evidence_plus_nc["full_coverage"] == evidence_only["full_coverage"]
