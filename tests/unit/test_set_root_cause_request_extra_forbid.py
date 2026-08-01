"""B-10: SetRootCauseRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.rca_tools import SetRootCauseRequest


def test_set_root_cause_request_accepts_known_fields() -> None:
    m = SetRootCauseRequest(
        primary_root_cause="Inadequate training on lockout procedure",
        contributing_factors=["Missing refresher", "No competency gate"],
    )
    assert m.primary_root_cause == "Inadequate training on lockout procedure"
    assert m.contributing_factors == ["Missing refresher", "No competency gate"]


def test_set_root_cause_request_contributing_optional() -> None:
    m = SetRootCauseRequest(primary_root_cause="Procedure not followed")
    assert m.contributing_factors is None


def test_set_root_cause_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SetRootCauseRequest(
            primary_root_cause="Procedure not followed",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
