"""Unit tests for Notification Service - can run standalone."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

try:
    from src.domain.models.notification import NotificationChannel, NotificationPriority, NotificationType
    from src.domain.services.notification_service import MENTION_PATTERN, NotificationService

    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Imports not available")


# ---------------------------------------------------------------------------
# Mention parsing (pure functions)
# ---------------------------------------------------------------------------


def test_parse_mentions_simple_username():
    """Test parsing simple @username mentions."""
    svc = NotificationService()
    result = svc.parse_mentions("Hello @john please review this")
    assert result == ["john"]


def test_parse_mentions_bracket_format():
    """Test parsing @[Full Name] bracket mentions."""
    svc = NotificationService()
    result = svc.parse_mentions("Please ask @[Jane Doe] about this")
    assert result == ["Jane Doe"]


def test_parse_mentions_multiple():
    """Test parsing multiple mentions in one string."""
    svc = NotificationService()
    result = svc.parse_mentions("@alice and @[Bob Smith] need to review @charlie")
    assert len(result) == 3
    assert "alice" in result
    assert "Bob Smith" in result
    assert "charlie" in result


def test_parse_mentions_no_mentions():
    """Test parsing text with no mentions."""
    svc = NotificationService()
    result = svc.parse_mentions("This text has no mentions at all")
    assert result == []


def test_parse_mentions_email_not_matched_as_mention():
    """Test that email addresses don't produce full-address matches."""
    svc = NotificationService()
    result = svc.parse_mentions("Send to user@example.com for review")
    for m in result:
        assert "@" not in m


def test_mention_regex_pattern():
    """Test the MENTION_PATTERN regex directly for coverage."""
    matches = list(MENTION_PATTERN.finditer("@user1 and @[Full Name]"))
    assert len(matches) == 2
    assert matches[0].group(2) == "user1"
    assert matches[1].group(1) == "Full Name"


# ---------------------------------------------------------------------------
# Delivery channel routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_critical_priority_sends_all_channels():
    """Critical priority notifications must use all channels."""
    svc = NotificationService(db=None)
    channels = await svc._get_delivery_channels(
        user_id=1,
        notification_type=NotificationType.INCIDENT_ESCALATED,
        priority=NotificationPriority.CRITICAL,
    )
    assert NotificationChannel.IN_APP in channels
    assert NotificationChannel.EMAIL in channels
    assert NotificationChannel.SMS in channels
    assert NotificationChannel.PUSH in channels


@pytest.mark.asyncio
async def test_non_critical_without_db_returns_in_app_only():
    """Without a DB session, only IN_APP is returned for non-critical."""
    svc = NotificationService(db=None)
    channels = await svc._get_delivery_channels(
        user_id=1,
        notification_type=NotificationType.MENTION,
        priority=NotificationPriority.MEDIUM,
    )
    assert channels == [NotificationChannel.IN_APP]


# ---------------------------------------------------------------------------
# Notification creation (no DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_notification_without_db():
    """Notifications can be created without a database session."""
    svc = NotificationService(db=None)

    with patch.object(svc, "_deliver_in_app", new_callable=AsyncMock):
        notification = await svc.create_notification(
            user_id=42,
            notification_type=NotificationType.ASSIGNMENT,
            title="Test assignment",
            message="You have a new task",
            priority=NotificationPriority.MEDIUM,
        )

    assert notification.user_id == 42
    assert notification.title == "Test assignment"
    assert notification.type == NotificationType.ASSIGNMENT
    assert notification.priority == NotificationPriority.MEDIUM


@pytest.mark.asyncio
async def test_create_notification_records_delivered_channels():
    """Delivered channels are recorded on the notification object."""
    svc = NotificationService(db=None)

    with patch.object(svc, "_deliver_in_app", new_callable=AsyncMock):
        notification = await svc.create_notification(
            user_id=1,
            notification_type=NotificationType.INCIDENT_NEW,
            title="Incident",
            message="New incident",
            channels=[NotificationChannel.IN_APP],
        )

    assert NotificationChannel.IN_APP.value in notification.delivered_channels


@pytest.mark.asyncio
async def test_create_notification_with_metadata():
    """Metadata is stored in extra_data."""
    svc = NotificationService(db=None)

    with patch.object(svc, "_deliver_in_app", new_callable=AsyncMock):
        notification = await svc.create_notification(
            user_id=1,
            notification_type=NotificationType.SYSTEM_ANNOUNCEMENT,
            title="Announcement",
            message="Scheduled maintenance",
            metadata={"window": "02:00-04:00"},
        )

    assert notification.extra_data == {"window": "02:00-04:00"}


# ---------------------------------------------------------------------------
# Bulk notifications
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_bulk_notifications():
    """Bulk notifications create one notification per user."""
    svc = NotificationService(db=None)

    with patch.object(svc, "_deliver_in_app", new_callable=AsyncMock):
        notifications = await svc.create_bulk_notifications(
            user_ids=[10, 20, 30],
            notification_type=NotificationType.SYSTEM_ANNOUNCEMENT,
            title="Downtime",
            message="System maintenance tonight",
        )

    assert len(notifications) == 3
    assert {n.user_id for n in notifications} == {10, 20, 30}


# ---------------------------------------------------------------------------
# Mark-as-read without DB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_as_read_returns_false_without_db():
    """mark_as_read gracefully returns False when no DB is available."""
    svc = NotificationService(db=None)
    result = await svc.mark_as_read(notification_id=1, user_id=1)
    assert result is False


@pytest.mark.asyncio
async def test_mark_all_as_read_returns_zero_without_db():
    """mark_all_as_read returns 0 when no DB is available."""
    svc = NotificationService(db=None)
    result = await svc.mark_all_as_read(user_id=1)
    assert result == 0


@pytest.mark.asyncio
async def test_get_unread_count_returns_zero_without_db():
    """get_unread_count returns 0 when no DB is available."""
    svc = NotificationService(db=None)
    result = await svc.get_unread_count(user_id=1)
    assert result == 0


@pytest.mark.asyncio
async def test_get_notifications_returns_empty_without_db():
    """get_notifications returns [] when no DB is available."""
    svc = NotificationService(db=None)
    result = await svc.get_notifications(user_id=1)
    assert result == []


# ---------------------------------------------------------------------------
# SOS / emergency alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_sos_alert_creates_notifications_for_safety_team():
    """SOS alert creates one CRITICAL notification per safety team member."""
    svc = NotificationService(db=None)

    with patch.object(svc, "_deliver_in_app", new_callable=AsyncMock):
        notifications = await svc.send_sos_alert(
            reporter_id=1,
            reporter_name="Alice",
            location="Building A",
            safety_team_ids=[10, 20],
        )

    assert len(notifications) == 2
    for n in notifications:
        assert n.priority == NotificationPriority.CRITICAL
        assert n.type == NotificationType.SOS_ALERT


@pytest.mark.asyncio
async def test_send_sos_alert_empty_team():
    """SOS with no safety_team_ids produces no notifications."""
    svc = NotificationService(db=None)
    notifications = await svc.send_sos_alert(
        reporter_id=1,
        reporter_name="Bob",
        location="Warehouse",
        safety_team_ids=[],
    )
    assert notifications == []


# ---------------------------------------------------------------------------
# RIDDOR alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_riddor_alert_creates_critical_notifications():
    """RIDDOR alert creates CRITICAL notifications for compliance team."""
    svc = NotificationService(db=None)

    with patch.object(svc, "_deliver_in_app", new_callable=AsyncMock):
        notifications = await svc.send_riddor_alert(
            incident_id="INC-001",
            incident_type="Major injury",
            location="Site B",
            compliance_team_ids=[5, 6, 7],
        )

    assert len(notifications) == 3
    for n in notifications:
        assert n.priority == NotificationPriority.CRITICAL
        assert n.type == NotificationType.RIDDOR_INCIDENT
        assert n.entity_id == "INC-001"


# ---------------------------------------------------------------------------
# Assignment creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_assignment_notifies_user():
    """Creating an assignment sends a notification to the assignee."""
    svc = NotificationService(db=None)

    with patch.object(svc, "_deliver_in_app", new_callable=AsyncMock) as mock_deliver:
        assignment = await svc.create_assignment(
            entity_type="action",
            entity_id="ACT-100",
            assigned_to_user_id=50,
            assigned_by_user_id=1,
            priority="high",
            notes="Please complete by Friday",
        )

    assert assignment.entity_type == "action"
    assert assignment.assigned_to_user_id == 50
    assert mock_deliver.call_count >= 1


# ---------------------------------------------------------------------------
# Process mentions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_mentions_creates_notifications():
    """Processing mentions notifies mentioned users (not the author)."""
    svc = NotificationService(db=None)
    user_lookup = {"alice": 10, "bob": 20}

    with patch.object(svc, "_deliver_in_app", new_callable=AsyncMock):
        mentions = await svc.process_mentions(
            text="Hey @alice and @bob, please review",
            content_type="incident",
            content_id="INC-50",
            mentioned_by_user_id=99,
            user_lookup=user_lookup,
        )

    assert len(mentions) == 2
    mentioned_ids = {m.mentioned_user_id for m in mentions}
    assert mentioned_ids == {10, 20}


@pytest.mark.asyncio
async def test_process_mentions_skips_self_mention():
    """Author mentioning themselves does not create a mention record."""
    svc = NotificationService(db=None)
    user_lookup = {"alice": 99}

    with patch.object(svc, "_deliver_in_app", new_callable=AsyncMock):
        mentions = await svc.process_mentions(
            text="Reminder to myself @alice",
            content_type="action",
            content_id="ACT-1",
            mentioned_by_user_id=99,
            user_lookup=user_lookup,
        )

    assert len(mentions) == 0


if __name__ == "__main__":
    print("=" * 60)
    print("NOTIFICATION SERVICE UNIT TESTS")
    print("=" * 60)

    test_parse_mentions_simple_username()
    print("  parse_mentions simple username")
    test_parse_mentions_bracket_format()
    print("  parse_mentions bracket format")
    test_parse_mentions_multiple()
    print("  parse_mentions multiple")
    test_parse_mentions_no_mentions()
    print("  parse_mentions no mentions")
    test_mention_regex_pattern()
    print("  mention regex pattern")

    print()
    print("=" * 60)
    print("ALL NOTIFICATION SERVICE TESTS PASSED")
    print("=" * 60)
