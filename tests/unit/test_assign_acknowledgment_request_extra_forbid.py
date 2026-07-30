"""B-10: AssignAcknowledgmentRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.policy_acknowledgment import AssignAcknowledgmentRequest


def test_assign_acknowledgment_request_accepts_known_fields() -> None:
    m = AssignAcknowledgmentRequest(user_ids=[1, 2, 3], policy_version="1.2")
    assert m.user_ids == [1, 2, 3]
    assert m.policy_version == "1.2"


def test_assign_acknowledgment_request_defaults() -> None:
    m = AssignAcknowledgmentRequest(user_ids=[9])
    assert m.user_ids == [9]
    assert m.policy_version is None


def test_assign_acknowledgment_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AssignAcknowledgmentRequest(
            user_ids=[1],
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
