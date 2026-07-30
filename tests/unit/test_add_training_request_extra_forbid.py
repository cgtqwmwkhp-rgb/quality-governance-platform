"""B-10: AddTrainingRequest must reject unknown body fields (extra=forbid)."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.api.routes.auditor_competence import AddTrainingRequest


def test_add_training_request_accepts_known_fields() -> None:
    m = AddTrainingRequest(
        training_name="ISO 45001 Awareness",
        start_date=datetime(2024, 3, 1),
        training_type="workshop",
        training_provider="BSI",
        duration_hours=8.0,
    )
    assert m.training_name == "ISO 45001 Awareness"
    assert m.training_type == "workshop"
    assert m.training_provider == "BSI"
    assert m.duration_hours == 8.0


def test_add_training_request_defaults() -> None:
    m = AddTrainingRequest(
        training_name="Intro to Auditing",
        start_date=datetime(2024, 4, 1),
    )
    assert m.training_type == "course"
    assert m.training_provider is None
    assert m.duration_hours is None


def test_add_training_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AddTrainingRequest(
            training_name="Intro to Auditing",
            start_date=datetime(2024, 4, 1),
            completed=True,  # type: ignore[call-arg]
        )
    assert "completed" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
