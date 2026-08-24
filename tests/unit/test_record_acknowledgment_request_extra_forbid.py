"""B-10: RecordAcknowledgmentRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.policy_acknowledgment import RecordAcknowledgmentRequest


def test_record_acknowledgment_request_accepts_known_fields() -> None:
    m = RecordAcknowledgmentRequest(
        quiz_score=95,
        acceptance_statement="I have read and understood this document.",
        signature_data="data:image/png;base64,abc",
    )
    assert m.quiz_score == 95
    assert m.acceptance_statement == "I have read and understood this document."
    assert m.signature_data == "data:image/png;base64,abc"


def test_record_acknowledgment_request_all_optional() -> None:
    m = RecordAcknowledgmentRequest()
    assert m.quiz_score is None
    assert m.acceptance_statement is None
    assert m.signature_data is None


def test_record_acknowledgment_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RecordAcknowledgmentRequest(
            acceptance_statement="ok",
            acknowledgment_id=99,  # type: ignore[call-arg]
        )
    assert "acknowledgment_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
