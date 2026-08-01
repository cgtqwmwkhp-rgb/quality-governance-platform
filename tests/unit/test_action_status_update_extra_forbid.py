"""B-10: ActionStatusUpdate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.planet_mark import ActionStatusUpdate


def test_action_status_update_accepts_known_fields() -> None:
    m = ActionStatusUpdate(
        status="completed",
        progress_percent=100,
        actual_reduction_achieved=12.5,
        lessons_learned="Good",
    )
    assert m.status == "completed"
    assert m.progress_percent == 100
    assert m.actual_reduction_achieved == 12.5


def test_action_status_update_optionals_default_none() -> None:
    m = ActionStatusUpdate(status="in_progress", progress_percent=40)
    assert m.actual_completion_date is None
    assert m.actual_reduction_achieved is None
    assert m.lessons_learned is None


def test_action_status_update_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ActionStatusUpdate(
            status="in_progress",
            progress_percent=10,
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
