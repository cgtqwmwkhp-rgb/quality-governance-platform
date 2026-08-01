"""B-10: AuditTemplateCreate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.audit import AuditTemplateCreate


def test_audit_template_create_accepts_known_fields() -> None:
    m = AuditTemplateCreate(
        name="Site inspection v2",
        audit_type="inspection",
        category="H&S",
        allow_offline=True,
    )
    assert m.name == "Site inspection v2"
    assert m.allow_offline is True


def test_audit_template_create_defaults() -> None:
    m = AuditTemplateCreate(name="Site inspection v2")
    assert m.audit_type == "inspection"
    assert m.scoring_method == "percentage"
    assert m.auto_create_findings is True


def test_audit_template_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditTemplateCreate(
            name="Site inspection v2",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
