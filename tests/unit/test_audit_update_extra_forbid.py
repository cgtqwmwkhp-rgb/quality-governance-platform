"""B-10: AuditUpdate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.uvdb import AuditUpdate


def test_audit_update_accepts_known_fields() -> None:
    m = AuditUpdate(status="completed", total_score=92.5, lead_auditor="Jane Doe")
    assert m.status == "completed"
    assert m.total_score == 92.5


def test_audit_update_all_optional() -> None:
    m = AuditUpdate()
    assert m.status is None
    assert m.audit_notes is None


def test_audit_update_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditUpdate(
            status="completed",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
