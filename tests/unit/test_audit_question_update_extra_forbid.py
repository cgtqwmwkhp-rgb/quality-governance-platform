"""B-10: AuditQuestionUpdate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.audit import AuditQuestionUpdate


def test_audit_question_update_accepts_known_fields() -> None:
    m = AuditQuestionUpdate(question_text="Updated question?", is_required=False)
    assert m.question_text == "Updated question?"
    assert m.is_required is False


def test_audit_question_update_all_optional() -> None:
    m = AuditQuestionUpdate()
    assert m.question_text is None
    assert m.question_type is None


def test_audit_question_update_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditQuestionUpdate(
            question_text="Updated question?",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
