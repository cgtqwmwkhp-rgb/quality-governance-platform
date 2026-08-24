"""B-10: CreateFishboneRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.rca_tools import CreateFishboneRequest


def test_create_fishbone_request_accepts_known_fields() -> None:
    m = CreateFishboneRequest(
        effect_statement="Delayed handover",
        entity_type="complaint",
        entity_id=11,
        investigation_id=3,
    )
    assert m.effect_statement == "Delayed handover"
    assert m.entity_type == "complaint"
    assert m.entity_id == 11
    assert m.investigation_id == 3


def test_create_fishbone_request_optional_fields_default_none() -> None:
    m = CreateFishboneRequest(effect_statement="Missed checklist")
    assert m.entity_type is None
    assert m.entity_id is None
    assert m.investigation_id is None


def test_create_fishbone_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CreateFishboneRequest(
            effect_statement="Delayed handover",
            diagram_id=99,  # type: ignore[call-arg]
        )
    assert "diagram_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
