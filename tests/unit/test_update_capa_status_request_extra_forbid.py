"""B-10: UpdateCAPAStatusRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.rca_tools import UpdateCAPAStatusRequest


def test_update_capa_status_request_accepts_known_fields() -> None:
    m = UpdateCAPAStatusRequest(status="in_progress", notes="Started remediation")
    assert m.status == "in_progress"
    assert m.notes == "Started remediation"


def test_update_capa_status_request_notes_optional() -> None:
    m = UpdateCAPAStatusRequest(status="completed")
    assert m.notes is None


def test_update_capa_status_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        UpdateCAPAStatusRequest(
            status="completed",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
