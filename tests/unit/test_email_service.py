"""Unit tests for async EmailService (WCS-B04)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tenacity import wait_none

from src.domain.services.email_service import EmailSendResult, EmailService


@pytest.fixture
def email_svc(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "smtp-user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    return EmailService()


@pytest.fixture
def disabled_email_svc(monkeypatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    return EmailService()


def _mock_smtp_context(send_message=None, side_effect=None):
    smtp = AsyncMock()
    if side_effect is not None:
        smtp.send_message = AsyncMock(side_effect=side_effect)
    else:
        smtp.send_message = AsyncMock(return_value=send_message or ({}, "ok"))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=smtp)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm, smtp


class TestEmailSendResult:
    def test_frozen_dataclass(self):
        result = EmailSendResult(success=True, status="sent")
        assert result.success is True
        assert result.status == "sent"
        assert result.error_message is None
        with pytest.raises(Exception):
            result.success = False  # type: ignore[misc]


class TestSendEmailDisabled:
    @pytest.mark.asyncio
    async def test_disabled_returns_skipped(self, disabled_email_svc):
        result = await disabled_email_svc.send_email(
            to=["user@example.com"],
            subject="Test",
            html_content="<p>hi</p>",
        )
        assert isinstance(result, EmailSendResult)
        assert result.success is False
        assert result.status == "skipped"
        assert result.error_message == "Email service not configured"


class TestSendEmailSuccess:
    @pytest.mark.asyncio
    async def test_success_with_mocked_aiosmtplib(self, email_svc):
        cm, smtp = _mock_smtp_context()
        with patch("src.domain.services.email_service.aiosmtplib.SMTP", return_value=cm) as smtp_cls:
            result = await email_svc.send_email(
                to=["user@example.com"],
                subject="Hello",
                html_content="<p>body</p>",
                cc=["cc@example.com"],
                bcc=["bcc@example.com"],
            )

        assert result == EmailSendResult(success=True, status="sent")
        smtp_cls.assert_called_once_with(
            hostname="smtp.example.com",
            port=587,
            username="smtp-user@example.com",
            password="secret",
            start_tls=True,
            use_tls=False,
        )
        smtp.send_message.assert_awaited_once()
        _msg, kwargs = smtp.send_message.await_args
        assert kwargs["recipients"] == [
            "user@example.com",
            "cc@example.com",
            "bcc@example.com",
        ]


class TestSendEmailRetries:
    @pytest.mark.asyncio
    async def test_smtp_error_raises_and_retries(self, email_svc):
        email_svc.send_email.retry.wait = wait_none()
        cm, smtp = _mock_smtp_context(side_effect=OSError("connection refused"))

        with patch("src.domain.services.email_service.aiosmtplib.SMTP", return_value=cm):
            with pytest.raises(OSError, match="connection refused"):
                await email_svc.send_email(
                    to=["user@example.com"],
                    subject="Fail",
                    html_content="<p>x</p>",
                )

        assert smtp.send_message.await_count == 3

    @pytest.mark.asyncio
    async def test_smtp_recovers_after_transient_failure(self, email_svc):
        email_svc.send_email.retry.wait = wait_none()
        cm, smtp = _mock_smtp_context(
            side_effect=[OSError("temp"), ({}, "ok")],
        )

        with patch("src.domain.services.email_service.aiosmtplib.SMTP", return_value=cm):
            result = await email_svc.send_email(
                to=["user@example.com"],
                subject="Retry ok",
                html_content="<p>x</p>",
            )

        assert result.status == "sent"
        assert smtp.send_message.await_count == 2


class TestWrapperBoolCompatibility:
    @pytest.mark.asyncio
    async def test_password_reset_returns_bool_on_success(self, email_svc):
        with patch.object(
            email_svc,
            "send_email",
            new=AsyncMock(return_value=EmailSendResult(success=True, status="sent")),
        ):
            ok = await email_svc.send_password_reset_email(
                to="user@example.com",
                reset_url="https://app.example/reset?token=abc",
                user_name="Ada",
            )
        assert ok is True

    @pytest.mark.asyncio
    async def test_password_reset_returns_false_on_exception(self, email_svc):
        with patch.object(
            email_svc,
            "send_email",
            new=AsyncMock(side_effect=OSError("smtp down")),
        ):
            ok = await email_svc.send_password_reset_email(
                to="user@example.com",
                reset_url="https://app.example/reset?token=abc",
            )
        assert ok is False

    @pytest.mark.asyncio
    async def test_incident_notification_returns_bool(self, email_svc):
        with patch.object(
            email_svc,
            "send_email",
            new=AsyncMock(return_value=EmailSendResult(success=True, status="sent")),
        ):
            ok = await email_svc.send_incident_notification(
                to=["ops@example.com"],
                incident_id="INC-1",
                title="Spill",
                severity="high",
                description="Oil spill",
            )
        assert ok is True
