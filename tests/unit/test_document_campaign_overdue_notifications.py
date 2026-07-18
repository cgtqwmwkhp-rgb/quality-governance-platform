"""Unit tests for document campaign overdue escalation and typed notifications."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models.document_campaign import AssignmentStatus, CampaignStatus
from src.domain.models.notification import Notification, NotificationType
from src.domain.services.document_campaign_notifications import (
    ENTITY_TYPE_CAMPAIGN,
    ENTITY_TYPE_CAMPAIGN_OVERDUE,
    ENTITY_TYPE_CAMPAIGN_REMINDER,
    build_assignment_notification_kwargs,
    build_overdue_notification_kwargs,
    build_reminder_notification_kwargs,
    overdue_escalation_recipients,
    overdue_recipient_role,
    reminder_due_now,
    sorted_reminder_offsets_hours,
    user_manager_id,
)
from src.domain.services.document_campaign_service import DocumentCampaignService

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


class TestCampaignNotificationHelpers:
    def test_sorted_reminder_offsets_descending(self):
        assert sorted_reminder_offsets_hours([24, 720, 168]) == [720, 168, 24]

    def test_user_manager_id_checks_known_fields(self):
        assert user_manager_id(SimpleNamespace(manager_id=9)) == 9
        assert user_manager_id(SimpleNamespace(supervisor_id=11)) == 11
        assert user_manager_id(SimpleNamespace(reports_to=12)) == 12
        assert user_manager_id(SimpleNamespace(first_name="No")) is None

    def test_reminder_due_now_respects_offset_schedule(self):
        due_at = NOW + timedelta(hours=720)
        assert reminder_due_now(
            now=NOW,
            due_at=due_at,
            reminders_sent=0,
            reminder_offsets_hours=[24, 168, 720],
        )
        assert not reminder_due_now(
            now=NOW,
            due_at=due_at,
            reminders_sent=0,
            reminder_offsets_hours=[24],
        )

    def test_overdue_escalation_recipients_includes_assignee_manager_and_hsec(self):
        assignee = SimpleNamespace(manager_id=42)
        recipients = overdue_escalation_recipients(
            assignee_user_id=10,
            assignee_user=assignee,
            created_by_id=5,
            launched_by_id=5,
        )
        assert recipients == [10, 42, 5]

    def test_build_assignment_notification_uses_document_campaign_entity_type(self):
        kwargs = build_assignment_notification_kwargs(
            tenant_id=1,
            user_id=10,
            campaign_id=99,
            assignment_id=55,
            document_id=7,
            doc_title="Fire Safety Policy",
            require_quiz=True,
            sender_id=3,
        )
        assert kwargs["entity_type"] == ENTITY_TYPE_CAMPAIGN
        assert kwargs["type"] is NotificationType.ASSIGNMENT
        assert kwargs["title"] == "Document campaign assigned"
        assert kwargs["action_url"] == "/portal/reading?assignment=55"
        assert "quiz" in kwargs["message"]

    def test_build_reminder_notification_uses_reminder_entity_type(self):
        kwargs = build_reminder_notification_kwargs(
            tenant_id=1,
            user_id=10,
            campaign_id=99,
            assignment_id=55,
            document_id=7,
            doc_title="Fire Safety Policy",
            due_at=NOW + timedelta(days=7),
        )
        assert kwargs["entity_type"] == ENTITY_TYPE_CAMPAIGN_REMINDER
        assert kwargs["type"] is NotificationType.ACTION_DUE_SOON
        assert kwargs["title"] == "Document campaign reminder"
        assert kwargs["action_url"] == "/portal/reading?assignment=55"

    def test_build_overdue_notification_varies_by_recipient_role(self):
        assignee_kwargs = build_overdue_notification_kwargs(
            tenant_id=1,
            user_id=10,
            campaign_id=99,
            assignment_id=55,
            document_id=7,
            doc_title="Fire Safety Policy",
            assignee_user_id=10,
            assignee_display_name="Alex Engineer",
            recipient_role="assignee",
        )
        manager_kwargs = build_overdue_notification_kwargs(
            tenant_id=1,
            user_id=42,
            campaign_id=99,
            assignment_id=55,
            document_id=7,
            doc_title="Fire Safety Policy",
            assignee_user_id=10,
            assignee_display_name="Alex Engineer",
            recipient_role="manager",
        )
        assert assignee_kwargs["entity_type"] == ENTITY_TYPE_CAMPAIGN_OVERDUE
        assert assignee_kwargs["type"] is NotificationType.ACTION_OVERDUE
        assert assignee_kwargs["title"] == "Document campaign overdue"
        assert assignee_kwargs["action_url"] == "/portal/reading?assignment=55"
        assert manager_kwargs["title"] == "Team member campaign overdue"
        assert "Alex Engineer" in manager_kwargs["message"]

    def test_overdue_recipient_role_classification(self):
        assignee = SimpleNamespace(manager_id=42)
        assert overdue_recipient_role(recipient_user_id=10, assignee_user_id=10, assignee_user=assignee) == "assignee"
        assert overdue_recipient_role(recipient_user_id=42, assignee_user_id=10, assignee_user=assignee) == "manager"
        assert overdue_recipient_role(recipient_user_id=5, assignee_user_id=10, assignee_user=assignee) == "hsec_owner"


def _assignment_row(*, assignment_id=1, user_id=10, due_at=None, reminders_sent=0):
    assignment = SimpleNamespace(
        id=assignment_id,
        user_id=user_id,
        tenant_id=1,
        campaign_id=99,
        status=AssignmentStatus.PENDING,
        due_at=due_at or (NOW - timedelta(hours=1)),
        reminders_sent=reminders_sent,
        last_reminder_at=None,
    )
    campaign = SimpleNamespace(
        id=99,
        tenant_id=1,
        document_id=7,
        status=CampaignStatus.ACTIVE,
        reminder_offsets_hours=[24, 168, 720],
        require_quiz=False,
        created_by_id=5,
        launched_by_id=6,
    )
    return assignment, campaign


class TestProcessDueReminders:
    @pytest.mark.asyncio
    async def test_marks_overdue_and_creates_notifications_for_assignee_and_hsec(self):
        assignment, campaign = _assignment_row(user_id=10)
        assignee = SimpleNamespace(id=10, first_name="Alex", last_name="Engineer", manager_id=None)

        pending_result = MagicMock()
        pending_result.all.return_value = [(assignment, campaign)]

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [assignee]

        db = SimpleNamespace(
            execute=AsyncMock(side_effect=[pending_result, users_result]),
            add=MagicMock(),
            commit=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service._document_title = AsyncMock(return_value="Fire Safety Policy")

        results = await service.process_due_reminders(now=NOW)

        assert results["overdue_escalated"] == 1
        assert results["notifications_created"] == 3  # assignee + created_by + launched_by
        assert assignment.status == AssignmentStatus.OVERDUE

        notifications = [call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], Notification)]
        assert len(notifications) == 3
        assert {n.user_id for n in notifications} == {10, 5, 6}

    @pytest.mark.asyncio
    async def test_overdue_escalation_includes_manager_when_present(self):
        assignment, campaign = _assignment_row(user_id=10)
        assignee = SimpleNamespace(id=10, first_name="Alex", last_name="Engineer", manager_id=42)

        pending_result = MagicMock()
        pending_result.all.return_value = [(assignment, campaign)]
        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [assignee]

        db = SimpleNamespace(
            execute=AsyncMock(side_effect=[pending_result, users_result]),
            add=MagicMock(),
            commit=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service._document_title = AsyncMock(return_value="Fire Safety Policy")

        results = await service.process_due_reminders(now=NOW)

        assert results["notifications_created"] == 4
        notifications = [call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], Notification)]
        assert {n.user_id for n in notifications} == {10, 42, 5, 6}

    @pytest.mark.asyncio
    async def test_sends_reminder_before_due_without_marking_overdue(self):
        due_at = NOW + timedelta(hours=24)
        assignment, campaign = _assignment_row(user_id=10, due_at=due_at, reminders_sent=0)

        pending_result = MagicMock()
        pending_result.all.return_value = [(assignment, campaign)]
        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = []

        db = SimpleNamespace(
            execute=AsyncMock(side_effect=[pending_result, users_result]),
            add=MagicMock(),
            commit=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service._document_title = AsyncMock(return_value="Fire Safety Policy")

        results = await service.process_due_reminders(now=NOW)

        assert results["reminders_sent"] == 1
        assert results["overdue_escalated"] == 0
        assert assignment.status == AssignmentStatus.PENDING
        assert assignment.reminders_sent == 1
        assert assignment.last_reminder_at == NOW

        notification = db.add.call_args.args[0]
        assert notification.entity_type == ENTITY_TYPE_CAMPAIGN_REMINDER
        assert notification.user_id == 10

    @pytest.mark.asyncio
    async def test_notification_failure_does_not_abort_sweep(self):
        assignment, campaign = _assignment_row(user_id=10)
        assignee = SimpleNamespace(id=10, first_name="Alex", last_name="Engineer")

        pending_result = MagicMock()
        pending_result.all.return_value = [(assignment, campaign)]
        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [assignee]

        db = SimpleNamespace(
            execute=AsyncMock(side_effect=[pending_result, users_result]),
            add=MagicMock(side_effect=RuntimeError("db write failed")),
            commit=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service._document_title = AsyncMock(return_value="Fire Safety Policy")

        results = await service.process_due_reminders(now=NOW)

        assert results["overdue_escalated"] == 1
        assert results["notifications_created"] == 0
        assert assignment.status == AssignmentStatus.OVERDUE
        db.commit.assert_awaited_once()
