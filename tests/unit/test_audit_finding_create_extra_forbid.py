"""B-10: AuditFindingCreate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.audit import AuditFindingCreate


def test_audit_finding_create_accepts_known_fields() -> None:
    m = AuditFindingCreate(
        title="Missing induction records",
        description="Site induction evidence was not available for review.",
        severity="high",
        finding_type="nonconformity",
        question_id=42,
        corrective_action_required=True,
    )
    assert m.title == "Missing induction records"
    assert m.question_id == 42


def test_audit_finding_create_defaults() -> None:
    m = AuditFindingCreate(
        title="Observation note",
        description="Housekeeping below expected standard in compound.",
    )
    assert m.severity == "medium"
    assert m.finding_type == "nonconformity"
    assert m.corrective_action_required is True
    assert m.question_id is None


def test_audit_finding_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditFindingCreate(
            title="Missing induction records",
            description="Site induction evidence was not available for review.",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
