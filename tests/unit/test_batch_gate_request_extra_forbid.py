"""B-10: BatchGateRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.vehicles import BatchGateRequest


def test_batch_gate_request_accepts_known_fields() -> None:
    m = BatchGateRequest(vehicle_regs=["AB12CDE", "XY99ZZZ"])
    assert m.vehicle_regs == ["AB12CDE", "XY99ZZZ"]


def test_batch_gate_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        BatchGateRequest(
            vehicle_regs=["AB12CDE"],
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
