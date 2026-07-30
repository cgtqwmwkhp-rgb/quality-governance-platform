"""B-10: AddCauseRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.rca_tools import AddCauseRequest


def test_add_cause_request_accepts_known_fields() -> None:
    m = AddCauseRequest(
        category="method",
        cause="Missing checklist",
        sub_causes=["No template", "Skipped step"],
    )
    assert m.category == "method"
    assert m.cause == "Missing checklist"
    assert m.sub_causes == ["No template", "Skipped step"]


def test_add_cause_request_sub_causes_optional() -> None:
    m = AddCauseRequest(category="manpower", cause="Fatigue")
    assert m.sub_causes is None


def test_add_cause_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AddCauseRequest(
            category="machine",
            cause="Worn brake",
            diagram_id=99,  # type: ignore[call-arg]
        )
    assert "diagram_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
