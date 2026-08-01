"""B-10: SetFishboneRootCauseRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.rca_tools import SetFishboneRootCauseRequest


def test_set_fishbone_root_cause_request_accepts_known_fields() -> None:
    m = SetFishboneRootCauseRequest(
        root_cause="Inadequate training on lockout procedure",
        root_cause_category="manpower",
        primary_causes=["Missed refresher"],
    )
    assert m.root_cause == "Inadequate training on lockout procedure"
    assert m.root_cause_category == "manpower"
    assert m.primary_causes == ["Missed refresher"]


def test_set_fishbone_root_cause_request_primary_optional() -> None:
    m = SetFishboneRootCauseRequest(
        root_cause="Procedure not followed",
        root_cause_category="method",
    )
    assert m.primary_causes is None


def test_set_fishbone_root_cause_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SetFishboneRootCauseRequest(
            root_cause="Procedure not followed",
            root_cause_category="method",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
