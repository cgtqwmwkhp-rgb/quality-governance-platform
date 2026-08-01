"""B-10: AssessmentRunUpdate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.assessment import AssessmentRunUpdate


def test_assessment_run_update_accepts_known_fields() -> None:
    m = AssessmentRunUpdate(title="T", location="L", notes="n", status="in_progress")
    assert m.title == "T"
    assert m.status == "in_progress"


def test_assessment_run_update_all_optional() -> None:
    m = AssessmentRunUpdate()
    assert m.title is None
    assert m.status is None


def test_assessment_run_update_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AssessmentRunUpdate(
            title="T",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
