"""Owner assignment notify for Compliance Schedule — flag gates + once-per-change."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models.notification import NotificationChannel, NotificationType
from src.domain.services.compliance_schedule_assignment_notify import (
    notify_compliance_schedule_owner_assignment,
)
from src.domain.services.compliance_schedule_notify_flags import (
    ASSIGNMENT_NOTIFY_FLAG,
    DUE_REMINDER_NOTIFY_FLAG,
    EMAIL_ENABLED_FLAG,
    NOTIFY_FLAG_KEYS,
)


@pytest.mark.asyncio
async def test_notify_skips_when_owner_unchanged() -> None:
    db = MagicMock()
    with patch(
        "src.domain.services.compliance_schedule_assignment_notify.NotificationService"
    ) as svc_cls:
        result = await notify_compliance_schedule_owner_assignment(
            db,
            tenant_id=1,
            requirement_id=11,
            reference_number="CSR-1",
            title="FRA",
            new_owner_id=7,
            previous_owner_id=7,
            assigned_by_user_id=2,
            next_due_date=date(2026, 9, 1),
        )
    assert result is None
    svc_cls.assert_not_called()


@pytest.mark.asyncio
async def test_notify_skips_when_assignment_flag_off(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.domain.services.compliance_schedule_assignment_notify.settings.compliance_schedule_enabled",
        True,
    )
    db = MagicMock()
    with (
        patch(
            "src.domain.services.compliance_schedule_assignment_notify._kill_switch_engaged",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "src.domain.services.compliance_schedule_assignment_notify.assignment_notify_enabled",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "src.domain.services.compliance_schedule_assignment_notify.NotificationService"
        ) as svc_cls,
    ):
        result = await notify_compliance_schedule_owner_assignment(
            db,
            tenant_id=1,
            requirement_id=11,
            reference_number="CSR-1",
            title="FRA",
            new_owner_id=7,
            previous_owner_id=None,
            assigned_by_user_id=2,
        )
    assert result is None
    svc_cls.assert_not_called()


@pytest.mark.asyncio
async def test_notify_creates_assignment_once_for_new_owner(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.domain.services.compliance_schedule_assignment_notify.settings.compliance_schedule_enabled",
        True,
    )
    db = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    mock_service = AsyncMock()
    notification = MagicMock()
    notification.tenant_id = None
    mock_service.create_notification = AsyncMock(return_value=notification)

    with (
        patch(
            "src.domain.services.compliance_schedule_assignment_notify._kill_switch_engaged",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "src.domain.services.compliance_schedule_assignment_notify.assignment_notify_enabled",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "src.domain.services.compliance_schedule_assignment_notify.email_channel_enabled",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "src.domain.services.compliance_schedule_assignment_notify._user_email_pref_enabled",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "src.domain.services.compliance_schedule_assignment_notify.NotificationService",
            return_value=mock_service,
        ),
    ):
        result = await notify_compliance_schedule_owner_assignment(
            db,
            tenant_id=3,
            requirement_id=11,
            reference_number="CSR-0011",
            title="Fire risk assessment",
            new_owner_id=7,
            previous_owner_id=None,
            assigned_by_user_id=2,
            next_due_date=date(2026, 9, 1),
        )

    assert result is notification
    mock_service.create_notification.assert_awaited_once()
    kwargs = mock_service.create_notification.await_args.kwargs
    assert kwargs["user_id"] == 7
    assert kwargs["notification_type"] is NotificationType.ASSIGNMENT
    assert NotificationChannel.IN_APP in kwargs["channels"]
    assert NotificationChannel.EMAIL in kwargs["channels"]
    assert notification.tenant_id == 3


@pytest.mark.asyncio
async def test_notify_omits_email_when_email_flag_off(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.domain.services.compliance_schedule_assignment_notify.settings.compliance_schedule_enabled",
        True,
    )
    mock_service = AsyncMock()
    notification = MagicMock()
    notification.tenant_id = 1
    mock_service.create_notification = AsyncMock(return_value=notification)

    with (
        patch(
            "src.domain.services.compliance_schedule_assignment_notify._kill_switch_engaged",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "src.domain.services.compliance_schedule_assignment_notify.assignment_notify_enabled",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "src.domain.services.compliance_schedule_assignment_notify.email_channel_enabled",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "src.domain.services.compliance_schedule_assignment_notify.NotificationService",
            return_value=mock_service,
        ),
    ):
        await notify_compliance_schedule_owner_assignment(
            MagicMock(),
            tenant_id=1,
            requirement_id=11,
            reference_number="CSR-1",
            title="FRA",
            new_owner_id=7,
            previous_owner_id=3,
            assigned_by_user_id=2,
        )

    channels = mock_service.create_notification.await_args.kwargs["channels"]
    assert channels == [NotificationChannel.IN_APP]
    assert mock_service.create_notification.await_args.kwargs["notification_type"] is NotificationType.REASSIGNMENT


@pytest.mark.asyncio
async def test_notify_failure_is_swallowed(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.domain.services.compliance_schedule_assignment_notify.settings.compliance_schedule_enabled",
        True,
    )
    mock_service = AsyncMock()
    mock_service.create_notification = AsyncMock(side_effect=RuntimeError("down"))

    with (
        patch(
            "src.domain.services.compliance_schedule_assignment_notify._kill_switch_engaged",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "src.domain.services.compliance_schedule_assignment_notify.assignment_notify_enabled",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "src.domain.services.compliance_schedule_assignment_notify.email_channel_enabled",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "src.domain.services.compliance_schedule_assignment_notify.NotificationService",
            return_value=mock_service,
        ),
    ):
        result = await notify_compliance_schedule_owner_assignment(
            MagicMock(),
            tenant_id=1,
            requirement_id=11,
            reference_number="CSR-1",
            title="FRA",
            new_owner_id=7,
            previous_owner_id=None,
            assigned_by_user_id=2,
        )
    assert result is None


def test_notify_flag_keys_are_stable() -> None:
    assert ASSIGNMENT_NOTIFY_FLAG in NOTIFY_FLAG_KEYS
    assert DUE_REMINDER_NOTIFY_FLAG in NOTIFY_FLAG_KEYS
    assert EMAIL_ENABLED_FLAG in NOTIFY_FLAG_KEYS
