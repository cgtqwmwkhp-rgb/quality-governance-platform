"""Storage backend selection — staging must use Azure Blob, not local disk."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.infrastructure import storage as storage_mod
from src.infrastructure.storage import StorageNotConfiguredError, get_storage_service


@pytest.fixture(autouse=True)
def _reset_singleton(monkeypatch):
    monkeypatch.setattr(storage_mod, "_storage_service", None)
    yield
    monkeypatch.setattr(storage_mod, "_storage_service", None)


def test_staging_with_connection_string_uses_azure(monkeypatch):
    monkeypatch.setattr(
        storage_mod,
        "settings",
        SimpleNamespace(
            azure_storage_connection_string=(
                "DefaultEndpointsProtocol=https;AccountName=x;AccountKey=y;EndpointSuffix=core.windows.net"
            ),
            azure_storage_container_name="attachments",
            is_production=False,
            is_staging=True,
        ),
    )
    svc = get_storage_service()
    assert svc.__class__.__name__ == "AzureBlobStorageService"


def test_staging_without_connection_string_fails_closed(monkeypatch):
    monkeypatch.setattr(
        storage_mod,
        "settings",
        SimpleNamespace(
            azure_storage_connection_string="",
            azure_storage_container_name="attachments",
            is_production=False,
            is_staging=True,
        ),
    )
    with pytest.raises(StorageNotConfiguredError):
        get_storage_service()


def test_development_without_connection_string_uses_local(monkeypatch):
    monkeypatch.setattr(
        storage_mod,
        "settings",
        SimpleNamespace(
            azure_storage_connection_string="",
            azure_storage_container_name="attachments",
            is_production=False,
            is_staging=False,
        ),
    )
    local = MagicMock(name="LocalFileStorageService")
    monkeypatch.setattr(storage_mod, "LocalFileStorageService", local)
    get_storage_service()
    local.assert_called_once_with()
