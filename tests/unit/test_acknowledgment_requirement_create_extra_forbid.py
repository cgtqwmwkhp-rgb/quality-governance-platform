"""B-10: AcknowledgmentRequirementCreate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.policy_acknowledgment import AcknowledgmentRequirementCreate


def test_acknowledgment_requirement_create_accepts_known_fields() -> None:
    m = AcknowledgmentRequirementCreate(
        policy_id=3,
        acknowledgment_type="accept",
        required_for_all=True,
        due_within_days=14,
        quiz_passing_score=90,
    )
    assert m.policy_id == 3
    assert m.acknowledgment_type == "accept"
    assert m.due_within_days == 14


def test_acknowledgment_requirement_create_defaults() -> None:
    m = AcknowledgmentRequirementCreate(policy_id=1)
    assert m.acknowledgment_type == "read_only"
    assert m.required_for_all is False
    assert m.due_within_days == 30
    assert m.quiz_passing_score == 80
    assert m.is_active is True


def test_acknowledgment_requirement_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AcknowledgmentRequirementCreate(
            policy_id=1,
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
