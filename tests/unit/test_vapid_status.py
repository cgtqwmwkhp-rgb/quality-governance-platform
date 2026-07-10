"""Unit tests for VAPID / Web Push readiness helper (WCS-B06)."""

from src.infrastructure.push.vapid_status import get_vapid_readiness


def test_vapid_not_configured_when_keys_missing(monkeypatch):
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("VAPID_EMAIL", raising=False)

    result = get_vapid_readiness()

    assert result["status"] == "not_configured"
    assert result["public_key_present"] is False
    assert result["private_key_present"] is False
    assert result["public_key"] is None
    assert "note" in result


def test_vapid_partial_when_only_public_present(monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "BPublicKeyExample")
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)

    result = get_vapid_readiness()

    assert result["status"] == "partial"
    assert result["public_key_present"] is True
    assert result["private_key_present"] is False
    assert result["public_key"] == "BPublicKeyExample"


def test_vapid_configured_when_both_keys_present(monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "BPublicKeyExample")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private-key-material")
    monkeypatch.setenv("VAPID_EMAIL", "ops@example.com")

    result = get_vapid_readiness()

    assert result["status"] == "configured"
    assert result["public_key_present"] is True
    assert result["private_key_present"] is True
    assert result["contact_email_configured"] is True
    assert result["public_key"] == "BPublicKeyExample"
    # Never leak the private key
    assert "private_key" not in result or result.get("private_key") is None
    assert "private-key-material" not in str(result)
