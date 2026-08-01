"""B-10: AuditTemplateUpdate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.audit import AuditTemplateUpdate


def test_audit_template_update_accepts_known_fields() -> None:
    m = AuditTemplateUpdate(name="Updated name", is_active=False, category="H&S")
    assert m.name == "Updated name"
    assert m.is_active is False


def test_audit_template_update_all_optional() -> None:
    m = AuditTemplateUpdate()
    assert m.name is None
    assert m.description is None


def test_audit_template_update_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditTemplateUpdate(
            name="Updated name",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
