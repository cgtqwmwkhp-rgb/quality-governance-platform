"""Unit tests for PagerDuty Celery alert task."""

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.alerting.pagerduty_client import PagerDutySendError, reset_last_enqueue_status


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    reset_last_enqueue_status()
    monkeypatch.delenv("PAGERDUTY_ENABLED", raising=False)
    monkeypatch.delenv("PAGERDUTY_ROUTING_KEY", raising=False)
    yield
    reset_last_enqueue_status()


def test_trigger_skipped_when_not_enabled(monkeypatch):
    from src.infrastructure.tasks.pagerduty_tasks import trigger_pagerduty_alert

    result = trigger_pagerduty_alert.run(summary="x")
    assert result["status"] == "skipped"


def test_trigger_not_configured_when_enabled_without_key(monkeypatch):
    monkeypatch.setenv("PAGERDUTY_ENABLED", "true")
    from src.infrastructure.tasks.pagerduty_tasks import trigger_pagerduty_alert

    result = trigger_pagerduty_alert.run(summary="dlq critical")
    assert result["status"] == "not_configured"


def test_trigger_enqueues_when_configured(monkeypatch):
    monkeypatch.setenv("PAGERDUTY_ENABLED", "true")
    monkeypatch.setenv("PAGERDUTY_ROUTING_KEY", "rk-test")

    with patch(
        "src.infrastructure.alerting.pagerduty_client.enqueue_event",
        return_value={"status": "enqueued", "http_status": 202},
    ) as mock_enqueue:
        from src.infrastructure.tasks.pagerduty_tasks import trigger_pagerduty_alert

        result = trigger_pagerduty_alert.run(
            summary="DLQ critical",
            severity="critical",
            dedup_key="qgp-dlq-depth-critical",
        )

    assert result["status"] == "enqueued"
    mock_enqueue.assert_called_once()


def test_trigger_retries_on_send_error(monkeypatch):
    monkeypatch.setenv("PAGERDUTY_ENABLED", "true")
    monkeypatch.setenv("PAGERDUTY_ROUTING_KEY", "rk-test")

    with patch(
        "src.infrastructure.alerting.pagerduty_client.enqueue_event",
        side_effect=PagerDutySendError("boom"),
    ):
        from src.infrastructure.tasks.pagerduty_tasks import trigger_pagerduty_alert

        with pytest.raises(Exception):
            # Celery retry raises Retry or the original depending on eager mode
            trigger_pagerduty_alert.run(summary="fail")
