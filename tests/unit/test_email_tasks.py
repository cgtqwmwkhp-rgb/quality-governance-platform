"""Unit tests for Celery email_tasks mapping (WCS-B04)."""

from unittest.mock import MagicMock, patch

from src.domain.services.email_service import EmailSendResult
from src.infrastructure.tasks import email_tasks


def test_send_email_task_maps_structured_result():
    mock_service = MagicMock()
    mock_service.enabled = True

    with patch("src.domain.services.email_service.email_service", mock_service):
        with patch.object(
            email_tasks,
            "_run_async",
            return_value=EmailSendResult(success=True, status="sent"),
        ):
            result = email_tasks.send_email.run(
                "user@example.com",
                "Hello",
                "<p>body</p>",
                True,
            )

    assert result["status"] == "sent"
    assert result["to"] == "use***"
    assert result["subject"] == "Hello"
    assert "error" not in result


def test_send_email_task_includes_error_message():
    mock_service = MagicMock()
    mock_service.enabled = True

    with patch("src.domain.services.email_service.email_service", mock_service):
        with patch.object(
            email_tasks,
            "_run_async",
            return_value=EmailSendResult(
                success=False,
                status="skipped",
                error_message="Email service not configured",
            ),
        ):
            result = email_tasks.send_email.run(
                "ab@example.com",
                "Subj",
                "body",
                False,
            )

    assert result["status"] == "skipped"
    assert result["error"] == "Email service not configured"


def test_send_email_task_skipped_when_disabled():
    mock_service = MagicMock()
    mock_service.enabled = False

    with patch("src.domain.services.email_service.email_service", mock_service):
        result = email_tasks.send_email.run("user@example.com", "S", "b", False)

    assert result == {"status": "skipped", "to": "use***", "subject": "S"}
