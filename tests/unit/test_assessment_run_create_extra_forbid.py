"""B-10: AssessmentRunCreate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.assessment import AssessmentRunCreate


def test_assessment_run_create_accepts_known_fields() -> None:
    m = AssessmentRunCreate(
        template_id=1,
        engineer_id=2,
        title="Run A",
        location="Bay 3",
        notes="prep",
    )
    assert m.template_id == 1
    assert m.engineer_id == 2
    assert m.title == "Run A"


def test_assessment_run_create_optionals_default_none() -> None:
    m = AssessmentRunCreate(template_id=1, engineer_id=2)
    assert m.asset_type_id is None
    assert m.asset_id is None
    assert m.title is None
    assert m.scheduled_date is None


def test_assessment_run_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AssessmentRunCreate(
            template_id=1,
            engineer_id=2,
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
