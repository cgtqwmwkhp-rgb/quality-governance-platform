"""B-10: ApprovalActionRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.document_control import ApprovalActionRequest


def test_approval_action_request_accepts_known_fields() -> None:
    m = ApprovalActionRequest(
        action="approved",
        comments="Looks good",
        conditions=None,
        delegated_to=None,
    )
    assert m.action == "approved"
    assert m.comments == "Looks good"


def test_approval_action_request_optionals_default_none() -> None:
    m = ApprovalActionRequest(action="rejected")
    assert m.comments is None
    assert m.conditions is None
    assert m.delegated_to is None


def test_approval_action_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ApprovalActionRequest(
            action="approved",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
