"""D-W1-11: unified action assignment notify + audit proof tests."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.services.action_assignment_service import notify_action_assignment, record_action_assigned_audit


@pytest.mark.asyncio
async def test_notify_action_assignment_calls_create_assignment() -> None:
    db = object()
    due = datetime(2026, 7, 14, tzinfo=timezone.utc)
    mock_service = AsyncMock()
    mock_service.create_assignment = AsyncMock()

    with patch(
        "src.domain.services.action_assignment_service.NotificationService",
        return_value=mock_service,
    ):
        await notify_action_assignment(
            db,
            action_id=42,
            assigned_to_user_id=7,
            assigned_by_user_id=3,
            title="Close wet-floor hazard",
            priority="high",
            due_date=due,
        )

    mock_service.create_assignment.assert_awaited_once_with(
        entity_type="action",
        entity_id="42",
        assigned_to_user_id=7,
        assigned_by_user_id=3,
        due_date=due,
        priority="high",
        notes="You have been assigned action: Close wet-floor hazard",
    )


@pytest.mark.asyncio
async def test_notify_action_assignment_normalizes_unknown_priority() -> None:
    mock_service = AsyncMock()
    mock_service.create_assignment = AsyncMock()

    with patch(
        "src.domain.services.action_assignment_service.NotificationService",
        return_value=mock_service,
    ):
        await notify_action_assignment(
            object(),
            action_id=1,
            assigned_to_user_id=2,
            assigned_by_user_id=3,
            title="Triage follow-up",
            priority="urgent",
        )

    assert mock_service.create_assignment.await_args.kwargs["priority"] == "medium"


@pytest.mark.asyncio
async def test_notify_action_assignment_logs_structured_warning_without_raising() -> None:
    mock_service = AsyncMock()
    mock_service.create_assignment = AsyncMock(side_effect=RuntimeError("notify down"))

    with (
        patch(
            "src.domain.services.action_assignment_service.NotificationService",
            return_value=mock_service,
        ),
        patch("src.domain.services.action_assignment_service.logger.warning") as warning_mock,
    ):
        await notify_action_assignment(
            object(),
            action_id=99,
            assigned_to_user_id=2,
            assigned_by_user_id=3,
            title="Should not raise",
        )

    warning_mock.assert_called_once_with(
        "action_assignment_notification_failed",
        extra={
            "action_id": 99,
            "assigned_to_user_id": 2,
            "assigned_by_user_id": 3,
            "exception_type": "RuntimeError",
        },
        exc_info=True,
    )


@pytest.mark.asyncio
async def test_record_action_assigned_audit_emits_unified_action_assigned() -> None:
    with patch(
        "src.domain.services.action_assignment_service.record_audit_event",
        new_callable=AsyncMock,
    ) as audit_mock:
        await record_action_assigned_audit(
            object(),
            action_key="incident_action:12",
            assigned_to_user_id=5,
            previous_owner_id=2,
            assigned_by_user_id=9,
            request_id="req-assign",
            source_type="incident",
            reference_number="INA-2026-AB12",
        )

    audit_mock.assert_awaited_once()
    kwargs = audit_mock.await_args.kwargs
    assert kwargs["event_type"] == "unified_action.assigned"
    assert kwargs["entity_id"] == "incident_action:12"
    assert kwargs["action"] == "assign"
    assert kwargs["payload"] == {
        "source_type": "incident",
        "assigned_to_user_id": 5,
        "previous_owner_id": 2,
    }
    assert kwargs["user_id"] == 9
    assert kwargs["request_id"] == "req-assign"


def test_actions_route_imports_assignment_service_helpers() -> None:
    """Unified actions routes must use the shared assignment service."""
    from src.api.routes import actions as actions_module
    from src.domain.services import action_assignment_service as service_module

    assert actions_module.notify_action_assignment is service_module.notify_action_assignment
    assert actions_module.record_action_assigned_audit is service_module.record_action_assigned_audit
