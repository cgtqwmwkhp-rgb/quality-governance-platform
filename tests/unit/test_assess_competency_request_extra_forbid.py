"""B-10: AssessCompetencyRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.auditor_competence import AssessCompetencyRequest


def test_assess_competency_request_accepts_known_fields() -> None:
    m = AssessCompetencyRequest(
        competency_area_id=3,
        current_level=4,
        assessment_method="peer",
        evidence_summary="Observed lead audit",
    )
    assert m.competency_area_id == 3
    assert m.current_level == 4
    assert m.assessment_method == "peer"
    assert m.evidence_summary == "Observed lead audit"


def test_assess_competency_request_defaults() -> None:
    m = AssessCompetencyRequest(competency_area_id=1, current_level=2)
    assert m.assessment_method == "supervisor"
    assert m.evidence_summary is None


def test_assess_competency_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AssessCompetencyRequest(
            competency_area_id=3,
            current_level=4,
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
