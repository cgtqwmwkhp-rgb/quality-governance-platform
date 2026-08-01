"""B-10: ApprovalResponse (workflow approve/reject body) must reject unknown fields."""

import pytest
from pydantic import ValidationError

from src.api.routes.workflows import ApprovalResponse


def test_approval_response_accepts_known_fields() -> None:
    m = ApprovalResponse(notes="Looks fine", reason="policy")
    assert m.notes == "Looks fine"
    assert m.reason == "policy"


def test_approval_response_all_optional() -> None:
    m = ApprovalResponse()
    assert m.notes is None
    assert m.reason is None


def test_approval_response_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ApprovalResponse(
            notes="ok",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
