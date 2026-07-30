"""B-10: AllocationRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.vehicles import AllocationRequest


def test_allocation_request_accepts_known_fields() -> None:
    m = AllocationRequest(vehicle_reg="AB12CDE", driver_profile_id=7, force=True)
    assert m.vehicle_reg == "AB12CDE"
    assert m.driver_profile_id == 7
    assert m.force is True


def test_allocation_request_force_defaults_false() -> None:
    m = AllocationRequest(vehicle_reg="AB12CDE", driver_profile_id=7)
    assert m.force is False


def test_allocation_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AllocationRequest(
            vehicle_reg="AB12CDE",
            driver_profile_id=7,
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
