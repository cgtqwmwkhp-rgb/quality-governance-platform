from types import SimpleNamespace

from src.domain.services.external_audit_uvdb_iso_mapping_service import ExternalAuditUVDBISOMappingService


def _matrix_row(
    *,
    question_number: str = "2.3",
    question_text: str = "How does the company guarantee confidentiality, availability and integrity of information?",
    standard: str = "27001",
    clause: str = "5.1",
    mapping_type: str = "direct",
) -> tuple[SimpleNamespace, SimpleNamespace]:
    return (
        SimpleNamespace(
            iso_standard=standard,
            iso_clause=clause,
            iso_clause_title="Information security policies",
            mapping_type=mapping_type,
            mapping_notes="UVDB Verify B2 matrix",
        ),
        SimpleNamespace(question_number=question_number, question_text=question_text),
    )


def test_enrichment_attaches_matrix_mapping_and_readiness_to_uvdb_draft() -> None:
    enrichment = ExternalAuditUVDBISOMappingService.enrich_from_rows(
        detected_scheme="achilles_uvdb",
        candidate_texts=["UVDB question 2.3 found an information security gap."],
        rows=[_matrix_row()],
    )

    assert enrichment.candidate_mapped_standards[0] == [
        {
            "standard": "ISO 27001",
            "clause_number": "5.1",
            "title": "Information security policies",
            "basis": "uvdb_iso_cross_mapping",
            "confidence": 0.95,
            "mapping_type": "direct",
            "uvdb_question": "2.3",
            "uvdb_question_text": "How does the company guarantee confidentiality, availability and integrity of information?",
            "mapping_notes": "UVDB Verify B2 matrix",
        }
    ]
    assert enrichment.candidate_readiness[0]["verify_mapped_iso_clause_evidence"] is True
    assert enrichment.candidate_readiness[0]["blocks_promotion"] is False
    assert enrichment.readiness_checklist["reviewer_confirmation_required"] is True


def test_enrichment_requires_manual_review_when_uvdb_draft_has_no_matrix_match() -> None:
    enrichment = ExternalAuditUVDBISOMappingService.enrich_from_rows(
        detected_scheme="achilles_uvdb",
        candidate_texts=["A generic audit observation needs review."],
        rows=[_matrix_row()],
    )

    assert enrichment.candidate_mapped_standards == [[]]
    assert enrichment.candidate_readiness[0]["manual_mapping_review_required"] is True
    assert enrichment.candidate_readiness[0]["blocks_promotion"] is False


def test_enrichment_does_not_apply_uvdb_matrix_to_other_schemes() -> None:
    enrichment = ExternalAuditUVDBISOMappingService.enrich_from_rows(
        detected_scheme="iso",
        candidate_texts=["ISO 27001:2022 finding"],
        rows=[_matrix_row()],
    )

    assert enrichment.mapped_standards == []
    assert enrichment.candidate_mapped_standards == [[]]
    assert enrichment.readiness_checklist["uvdb_iso_matrix_applicable"] is False


def test_merge_preserves_existing_standard_mapping() -> None:
    merged = ExternalAuditUVDBISOMappingService.merge_mapped_standards(
        [{"standard": "ISO 27001", "confidence": 0.8, "basis": "explicit_reference"}],
        ExternalAuditUVDBISOMappingService.enrich_from_rows(
            detected_scheme="achilles_uvdb",
            candidate_texts=["Question 2.3"],
            rows=[_matrix_row()],
        ).candidate_mapped_standards[0],
    )

    assert [item["basis"] for item in merged] == ["explicit_reference", "uvdb_iso_cross_mapping"]
