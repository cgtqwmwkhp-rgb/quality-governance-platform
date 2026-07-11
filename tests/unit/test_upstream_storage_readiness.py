"""Path-to-10 S10: Azure Blob upstream readiness honesty."""

from src.infrastructure.upstream.storage_status import get_upstream_storage_readiness


def test_upstream_storage_not_configured_when_connection_missing(monkeypatch):
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("AZURE_STORAGE_CONTAINER_NAME", raising=False)
    result = get_upstream_storage_readiness()
    assert result["status"] == "not_configured"
    assert result["connection_string_present"] is False
    assert result["role"] == "blob"
    assert "note" in result
    assert "connection_string" not in result
    assert "AccountKey" not in str(result)
    # Preferred S10 honesty: circuit metadata + skipped ping; never invent secrets
    assert result["circuits"]["blob_storage"]["state"] == "unregistered"
    assert result["ping"]["connectivity"] == "unprobed"
    assert "password" not in str(result).lower()
    assert "smtp" not in str(result).lower()


def test_upstream_storage_partial_when_container_explicitly_empty(monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=demo")
    monkeypatch.setenv("AZURE_STORAGE_CONTAINER_NAME", "   ")
    result = get_upstream_storage_readiness()
    assert result["status"] == "partial"
    assert result["connection_string_present"] is True
    assert result["container_name_present"] is False
    assert "note" in result


def test_upstream_storage_configured_with_default_container(monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=demo")
    monkeypatch.delenv("AZURE_STORAGE_CONTAINER_NAME", raising=False)
    result = get_upstream_storage_readiness()
    assert result["status"] == "configured"
    assert result["container_name"] == "attachments"
    assert result["connection_string_present"] is True
