"""B-10: AuditQuestionCreate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.audit import AuditQuestionCreate


def test_audit_question_create_accepts_known_fields() -> None:
    m = AuditQuestionCreate(
        question_text="Is induction complete?",
        question_type="yes_no",
        section_id=3,
        is_required=True,
    )
    assert m.question_text == "Is induction complete?"
    assert m.section_id == 3


def test_audit_question_create_defaults() -> None:
    m = AuditQuestionCreate(
        question_text="Is induction complete?",
        question_type="yes_no",
    )
    assert m.is_required is True
    assert m.section_id is None
    assert m.positive_answer == "yes"


def test_audit_question_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditQuestionCreate(
            question_text="Is induction complete?",
            question_type="yes_no",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
