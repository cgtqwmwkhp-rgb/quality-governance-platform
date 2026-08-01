"""B-10: AuditRunUpdate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.audit import AuditRunUpdate


def test_audit_run_update_accepts_known_fields() -> None:
    m = AuditRunUpdate(title="Updated run", location="Depot B", status="in_progress")
    assert m.title == "Updated run"
    assert m.location == "Depot B"


def test_audit_run_update_all_optional() -> None:
    m = AuditRunUpdate()
    assert m.title is None
    assert m.status is None


def test_audit_run_update_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditRunUpdate(
            title="Updated run",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
