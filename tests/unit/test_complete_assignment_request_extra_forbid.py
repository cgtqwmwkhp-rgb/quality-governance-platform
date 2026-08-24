"""B-10: CompleteAssignmentRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.document_campaign import CompleteAssignmentRequest


def test_complete_assignment_request_accepts_known_fields() -> None:
    m = CompleteAssignmentRequest(
        acceptance_statement="I have read and understood this document",
        signature_data="data:image/png;base64,abc",
        signature_disposition="signed",
    )
    assert m.acceptance_statement == "I have read and understood this document"
    assert m.signature_data == "data:image/png;base64,abc"
    assert m.signature_disposition == "signed"


def test_complete_assignment_request_optionals_default_none() -> None:
    m = CompleteAssignmentRequest(acceptance_statement="Accepted")
    assert m.signature_data is None
    assert m.signature_disposition is None


def test_complete_assignment_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CompleteAssignmentRequest(
            acceptance_statement="Accepted",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
