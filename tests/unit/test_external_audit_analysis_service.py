from src.domain.services.external_audit_analysis_service import ExternalAuditAnalysisService


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
