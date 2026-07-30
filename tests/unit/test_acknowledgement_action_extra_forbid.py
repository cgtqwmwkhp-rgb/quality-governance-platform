"""B-10: AcknowledgementAction must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.driver_profile import AcknowledgementAction


def test_acknowledgement_action_accepts_known_fields() -> None:
    m = AcknowledgementAction(action="acknowledge", notes="confirmed")
    assert m.action == "acknowledge"
    assert m.notes == "confirmed"


def test_acknowledgement_action_notes_optional() -> None:
    m = AcknowledgementAction(action="refuse")
    assert m.notes is None


def test_acknowledgement_action_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AcknowledgementAction(
            action="acknowledge",
            signed_by=7,  # type: ignore[call-arg]
        )
    assert "signed_by" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
