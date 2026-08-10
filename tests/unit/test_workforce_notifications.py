"""Workforce governance notification dispatch.

Covers the assessment / induction / competency-expiry dispatchers that were
folded out of ``governance_service.NotificationService`` (KILL-1) onto the
canonical ``notification_service.NotificationService``.
"""

import pytest

from src.domain.models.notification import NotificationChannel, NotificationPriority, NotificationType
from src.domain.services.notification_service import NotificationService


@pytest.fixture
def dispatcher(monkeypatch):
    """NotificationService with no DB session and in-app-only delivery stubbed out."""
    service = NotificationService(db=None)
    delivered: list = []

    async def _fake_deliver_in_app(notification):
        delivered.append(notification)

    monkeypatch.setattr(service, "_deliver_in_app", _fake_deliver_in_app)
    service.delivered = delivered  # type: ignore[attr-defined]
    return service


@pytest.mark.asyncio
async def test_assessment_notification_skips_missing_engineer_user(dispatcher):
    created = await dispatcher.notify_assessment_complete(
        assessment_run_id="asm-1",
        engineer_user_id=None,
        supervisor_id=7,
        outcome="pass",
        tenant_id=3,
    )

    assert len(created) == 1
    supervisor_notification = created[0]
    assert supervisor_notification.user_id == 7
    assert supervisor_notification.tenant_id == 3
    assert supervisor_notification.action_url == "/workforce/assessments/asm-1/execute"
    # Delivery must actually be dispatched, not just persisted.
    assert dispatcher.delivered == [supervisor_notification]
    assert supervisor_notification.delivered_channels == [NotificationChannel.IN_APP.value]


@pytest.mark.asyncio
async def test_induction_notification_skips_missing_engineer_user(dispatcher):
    created = await dispatcher.notify_induction_complete(
        induction_run_id="ind-1",
        engineer_user_id=None,
        supervisor_id=7,
        not_yet_competent_count=0,
        tenant_id=3,
    )

    assert len(created) == 1
    supervisor_notification = created[0]
    assert supervisor_notification.user_id == 7
    assert supervisor_notification.tenant_id == 3
    assert supervisor_notification.action_url == "/workforce/training/ind-1/execute"
    assert dispatcher.delivered == [supervisor_notification]


@pytest.mark.asyncio
async def test_induction_notification_notifies_engineer_and_supervisor(dispatcher):
    created = await dispatcher.notify_induction_complete(
        induction_run_id="ind-2",
        engineer_user_id=11,
        supervisor_id=7,
        not_yet_competent_count=2,
        tenant_id=5,
    )

    assert len(created) == 2
    engineer_notification, supervisor_notification = created
    assert engineer_notification.user_id == 11
    assert supervisor_notification.user_id == 7
    assert engineer_notification.tenant_id == 5
    assert supervisor_notification.tenant_id == 5
    # Workforce SPA routes are admin/supervisor gated, so the engineer gets no deep link.
    assert engineer_notification.action_url is None
    assert supervisor_notification.action_url == "/workforce/training/ind-2/execute"
    assert dispatcher.delivered == [engineer_notification, supervisor_notification]


@pytest.mark.asyncio
async def test_assessment_notifies_engineer_and_supervisor(dispatcher):
    created = await dispatcher.notify_assessment_complete(
        assessment_run_id="run-1",
        engineer_user_id=5,
        supervisor_id=10,
        outcome="pass",
    )

    assert len(created) == 2
    engineer_notification, supervisor_notification = created
    assert engineer_notification.user_id == 5
    assert supervisor_notification.user_id == 10
    assert engineer_notification.type == NotificationType.AUDIT_COMPLETED
    assert engineer_notification.priority == NotificationPriority.MEDIUM
    assert engineer_notification.entity_type == "assessment"
    assert engineer_notification.entity_id == "run-1"
    assert engineer_notification.action_url is None
    assert supervisor_notification.action_url == "/workforce/assessments/run-1/execute"
    assert dispatcher.delivered == [engineer_notification, supervisor_notification]


@pytest.mark.asyncio
async def test_assessment_outcome_shapes_engineer_message(dispatcher):
    engineer_notification, _supervisor = await dispatcher.notify_assessment_complete(
        assessment_run_id="run-2",
        engineer_user_id=5,
        supervisor_id=10,
        outcome="fail",
    )
    assert "FAIL" in engineer_notification.message
    assert engineer_notification.extra_data["outcome"] == "fail"

    unknown_engineer, _unknown_supervisor = await dispatcher.notify_assessment_complete(
        assessment_run_id="run-3",
        engineer_user_id=5,
        supervisor_id=10,
        outcome="withdrawn",
    )
    assert unknown_engineer.message == "Assessment completed with outcome: withdrawn"


@pytest.mark.asyncio
async def test_induction_message_differs_when_all_competent(dispatcher):
    all_competent, _supervisor = await dispatcher.notify_induction_complete(
        induction_run_id="ind-3",
        engineer_user_id=5,
        supervisor_id=10,
        not_yet_competent_count=0,
    )
    with_gaps, _gaps_supervisor = await dispatcher.notify_induction_complete(
        induction_run_id="ind-4",
        engineer_user_id=5,
        supervisor_id=10,
        not_yet_competent_count=3,
    )

    assert "Congratulations" in all_competent.message
    assert "Not Yet Competent" in with_gaps.message
    assert with_gaps.extra_data["not_yet_competent_count"] == 3


@pytest.mark.asyncio
async def test_competency_expiry_notification(dispatcher):
    notification = await dispatcher.notify_competency_expiry(
        engineer_user_id=5,
        asset_type_id=3,
        days_until_expiry=14,
        tenant_id=2,
    )

    assert notification is not None
    assert notification.user_id == 5
    assert notification.tenant_id == 2
    assert notification.type == NotificationType.CERTIFICATE_EXPIRING
    assert notification.entity_type == "competency"
    assert notification.entity_id == "3"
    assert "14 days" in notification.message
    assert dispatcher.delivered == [notification]


@pytest.mark.asyncio
async def test_competency_expiry_skips_when_no_user_id(dispatcher):
    assert (
        await dispatcher.notify_competency_expiry(
            engineer_user_id=None,
            asset_type_id=3,
            days_until_expiry=14,
        )
        is None
    )
    assert dispatcher.delivered == []
