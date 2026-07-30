"""B-10: AskAssignmentQuestionRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.document_campaign import AskAssignmentQuestionRequest


def test_ask_assignment_question_request_accepts_known_fields() -> None:
    m = AskAssignmentQuestionRequest(title="Clarification", body="What does section 3 mean?")
    assert m.title == "Clarification"
    assert m.body == "What does section 3 mean?"


def test_ask_assignment_question_request_title_optional() -> None:
    m = AskAssignmentQuestionRequest(body="Need more detail on the process.")
    assert m.title is None
    assert m.body == "Need more detail on the process."


def test_ask_assignment_question_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AskAssignmentQuestionRequest(
            body="A question",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
