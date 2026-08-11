from src.domain.services.external_audit_analysis_service import (
    DraftFindingCandidate,
    ExternalAuditAnalysisService,
)


def test_outcome_status_prioritizes_failures_over_observations() -> None:
    service = ExternalAuditAnalysisService()

    result = service.analyze(
        extracted_text=(
            "Audit summary: observation recorded. " "Major non-conformance identified against the management system."
        ),
        page_texts=[
            "Audit summary: observation recorded.",
            "Major non-conformance identified against the management system.",
        ],
        assurance_scheme="Achilles UVDB",
    )

    assert result.outcome_status == "fail"


def test_competence_verdict_only_applies_to_competence_gaps() -> None:
    service = ExternalAuditAnalysisService()

    result = service.analyze(
        extracted_text="Major non-conformance identified. Recommendation issued.",
        page_texts=["Major non-conformance identified. Recommendation issued."],
        assurance_scheme="Achilles UVDB",
    )

    nonconformity = next(finding for finding in result.findings if finding.finding_type == "nonconformity")

    assert nonconformity.competence_verdict is None


def _draft(
    *,
    title: str,
    description: str,
    finding_type: str = "positive_practice",
    confidence: float = 0.8,
    pages: list[int] | None = None,
    snippets: list[str] | None = None,
    provenance: dict | None = None,
) -> DraftFindingCandidate:
    return DraftFindingCandidate(
        title=title,
        description=description,
        severity="low",
        finding_type=finding_type,
        confidence_score=confidence,
        competence_verdict=None,
        source_pages=list(pages or [1]),
        evidence_snippets=list(snippets or [description[:40]]),
        provenance=dict(provenance or {}),
    )


def test_dedupe_clusters_per_page_compliant_flood() -> None:
    """FR-DEDUP-03: same Compliant title across pages collapses to one draft."""
    service = ExternalAuditAnalysisService()
    findings = [
        _draft(
            title="Section 4: Compliant",
            description=f"Page {page} keyword hit — Compliant observed in section text.",
            confidence=0.70 + (page * 0.01),
            pages=[page],
            provenance={"trigger": "compliant"},
        )
        for page in (1, 2, 3, 4)
    ]

    deduped = service._dedupe_findings(findings)

    assert len(deduped) == 1
    winner = deduped[0]
    assert winner.source_pages == [1, 2, 3, 4]
    assert winner.provenance.get("cluster_merged") is True
    assert winner.provenance.get("cluster_size") == 4
    # Highest confidence + description length preference among equals on conf.
    assert winner.confidence_score == max(f.confidence_score for f in findings)


def test_dedupe_clusters_by_shared_clause_id() -> None:
    service = ExternalAuditAnalysisService()
    findings = [
        _draft(
            title="Competence evidence incomplete",
            description="7.1 | Training records missing for two operatives on site A.",
            finding_type="nonconformity",
            confidence=0.82,
            pages=[3],
        ),
        _draft(
            title="Competence evidence incomplete",
            description="Clause 7.1 training matrix not signed off for new starters.",
            finding_type="nonconformity",
            confidence=0.91,
            pages=[7],
            provenance={"clause_reference": "7.1"},
        ),
    ]

    deduped = service._dedupe_findings(findings)

    assert len(deduped) == 1
    assert deduped[0].confidence_score == 0.91
    assert deduped[0].source_pages == [3, 7]


def test_dedupe_keeps_distinct_findings_without_shared_clause() -> None:
    service = ExternalAuditAnalysisService()
    findings = [
        _draft(
            title="Observation on waste segregation",
            description="Skip labels inconsistent at compound gate.",
            finding_type="observation",
            confidence=0.75,
            pages=[2],
        ),
        _draft(
            title="Observation on waste segregation",
            description="Different issue: oil drip trays missing under parked plant.",
            finding_type="observation",
            confidence=0.75,
            pages=[5],
        ),
    ]

    deduped = service._dedupe_findings(findings)

    assert len(deduped) == 2
