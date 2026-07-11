"""Path-to-10 S10: Preferred upstream degraded summary on /readyz honesty."""

from __future__ import annotations

import pytest

from src.domain.services.upstream_circuit_breaker import get_upstream_breaker
from src.infrastructure.resilience.circuit_breaker import _circuit_registry, _registry_lock
from src.infrastructure.upstream.degraded_status import get_upstream_degraded_readiness


@pytest.fixture(autouse=True)
def _clean_registry():
    with _registry_lock:
        saved = dict(_circuit_registry)
        _circuit_registry.clear()
    yield
    with _registry_lock:
        _circuit_registry.clear()
        _circuit_registry.update(saved)


def test_cold_process_not_degraded_and_no_secrets() -> None:
    result = get_upstream_degraded_readiness()
    assert result["status"] == "ok"
    assert result["degraded"] is False
    assert result["open_circuits"] == []
    assert result["half_open_circuits"] == []
    assert result["affects_readiness"] is False
    assert "informational" in result["note"].lower()
    # Honesty: unregistered catalog rows, never invented keys
    assert all(row.get("state") == "unregistered" for row in result["circuits"])
    blob = str(result)
    assert "API_KEY" not in blob
    assert "smtp" not in blob.lower()
    assert "password" not in blob.lower()


@pytest.mark.asyncio
async def test_open_circuit_marks_degraded_without_failing_probe_flag() -> None:
    cb = get_upstream_breaker("blob_storage")
    for _ in range(5):
        with pytest.raises(RuntimeError):
            await cb.call(_fail)

    result = get_upstream_degraded_readiness()
    assert result["status"] == "degraded"
    assert result["degraded"] is True
    assert "blob_storage" in result["open_circuits"]
    assert result["affects_readiness"] is False
    assert "unavailable" in result["message"].lower() or "degraded" in result["message"].lower()


async def _fail() -> None:
    raise RuntimeError("upstream failed")
