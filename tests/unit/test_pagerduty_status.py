"""Unit tests for PagerDuty readiness honesty + Events API v2 enqueue."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.alerting.pagerduty_client import (
    PagerDutySendError,
    enqueue_event,
    reset_last_enqueue_status,
    should_fail_readiness,
)
from src.infrastructure.alerting.pagerduty_status import get_pagerduty_readiness


@pytest.fixture(autouse=True)
def _reset_pagerduty_state(monkeypatch):
    reset_last_enqueue_status()
    monkeypatch.delenv("PAGERDUTY_ENABLED", raising=False)
    monkeypatch.delenv("PAGERDUTY_ROUTING_KEY", raising=False)
    monkeypatch.delenv("PAGERDUTY_EVENTS_API_URL", raising=False)
    yield
    reset_last_enqueue_status()


def test_pagerduty_not_configured_by_default():
    result = get_pagerduty_readiness()
    assert result["status"] == "not_configured"
    assert result["pagerduty_configured"] is False
    assert result["routing_key_present"] is False
    assert result["fail_closed"] is False
    assert "note" in result


def test_pagerduty_misconfigured_when_enabled_without_key(monkeypatch):
    monkeypatch.setenv("PAGERDUTY_ENABLED", "true")
    result = get_pagerduty_readiness()
    assert result["status"] == "misconfigured"
    assert result["pagerduty_enabled"] is True
    assert result["routing_key_present"] is False
    assert result["fail_closed"] is False


def test_pagerduty_credentials_present_without_enabled(monkeypatch):
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


def test_enqueue_without_key_returns_not_configured():
    result = enqueue_event(summary="test alert")
    assert result["status"] == "not_configured"
    assert should_fail_readiness() is False


def test_enqueue_with_key_success(monkeypatch):
    monkeypatch.setenv("PAGERDUTY_ROUTING_KEY", "rk-test")
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.text = '{"status":"success","dedup_key":"d1"}'
    mock_response.json.return_value = {"status": "success", "dedup_key": "d1"}

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = enqueue_event(summary="disk full", severity="critical", dedup_key="d1")

    assert result["status"] == "enqueued"
    assert result["http_status"] == 202
    assert result["dedup_key"] == "d1"
    assert should_fail_readiness() is False
    readiness = get_pagerduty_readiness()
    assert readiness["status"] == "credentials_present"
    assert readiness["last_enqueue_status"] == "enqueued"


def test_enqueue_with_key_http_failure_fail_closed(monkeypatch):
    monkeypatch.setenv("PAGERDUTY_ROUTING_KEY", "rk-test")
    monkeypatch.setenv("PAGERDUTY_ENABLED", "true")
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "bad routing key"

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        with pytest.raises(PagerDutySendError):
            enqueue_event(summary="should fail")

    assert should_fail_readiness() is True
    readiness = get_pagerduty_readiness()
    assert readiness["status"] == "send_failed"
    assert readiness["fail_closed"] is True
    assert "rk-test" not in str(readiness)


def test_enqueue_network_error_fail_closed(monkeypatch):
    import httpx

    monkeypatch.setenv("PAGERDUTY_ROUTING_KEY", "rk-live")

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.post.side_effect = httpx.ConnectError("connection refused")
        mock_client_cls.return_value = mock_client

        with pytest.raises(PagerDutySendError):
            enqueue_event(summary="network fail")

    assert should_fail_readiness() is True
