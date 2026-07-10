"""Unit tests for SMTP / email readiness helper."""

from src.infrastructure.email.email_status import get_email_readiness


def test_email_not_configured_when_disabled_and_no_creds(monkeypatch):
    monkeypatch.delenv("EMAIL_ENABLED", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    result = get_email_readiness()

    assert result["status"] == "not_configured"
    assert result["email_enabled"] is False
    assert result["email_configured"] is False
    assert "note" in result


def test_email_misconfigured_when_enabled_without_smtp(monkeypatch):
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    result = get_email_readiness()

    assert result["status"] == "misconfigured"
    assert result["email_enabled"] is True
    assert result["email_configured"] is False
    assert "SMTP_USER" in result["note"]


def test_email_configured_when_enabled_with_smtp(monkeypatch):
    monkeypatch.setenv("EMAIL_ENABLED", "1")
    monkeypatch.setenv("SMTP_USER", "noreply@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("FROM_EMAIL", "noreply@example.com")

    result = get_email_readiness()

    assert result["status"] == "configured"
    assert result["email_enabled"] is True
    assert result["email_configured"] is True
    assert result["smtp_user_present"] is True
    assert result["smtp_password_present"] is True
    # Never leak secrets
    assert "secret" not in str(result)
    assert "smtp_password" not in result


def test_email_credentials_present_without_enabled_flag(monkeypatch):
    monkeypatch.delenv("EMAIL_ENABLED", raising=False)
    monkeypatch.setenv("SMTP_USER", "noreply@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")

    result = get_email_readiness()

    assert result["status"] == "credentials_present"
    assert result["email_configured"] is True
    assert result["email_enabled"] is False
