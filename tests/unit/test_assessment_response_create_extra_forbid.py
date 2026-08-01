"""B-10: AssessmentResponseCreate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.assessment import AssessmentResponseCreate


def test_assessment_response_create_accepts_known_fields() -> None:
    m = AssessmentResponseCreate(
        question_id=4,
        verdict="competent",
        feedback="Good",
        supervisor_notes="Noted",
    )
    assert m.question_id == 4
    assert m.verdict == "competent"


def test_assessment_response_create_optionals_default_none() -> None:
    m = AssessmentResponseCreate(question_id=1)
    assert m.verdict is None
    assert m.feedback is None
    assert m.supervisor_notes is None


def test_assessment_response_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AssessmentResponseCreate(
            question_id=1,
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
