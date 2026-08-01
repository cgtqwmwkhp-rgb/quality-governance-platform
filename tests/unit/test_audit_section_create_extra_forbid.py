"""B-10: AuditSectionCreate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.audit import AuditSectionCreate


def test_audit_section_create_accepts_known_fields() -> None:
    m = AuditSectionCreate(title="Site conditions", description="Outdoor compound", sort_order=2)
    assert m.title == "Site conditions"
    assert m.sort_order == 2


def test_audit_section_create_defaults() -> None:
    m = AuditSectionCreate(title="Site conditions")
    assert m.weight == 1.0
    assert m.is_repeatable is False
    assert m.description is None


def test_audit_section_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditSectionCreate(
            title="Site conditions",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
