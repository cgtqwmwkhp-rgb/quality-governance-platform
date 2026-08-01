"""B-10: AuditResponseUpdate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.audit import AuditResponseUpdate


def test_audit_response_update_accepts_known_fields() -> None:
    m = AuditResponseUpdate(response_value="no", notes="Corrected on review", is_na=False)
    assert m.response_value == "no"
    assert m.notes == "Corrected on review"


def test_audit_response_update_all_optional() -> None:
    m = AuditResponseUpdate()
    assert m.response_value is None
    assert m.notes is None


def test_audit_response_update_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AuditResponseUpdate(
            response_value="yes",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
