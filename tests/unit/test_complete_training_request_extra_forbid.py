"""B-10: CompleteTrainingRequest must reject unknown body fields (extra=forbid)."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.api.routes.auditor_competence import CompleteTrainingRequest


def test_complete_training_request_accepts_known_fields() -> None:
    m = CompleteTrainingRequest(
        completion_date=datetime(2024, 6, 15),
        assessment_passed=True,
        assessment_score=92.5,
        cpd_hours_earned=3.0,
    )
    assert m.completion_date == datetime(2024, 6, 15)
    assert m.assessment_passed is True
    assert m.assessment_score == 92.5
    assert m.cpd_hours_earned == 3.0


def test_complete_training_request_optionals_default_none() -> None:
    m = CompleteTrainingRequest(completion_date=datetime(2024, 1, 1))
    assert m.assessment_passed is None
    assert m.assessment_score is None
    assert m.cpd_hours_earned is None


def test_complete_training_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CompleteTrainingRequest(
            completion_date=datetime(2024, 6, 15),
            training_id=99,  # type: ignore[call-arg]
        )
    assert "training_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
