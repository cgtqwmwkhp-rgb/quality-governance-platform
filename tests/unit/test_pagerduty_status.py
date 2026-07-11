"""Unit tests for PagerDuty readiness honesty helpers."""

import os

from src.infrastructure.alerting.pagerduty_status import get_pagerduty_readiness


def test_pagerduty_not_configured_by_default(monkeypatch):
    monkeypatch.delenv("PAGERDUTY_ENABLED", raising=False)
    monkeypatch.delenv("PAGERDUTY_ROUTING_KEY", raising=False)
    monkeypatch.delenv("PAGERDUTY_EVENTS_API_URL", raising=False)
    result = get_pagerduty_readiness()
    assert result["status"] == "not_configured"
    assert result["pagerduty_configured"] is False
    assert result["routing_key_present"] is False
    assert "note" in result


def test_pagerduty_misconfigured_when_enabled_without_key(monkeypatch):
    monkeypatch.setenv("PAGERDUTY_ENABLED", "true")
    monkeypatch.delenv("PAGERDUTY_ROUTING_KEY", raising=False)
    result = get_pagerduty_readiness()
    assert result["status"] == "misconfigured"
    assert result["pagerduty_enabled"] is True
    assert result["routing_key_present"] is False


def test_pagerduty_credentials_present_without_enabled(monkeypatch):
    monkeypatch.delenv("PAGERDUTY_ENABLED", raising=False)
    monkeypatch.setenv("PAGERDUTY_ROUTING_KEY", "rk-test")
    result = get_pagerduty_readiness()
    assert result["status"] == "credentials_present"
    assert result["pagerduty_configured"] is True


def test_pagerduty_configured(monkeypatch):
    monkeypatch.setenv("PAGERDUTY_ENABLED", "true")
    monkeypatch.setenv("PAGERDUTY_ROUTING_KEY", "rk-test")
    monkeypatch.setenv("PAGERDUTY_EVENTS_API_URL", "https://events.pagerduty.com/v2/enqueue")
    result = get_pagerduty_readiness()
    assert result["status"] == "configured"
    assert result["events_api_url_set"] is True
    assert "note" not in result
    # Never leak secrets
    assert "rk-test" not in str(result)
    assert os.getenv("PAGERDUTY_ROUTING_KEY") == "rk-test"
