"""B-10: QuestionReplyRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.document_campaign import QuestionReplyRequest


def test_question_reply_request_accepts_known_fields() -> None:
    m = QuestionReplyRequest(body="Please see the attached guidance.")
    assert m.body == "Please see the attached guidance."


def test_question_reply_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        QuestionReplyRequest(
            body="A reply",
            thread_id=99,  # type: ignore[call-arg]
        )
    assert "thread_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
