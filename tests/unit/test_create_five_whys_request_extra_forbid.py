"""B-10: CreateFiveWhysRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.rca_tools import CreateFiveWhysRequest


def test_create_five_whys_request_accepts_known_fields() -> None:
    m = CreateFiveWhysRequest(
        problem_statement="Brake failure on site",
        entity_type="incident",
        entity_id=42,
        investigation_id=7,
    )
    assert m.problem_statement == "Brake failure on site"
    assert m.entity_type == "incident"
    assert m.entity_id == 42
    assert m.investigation_id == 7


def test_create_five_whys_request_optional_fields_default_none() -> None:
    m = CreateFiveWhysRequest(problem_statement="Near miss on ramp")
    assert m.entity_type is None
    assert m.entity_id is None
    assert m.investigation_id is None


def test_create_five_whys_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CreateFiveWhysRequest(
            problem_statement="Brake failure on site",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
