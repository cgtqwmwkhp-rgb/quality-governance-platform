"""B-10: AssessmentResponseUpdate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.assessment import AssessmentResponseUpdate


def test_assessment_response_update_accepts_known_fields() -> None:
    m = AssessmentResponseUpdate(
        verdict="competent",
        feedback="ok",
        supervisor_notes="signed",
        engineer_signature="sig",
    )
    assert m.verdict == "competent"
    assert m.engineer_signature == "sig"


def test_assessment_response_update_all_optional() -> None:
    m = AssessmentResponseUpdate()
    assert m.verdict is None
    assert m.feedback is None
    assert m.engineer_signed_at is None


def test_assessment_response_update_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AssessmentResponseUpdate(
            verdict="na",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
