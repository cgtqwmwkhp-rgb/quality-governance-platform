"""Unit tests for fail-closed SMS Celery task (WCS-B03)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.sms_service import SMSResult, SMSStatus
from src.infrastructure.tasks.sms_tasks import _mask_phone, send_sms


def test_mask_phone_hides_prefix():
    assert _mask_phone("+447700900123") == "***0123"
    assert _mask_phone("123") == "***"


def test_send_sms_unconfigured_returns_skipped_never_sent():
    mock_service = MagicMock()
    mock_service.enabled = False

    with patch("src.domain.services.sms_service.SMSService", return_value=mock_service):
        result = send_sms.run("+447700900123", "Test message")

    assert result["status"] == "skipped"
    assert result["status"] != "sent"
    assert result["to"] == "***0123"
    assert result["reason"] == "SMS service not configured"
    mock_service.send_sms.assert_not_called()


def test_send_sms_configured_success_returns_sent():
    mock_service = MagicMock()
    mock_service.enabled = True
    mock_service.send_sms = AsyncMock(
        return_value=SMSResult(
            success=True,
            message_sid="SM123",
            status=SMSStatus.SENT,
        )
    )

    with patch("src.domain.services.sms_service.SMSService", return_value=mock_service):
        result = send_sms.run("+447700900123", "Test message")

    assert result == {
        "status": "sent",
        "to": "***0123",
        "message_sid": "SM123",
    }
    mock_service.send_sms.assert_awaited_once_with(to="+447700900123", message="Test message")


def test_send_sms_configured_failure_returns_failed():
    mock_service = MagicMock()
    mock_service.enabled = True
    mock_service.send_sms = AsyncMock(
        return_value=SMSResult(
            success=False,
            status=SMSStatus.FAILED,
            error_message="Twilio 21211",
        )
    )

    with patch("src.domain.services.sms_service.SMSService", return_value=mock_service):
        result = send_sms.run("+447700900123", "Test message")

    assert result["status"] == "failed"
    assert result["to"] == "***0123"
    assert result["error"] == "Twilio 21211"


def test_send_sms_hard_exception_retries():
    mock_service = MagicMock()
    mock_service.enabled = True
    mock_service.send_sms = AsyncMock(side_effect=RuntimeError("provider boom"))

    with (
        patch("src.domain.services.sms_service.SMSService", return_value=mock_service),
        patch.object(send_sms, "retry", side_effect=Exception("retry scheduled")) as mock_retry,
    ):
        with pytest.raises(Exception, match="retry scheduled"):
            send_sms.run("+447700900123", "Test message")

    mock_retry.assert_called_once()
    assert isinstance(mock_retry.call_args.kwargs["exc"], RuntimeError)


@pytest.mark.asyncio
async def test_deliver_sms_logs_success_only_when_result_ok():
    from src.domain.services.notification_service import NotificationService

    db = AsyncMock()
    prefs = SimpleNamespace(phone_number="+447700900123")
    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = prefs
    db.execute = AsyncMock(return_value=db_result)

    service = NotificationService(db=db)
    service.sms_service = MagicMock()
    service.sms_service.send_sms = AsyncMock(
        return_value=SMSResult(success=True, message_sid="SM1", status=SMSStatus.SENT)
    )

    notification = SimpleNamespace(
        user_id=7,
        title="Alert",
        message="Body",
    )

    with patch("src.domain.services.notification_service.logger") as mock_logger:
        await service._deliver_sms(notification)
        mock_logger.info.assert_called()
        mock_logger.warning.assert_not_called()


@pytest.mark.asyncio
async def test_deliver_sms_failure_does_not_log_sent():
    from src.domain.services.notification_service import NotificationService

    db = AsyncMock()
    prefs = SimpleNamespace(phone_number="+447700900123")
    db_result = MagicMock()
    db_result.scalar_one_or_none.return_value = prefs
    db.execute = AsyncMock(return_value=db_result)

    service = NotificationService(db=db)
    service.sms_service = MagicMock()
    service.sms_service.send_sms = AsyncMock(
        return_value=SMSResult(
            success=False,
            status=SMSStatus.FAILED,
            error_message="SMS service not configured",
        )
    )

    notification = SimpleNamespace(
        user_id=7,
        title="Alert",
        message="Body",
    )

    with patch("src.domain.services.notification_service.logger") as mock_logger:
        with pytest.raises(RuntimeError, match="SMS delivery failed"):
            await service._deliver_sms(notification)
        mock_logger.warning.assert_called()
        for call in mock_logger.info.call_args_list:
            assert "SMS sent" not in str(call)
