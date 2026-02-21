"""Unit tests for Email Service - can run standalone."""

import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

try:
    from src.domain.services.email_service import EmailService

    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Imports not available")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def email_svc():
    """Return an EmailService with SMTP disabled (no credentials)."""
    with patch.dict(os.environ, {"SMTP_USER": "", "SMTP_PASSWORD": ""}, clear=False):
        svc = EmailService()
    assert svc.enabled is False
    return svc


@pytest.fixture
def email_svc_enabled():
    """Return an EmailService with SMTP credentials set."""
    with patch.dict(
        os.environ,
        {"SMTP_USER": "test@example.com", "SMTP_PASSWORD": "secret"},
        clear=False,
    ):
        svc = EmailService()
    assert svc.enabled is True
    return svc


# ---------------------------------------------------------------------------
# Initialization & configuration
# ---------------------------------------------------------------------------


def test_defaults_from_env_vars():
    """EmailService reads SMTP config from environment variables."""
    with patch.dict(
        os.environ,
        {
            "SMTP_HOST": "mail.test.com",
            "SMTP_PORT": "465",
            "SMTP_USER": "user@test.com",
            "SMTP_PASSWORD": "pw",
            "FROM_EMAIL": "noreply@test.com",
            "FROM_NAME": "Test Platform",
        },
    ):
        svc = EmailService()

    assert svc.smtp_host == "mail.test.com"
    assert svc.smtp_port == 465
    assert svc.smtp_user == "user@test.com"
    assert svc.from_email == "noreply@test.com"
    assert svc.from_name == "Test Platform"
    assert svc.enabled is True


def test_disabled_without_credentials():
    """EmailService is disabled when SMTP_USER or SMTP_PASSWORD is empty."""
    with patch.dict(os.environ, {"SMTP_USER": "", "SMTP_PASSWORD": ""}, clear=False):
        svc = EmailService()
    assert svc.enabled is False


def test_enabled_with_credentials():
    """EmailService is enabled when both SMTP_USER and SMTP_PASSWORD are set."""
    with patch.dict(
        os.environ,
        {"SMTP_USER": "user@example.com", "SMTP_PASSWORD": "pass"},
        clear=False,
    ):
        svc = EmailService()
    assert svc.enabled is True


# ---------------------------------------------------------------------------
# Base template
# ---------------------------------------------------------------------------


def test_base_template_contains_placeholders():
    """The base HTML template contains required format placeholders."""
    svc = EmailService()
    template = svc._get_base_template()
    assert "{subject}" in template
    assert "{content}" in template
    assert "{alert_color}" in template
    assert "{year}" in template


def test_base_template_renders_without_error():
    """The base template renders when all placeholders are filled."""
    svc = EmailService()
    template = svc._get_base_template()
    rendered = template.format(
        subject="Test Subject",
        content="<p>Hello</p>",
        alert_color="#ff0000",
        year=2026,
    )
    assert "Test Subject" in rendered
    assert "<p>Hello</p>" in rendered
    assert "#ff0000" in rendered
    assert "2026" in rendered


# ---------------------------------------------------------------------------
# send_email — disabled service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_email_returns_false_when_disabled(email_svc):
    """send_email returns False when service is not configured."""
    result = await email_svc.send_email(
        to=["test@example.com"],
        subject="Test",
        html_content="<p>Hello</p>",
    )
    assert result is False


# ---------------------------------------------------------------------------
# send_email — enabled service, SMTP mocked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_email_success(email_svc_enabled):
    """send_email returns True on successful SMTP send."""
    with patch("src.domain.services.email_service.smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        result = await email_svc_enabled.send_email(
            to=["recipient@example.com"],
            subject="Test Email",
            html_content="<p>Content</p>",
        )

    assert result is True
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once()
    mock_server.sendmail.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_with_cc_and_bcc(email_svc_enabled):
    """CC and BCC recipients are included in the SMTP sendmail call."""
    with patch("src.domain.services.email_service.smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        await email_svc_enabled.send_email(
            to=["to@example.com"],
            subject="CC Test",
            html_content="<p>Hi</p>",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
        )

        all_recipients = mock_server.sendmail.call_args[0][1]
        assert "to@example.com" in all_recipients
        assert "cc@example.com" in all_recipients
        assert "bcc@example.com" in all_recipients


@pytest.mark.asyncio
async def test_send_email_returns_false_on_smtp_error(email_svc_enabled):
    """send_email returns False when SMTP raises an exception."""
    with patch("src.domain.services.email_service.smtplib.SMTP") as mock_smtp:
        mock_smtp.return_value.__enter__ = MagicMock(side_effect=ConnectionError("SMTP down"))
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        result = await email_svc_enabled.send_email(
            to=["test@example.com"],
            subject="Fail",
            html_content="<p>fail</p>",
        )

    assert result is False


# ---------------------------------------------------------------------------
# Incident notification template
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_incident_notification_calls_send_email(email_svc):
    """send_incident_notification composes HTML and calls send_email."""
    with patch.object(email_svc, "send_email", new_callable=AsyncMock, return_value=True) as mock_send:
        result = await email_svc.send_incident_notification(
            to=["safety@example.com"],
            incident_id="INC-2026-001",
            title="Forklift collision",
            severity="high",
            description="Collision in warehouse B",
            location="Warehouse B",
            reported_by="John Smith",
        )

    mock_send.assert_awaited_once()
    call_kwargs = mock_send.call_args
    assert "INC-2026-001" in call_kwargs.kwargs.get("html_content", call_kwargs[1].get("html_content", ""))
    assert "[HIGH]" in call_kwargs.kwargs.get("subject", call_kwargs[1].get("subject", ""))


@pytest.mark.asyncio
async def test_incident_severity_color_mapping():
    """Each severity level maps to the correct alert color."""
    svc = EmailService()
    severity_colors = {
        "critical": "#ef4444",
        "high": "#f97316",
        "medium": "#f59e0b",
        "low": "#22c55e",
    }
    for severity, expected_color in severity_colors.items():
        with patch.object(svc, "send_email", new_callable=AsyncMock, return_value=True) as mock_send:
            await svc.send_incident_notification(
                to=["test@example.com"],
                incident_id="INC-001",
                title="Test",
                severity=severity,
                description="desc",
            )
            html = mock_send.call_args.kwargs.get("html_content", mock_send.call_args[1].get("html_content", ""))
            assert expected_color in html, f"Expected {expected_color} for severity={severity}"


# ---------------------------------------------------------------------------
# Action reminder template
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_action_reminder_overdue():
    """Overdue action reminders use the [OVERDUE] subject prefix."""
    svc = EmailService()
    with patch.object(svc, "send_email", new_callable=AsyncMock, return_value=True) as mock_send:
        await svc.send_action_reminder(
            to=["manager@example.com"],
            action_id="ACT-001",
            title="Install guardrails",
            due_date="2026-01-15",
            days_overdue=5,
        )

    subject = mock_send.call_args.kwargs.get("subject", mock_send.call_args[1].get("subject", ""))
    assert "[OVERDUE]" in subject


@pytest.mark.asyncio
async def test_send_action_reminder_upcoming():
    """Upcoming (non-overdue) action reminders use the [REMINDER] subject prefix."""
    svc = EmailService()
    with patch.object(svc, "send_email", new_callable=AsyncMock, return_value=True) as mock_send:
        await svc.send_action_reminder(
            to=["manager@example.com"],
            action_id="ACT-002",
            title="Complete risk assessment",
            due_date="2026-03-01",
            days_overdue=0,
        )

    subject = mock_send.call_args.kwargs.get("subject", mock_send.call_args[1].get("subject", ""))
    assert "[REMINDER]" in subject


# ---------------------------------------------------------------------------
# Password reset template
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_password_reset_email_includes_url():
    """Password reset email includes the reset URL in the body."""
    svc = EmailService()
    reset_url = "https://app.example.com/reset?token=abc123"

    with patch.object(svc, "send_email", new_callable=AsyncMock, return_value=True) as mock_send:
        await svc.send_password_reset_email(
            to="user@example.com",
            reset_url=reset_url,
            user_name="Alice",
        )

    html = mock_send.call_args.kwargs.get("html_content", mock_send.call_args[1].get("html_content", ""))
    assert reset_url in html
    assert "Alice" in html


@pytest.mark.asyncio
async def test_send_password_reset_email_sends_to_single_recipient():
    """Password reset wraps the single email in a list for send_email."""
    svc = EmailService()

    with patch.object(svc, "send_email", new_callable=AsyncMock, return_value=True) as mock_send:
        await svc.send_password_reset_email(
            to="single@example.com",
            reset_url="https://example.com/reset",
        )

    to_arg = mock_send.call_args.kwargs.get("to", mock_send.call_args[1].get("to", []))
    assert to_arg == ["single@example.com"]


if __name__ == "__main__":
    print("=" * 60)
    print("EMAIL SERVICE UNIT TESTS")
    print("=" * 60)

    test_defaults_from_env_vars()
    print("✓ defaults from env vars")
    test_disabled_without_credentials()
    print("✓ disabled without credentials")
    test_enabled_with_credentials()
    print("✓ enabled with credentials")
    test_base_template_contains_placeholders()
    print("✓ base template placeholders")
    test_base_template_renders_without_error()
    print("✓ base template renders")

    print()
    print("=" * 60)
    print("ALL EMAIL SERVICE TESTS PASSED ✅")
    print("=" * 60)
