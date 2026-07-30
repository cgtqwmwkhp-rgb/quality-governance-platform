"""B-10: AcknowledgementCreate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.driver_profile import AcknowledgementCreate


def test_acknowledgement_create_accepts_known_fields() -> None:
    m = AcknowledgementCreate(
        entity_type="vehicle_defect",
        entity_id=12,
        notes="please confirm",
    )
    assert m.entity_type == "vehicle_defect"
    assert m.entity_id == 12
    assert m.notes == "please confirm"


def test_acknowledgement_create_notes_optional() -> None:
    m = AcknowledgementCreate(entity_type="vehicle_assignment", entity_id=3)
    assert m.notes is None


def test_acknowledgement_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AcknowledgementCreate(
            entity_type="vehicle_defect",
            entity_id=12,
            driver_id=99,  # type: ignore[call-arg]
        )
    assert "driver_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
