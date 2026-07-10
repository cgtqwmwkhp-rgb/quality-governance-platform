"""Unit tests for workflow webhook Celery delivery (httpx + retries)."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.infrastructure.tasks.webhook_tasks import (
    WebhookClientError,
    WebhookServerError,
    _build_payload,
    _deliver_webhook,
    deliver_webhook,
)


def test_build_payload_merges_entity_and_config():
    payload = _build_payload(
        entity_type="incident",
        entity_id=42,
        body={"event": "escalated"},
        payload={"severity": "high"},
    )
    assert payload == {
        "entity_type": "incident",
        "entity_id": 42,
        "event": "escalated",
        "severity": "high",
    }


def test_deliver_webhook_success():
    response = MagicMock()
    response.status_code = 202
    response.text = "accepted"

    with patch("src.infrastructure.tasks.webhook_tasks.httpx.Client") as mock_client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.request.return_value = response
        mock_client_cls.return_value = client

        result = _deliver_webhook(
            url="https://hooks.example.com/qgp",
            method="post",
            headers={"Content-Type": "application/json"},
            json_body={"entity_type": "incident", "entity_id": 1},
            timeout=10.0,
        )

    client.request.assert_called_once()
    assert result["status"] == "delivered"
    assert result["status_code"] == 202
    assert result["method"] == "POST"


def test_deliver_webhook_4xx_is_client_error():
    response = MagicMock()
    response.status_code = 404
    response.text = "not found"

    with patch("src.infrastructure.tasks.webhook_tasks.httpx.Client") as mock_client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.request.return_value = response
        mock_client_cls.return_value = client

        with pytest.raises(WebhookClientError, match="404"):
            _deliver_webhook(
                url="https://hooks.example.com/missing",
                method="POST",
                headers={},
                json_body={"entity_id": 1},
                timeout=5.0,
            )


def test_deliver_webhook_5xx_is_server_error():
    response = MagicMock()
    response.status_code = 503
    response.text = "unavailable"

    with patch("src.infrastructure.tasks.webhook_tasks.httpx.Client") as mock_client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.request.return_value = response
        mock_client_cls.return_value = client

        with pytest.raises(WebhookServerError, match="503"):
            _deliver_webhook(
                url="https://hooks.example.com/down",
                method="POST",
                headers={},
                json_body={"entity_id": 1},
                timeout=5.0,
            )


def test_deliver_webhook_network_error_is_server_error():
    with patch("src.infrastructure.tasks.webhook_tasks.httpx.Client") as mock_client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.request.side_effect = httpx.ConnectError("connection refused")
        mock_client_cls.return_value = client

        with pytest.raises(WebhookServerError, match="network"):
            _deliver_webhook(
                url="https://hooks.example.com/down",
                method="POST",
                headers={},
                json_body={"entity_id": 1},
                timeout=5.0,
            )


def test_celery_task_returns_structured_failure_on_4xx():
    response = MagicMock()
    response.status_code = 400
    response.text = "bad request"

    with patch("src.infrastructure.tasks.webhook_tasks.httpx.Client") as mock_client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.request.return_value = response
        mock_client_cls.return_value = client

        result = deliver_webhook.run(
            url="https://hooks.example.com/bad",
            method="POST",
            headers={"X-Api-Key": "k"},
            entity_type="incident",
            entity_id=9,
            body={"hello": "world"},
            timeout=12,
        )

    assert result["status"] == "failed"
    assert result["retryable"] is False
    assert result["entity_type"] == "incident"
    assert result["entity_id"] == 9
    assert "400" in result["error"]


def test_celery_task_success_includes_entity_context():
    response = MagicMock()
    response.status_code = 200
    response.text = "ok"

    with patch("src.infrastructure.tasks.webhook_tasks.httpx.Client") as mock_client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.request.return_value = response
        mock_client_cls.return_value = client

        result = deliver_webhook.run(
            url="https://hooks.example.com/ok",
            entity_type="complaint",
            entity_id=3,
            payload={"source": "workflow"},
        )

    assert result["status"] == "delivered"
    assert result["entity_type"] == "complaint"
    assert result["entity_id"] == 3
    called_kwargs = client.request.call_args.kwargs
    assert called_kwargs["json"]["entity_type"] == "complaint"
    assert called_kwargs["json"]["entity_id"] == 3
    assert called_kwargs["json"]["source"] == "workflow"
