"""B-10: AuditCreate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.uvdb import AuditCreate


def test_audit_create_accepts_known_fields() -> None:
    m = AuditCreate(
        company_name="Acme Contracting Ltd",
        company_id="C-100",
        audit_type="B2",
        audit_scope="Site verification",
        lead_auditor="Jane Doe",
    )
    assert m.company_name == "Acme Contracting Ltd"
    assert m.audit_type == "B2"


def test_audit_create_defaults() -> None:
    m = AuditCreate(company_name="Acme Contracting Ltd")
    assert m.audit_type == "B2"
    assert m.company_id is None
    assert m.lead_auditor is None


def test_audit_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditCreate(
            company_name="Acme Contracting Ltd",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
