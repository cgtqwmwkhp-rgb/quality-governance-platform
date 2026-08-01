"""B-10: AuditFindingUpdate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.audit import AuditFindingUpdate


def test_audit_finding_update_accepts_known_fields() -> None:
    m = AuditFindingUpdate(title="Updated title", severity="low", status="open")
    assert m.title == "Updated title"
    assert m.severity == "low"


def test_audit_finding_update_all_optional() -> None:
    m = AuditFindingUpdate()
    assert m.title is None
    assert m.description is None


def test_audit_finding_update_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditFindingUpdate(
            title="Updated title",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
