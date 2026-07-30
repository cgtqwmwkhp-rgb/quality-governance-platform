"""B-10: CreateWatchActionRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.governed_knowledge import CreateWatchActionRequest


def test_create_watch_action_request_accepts_known_fields() -> None:
    m = CreateWatchActionRequest(
        owner_email="owner@example.com",
        owner_id=12,
        due_date="2026-08-01",
        priority="high",
    )
    assert m.owner_email == "owner@example.com"
    assert m.owner_id == 12
    assert m.due_date == "2026-08-01"
    assert m.priority == "high"


def test_create_watch_action_request_all_optional() -> None:
    m = CreateWatchActionRequest()
    assert m.owner_email is None
    assert m.owner_id is None
    assert m.due_date is None
    assert m.priority is None


def test_create_watch_action_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CreateWatchActionRequest(
            impact_id=99,  # type: ignore[call-arg]
        )
    assert "impact_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
