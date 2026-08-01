"""B-10: AuditResponseCreate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.audit import AuditResponseCreate


def test_audit_response_create_accepts_known_fields() -> None:
    m = AuditResponseCreate(
        question_id=12,
        response_value="yes",
        notes="Verified on site",
        is_na=False,
    )
    assert m.question_id == 12
    assert m.response_value == "yes"


def test_audit_response_create_defaults() -> None:
    m = AuditResponseCreate(question_id=12)
    assert m.is_na is False
    assert m.response_text is None


def test_audit_response_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditResponseCreate(
            question_id=12,
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
