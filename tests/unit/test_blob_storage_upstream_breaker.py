"""Path-to-10 Preferred S10: Azure Blob I/O via catalog ``blob_storage`` breaker."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.domain.services.upstream_circuit_breaker import get_upstream_breaker
from src.infrastructure.resilience.circuit_breaker import (
    CircuitBreakerOpenError,
    CircuitState,
    _circuit_registry,
    _registry_lock,
)
from src.infrastructure.storage import AzureBlobStorageService, StorageError


@pytest.fixture(autouse=True)
def _clean_registry():
    with _registry_lock:
        saved = dict(_circuit_registry)
        _circuit_registry.clear()
    yield
    with _registry_lock:
        _circuit_registry.clear()
        _circuit_registry.update(saved)


def _service() -> AzureBlobStorageService:
    return AzureBlobStorageService(
        connection_string="DefaultEndpointsProtocol=https;AccountName=demo;AccountKey=dGVzdA==",
        container_name="attachments",
    )


@pytest.mark.asyncio
async def test_upload_registers_preferred_blob_breaker_on_success() -> None:
    svc = _service()
    blob_client = MagicMock()
    container_client = MagicMock()
    container_client.exists.return_value = True

    with (
        patch.object(svc, "_get_container_client", return_value=container_client),
        patch.object(svc, "_get_blob_client", return_value=blob_client),
    ):
        key = await svc.upload("a/b.txt", b"hello", "text/plain")

    assert key == "a/b.txt"
    blob_client.upload_blob.assert_called_once()
    health = get_upstream_breaker("blob_storage").get_health()
    assert health["name"] == "blob_storage"
    assert health["state"] == CircuitState.CLOSED.value


@pytest.mark.asyncio
async def test_repeated_upload_failures_open_blob_circuit() -> None:
    svc = _service()
    container_client = MagicMock()
    container_client.exists.return_value = True
    blob_client = MagicMock()
    blob_client.upload_blob.side_effect = RuntimeError("azure unavailable")

    with (
        patch.object(svc, "_get_container_client", return_value=container_client),
        patch.object(svc, "_get_blob_client", return_value=blob_client),
    ):
        for _ in range(5):
            with pytest.raises(StorageError):
                await svc.upload("fail.bin", b"x", "application/octet-stream")

        with pytest.raises(CircuitBreakerOpenError) as exc:
            await svc.upload("fail.bin", b"x", "application/octet-stream")

    assert exc.value.circuit_name == "blob_storage"
    assert get_upstream_breaker("blob_storage").state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_download_rejected_when_blob_circuit_open() -> None:
    cb = get_upstream_breaker("blob_storage")
    # Force OPEN without waiting for natural trip window.
    cb._state = CircuitState.OPEN
    cb._last_failure_time = 1e18  # keep OPEN (monotonic - last < recovery)

    svc = _service()
    with pytest.raises(CircuitBreakerOpenError) as exc:
        await svc.download("any.key")
    assert exc.value.circuit_name == "blob_storage"
