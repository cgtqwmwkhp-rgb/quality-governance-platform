"""B-10: AuditRunCreate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.audit import AuditRunCreate


def test_audit_run_create_accepts_known_fields() -> None:
    m = AuditRunCreate(template_id=3, title="Site inspection", location="Depot A")
    assert m.template_id == 3
    assert m.title == "Site inspection"


def test_audit_run_create_defaults() -> None:
    m = AuditRunCreate(template_id=3)
    assert m.assigned_to_id is None
    assert m.external_audit_type is None


def test_audit_run_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditRunCreate(
            template_id=3,
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
