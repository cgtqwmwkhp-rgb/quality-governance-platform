"""Unit tests for Compliance Schedule due-reminder email enqueue + flag gates."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.tasks.compliance_schedule_notification_tasks import (
    _empty_results,
    _maybe_enqueue_due_reminder_email,
    _sweep_tenant,
)


@pytest.mark.asyncio
async def test_enqueue_email_calls_send_email_delay() -> None:
    results = _empty_results(dry_run=False, evaluated_at=datetime.now(timezone.utc))
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: "owner@example.com")
    )

    with (
        patch(
            "src.domain.services.compliance_schedule_notify_flags.email_channel_enabled",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "src.infrastructure.tasks.compliance_schedule_notification_tasks._user_email_pref_enabled",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch("src.infrastructure.tasks.email_tasks.send_email") as send_email,
    ):
        await _maybe_enqueue_due_reminder_email(
            session,
            tenant_id=1,
            user_id=7,
            kwargs={
                "title": "Compliance requirement due within 7 days: FRA",
                "message": "CSR-1 is due within 7 days.",
                "action_url": "/compliance-schedule/11",
            },
            results=results,
        )

    send_email.delay.assert_called_once()
    assert results["emails_enqueued"] == 1
    assert results["emails_skipped"] == 0


@pytest.mark.asyncio
async def test_enqueue_email_skipped_when_email_flag_off() -> None:
    results = _empty_results(dry_run=False, evaluated_at=datetime.now(timezone.utc))
    with (
        patch(
            "src.domain.services.compliance_schedule_notify_flags.email_channel_enabled",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch("src.infrastructure.tasks.email_tasks.send_email") as send_email,
    ):
        await _maybe_enqueue_due_reminder_email(
            MagicMock(),
            tenant_id=1,
            user_id=7,
            kwargs={"title": "t", "message": "m", "action_url": "/x"},
            results=results,
        )
    send_email.delay.assert_not_called()
    assert results["emails_skipped"] == 1


@pytest.mark.asyncio
async def test_sweep_tenant_skips_when_due_reminder_flag_off() -> None:
    results = _empty_results(dry_run=False, evaluated_at=datetime.now(timezone.utc))
    session = MagicMock()

    with (
        patch(
            "src.domain.services.compliance_schedule_notify_flags.due_reminder_notify_enabled",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "src.infrastructure.tasks.compliance_schedule_notification_tasks._due_requirements",
            new_callable=AsyncMock,
        ) as due,
    ):
        await _sweep_tenant(
            session,
            tenant_id=1,
            today=date(2026, 8, 9),
            evaluated_at=datetime(2026, 8, 9, 8, 15, tzinfo=timezone.utc),
            dry_run=False,
            results=results,
        )

    due.assert_not_awaited()
    assert results["requirements_scanned"] == 0
    assert results["notifications_created"] == 0
