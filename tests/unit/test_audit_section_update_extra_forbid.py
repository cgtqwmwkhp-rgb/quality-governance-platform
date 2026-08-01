"""B-10: AuditSectionUpdate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.audit import AuditSectionUpdate


def test_audit_section_update_accepts_known_fields() -> None:
    m = AuditSectionUpdate(title="Updated section", weight=2.0, is_active=False)
    assert m.title == "Updated section"
    assert m.weight == 2.0


def test_audit_section_update_all_optional() -> None:
    m = AuditSectionUpdate()
    assert m.title is None
    assert m.description is None


def test_audit_section_update_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditSectionUpdate(
            title="Updated section",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
