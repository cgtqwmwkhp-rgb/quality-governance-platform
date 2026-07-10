"""Unit tests for Twilio / SMS readiness helper."""

from src.infrastructure.sms.sms_status import get_sms_readiness


def test_sms_not_configured_without_creds(monkeypatch):
    monkeypatch.delenv("SMS_ENABLED", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_FROM_NUMBER", raising=False)

    result = get_sms_readiness()

    assert result["status"] == "not_configured"
    assert result["sms_configured"] is False
    assert "note" in result


def test_sms_misconfigured_when_enabled_without_twilio(monkeypatch):
    monkeypatch.setenv("SMS_ENABLED", "true")
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)

    result = get_sms_readiness()

    assert result["status"] == "misconfigured"
    assert result["sms_configured"] is False
    assert "TWILIO" in result["note"]


def test_sms_configured_with_twilio_creds(monkeypatch):
    monkeypatch.delenv("SMS_ENABLED", raising=False)
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACxxxxxxxx")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret-token")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+447700900000")

    result = get_sms_readiness()

    assert result["status"] == "configured"
    assert result["sms_configured"] is True
    assert result["twilio_account_sid_present"] is True
    assert result["twilio_auth_token_present"] is True
    assert "secret-token" not in str(result)
    assert "twilio_auth_token" not in result or result.get("twilio_auth_token") is None


def test_sms_disabled_flag(monkeypatch):
    monkeypatch.setenv("SMS_ENABLED", "false")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACxxxxxxxx")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret-token")

    result = get_sms_readiness()

    assert result["status"] == "disabled"
    assert result["sms_enabled"] is False
