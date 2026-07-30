"""B-10: CreateCapaRequest (workforce competence gaps) must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.workforce_competence_gaps import CreateCapaRequest


def test_workforce_create_capa_request_accepts_known_fields() -> None:
    m = CreateCapaRequest(
        owner_id=42,
        owner_email="owner@example.com",
        due_date="2026-08-15",
        priority="high",
    )
    assert m.owner_id == 42
    assert m.owner_email == "owner@example.com"
    assert m.due_date == "2026-08-15"
    assert m.priority == "high"


def test_workforce_create_capa_request_all_optional_empty_body() -> None:
    m = CreateCapaRequest()
    assert m.owner_id is None
    assert m.owner_email is None
    assert m.due_date is None
    assert m.priority is None


def test_workforce_create_capa_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CreateCapaRequest(
            owner_id=1,
            gap_id=99,  # type: ignore[call-arg]
        )
    assert "gap_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
