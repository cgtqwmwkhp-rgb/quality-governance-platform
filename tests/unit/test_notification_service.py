"""Tests for NotificationService – mention parsing, channel logic, SOS alerts."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.notification_service import MENTION_PATTERN, NotificationService


class TestParseMentions:
    def setup_method(self):
        self.service = NotificationService()

    def test_simple_mention(self):
        result = self.service.parse_mentions("Hello @john please review")
        assert result == ["john"]

    def test_bracket_mention(self):
        result = self.service.parse_mentions("Hello @[John Smith] please review")
        assert result == ["John Smith"]

    def test_multiple_mentions(self):
        result = self.service.parse_mentions("@alice and @bob should look at this")
        assert result == ["alice", "bob"]

    def test_mixed_mention_formats(self):
        result = self.service.parse_mentions("@alice and @[Bob Jones] check this")
        assert result == ["alice", "Bob Jones"]

    def test_no_mentions(self):
        result = self.service.parse_mentions("No mentions here at all")
        assert result == []

    def test_mention_at_start(self):
        result = self.service.parse_mentions("@admin please help")
        assert result == ["admin"]

    def test_mention_at_end(self):
        result = self.service.parse_mentions("Please help @admin")
        assert result == ["admin"]

    def test_empty_string(self):
        result = self.service.parse_mentions("")
        assert result == []

    def test_email_captures_word_after_at(self):
        result = self.service.parse_mentions("Send to user@example.com")
        assert len(result) == 1


class TestMentionPattern:
    def test_pattern_matches_simple(self):
        match = MENTION_PATTERN.search("@john")
        assert match is not None

    def test_pattern_matches_bracket(self):
        match = MENTION_PATTERN.search("@[John Smith]")
        assert match is not None
        assert match.group(1) == "John Smith"

    def test_pattern_no_match(self):
        match = MENTION_PATTERN.search("no mentions here")
        assert match is None


class TestDeliveryChannels:
    @pytest.mark.asyncio
    async def test_critical_priority_gets_all_channels(self):
        from src.domain.models.notification import NotificationChannel, NotificationPriority, NotificationType

        service = NotificationService(db=None)
        channels = await service._get_delivery_channels(
            user_id=1,
            notification_type=NotificationType.INCIDENT_NEW,
            priority=NotificationPriority.CRITICAL,
        )

        assert NotificationChannel.IN_APP in channels
        assert NotificationChannel.EMAIL in channels
        assert NotificationChannel.SMS in channels
        assert NotificationChannel.PUSH in channels

    @pytest.mark.asyncio
    async def test_non_critical_without_db_returns_in_app_only(self):
        from src.domain.models.notification import NotificationChannel, NotificationPriority, NotificationType

        service = NotificationService(db=None)
        channels = await service._get_delivery_channels(
            user_id=1,
            notification_type=NotificationType.INCIDENT_NEW,
            priority=NotificationPriority.LOW,
        )

        assert channels == [NotificationChannel.IN_APP]


class TestNotificationCreation:
    @pytest.mark.asyncio
    async def test_create_notification_without_db(self):
        from src.domain.models.notification import NotificationChannel, NotificationPriority, NotificationType

        service = NotificationService(db=None)

        with patch.object(service, "_deliver_in_app", new_callable=AsyncMock) as mock_deliver:
            notification = await service.create_notification(
                user_id=1,
                notification_type=NotificationType.ASSIGNMENT,
                title="Test",
                message="Test message",
                priority=NotificationPriority.LOW,
                channels=[NotificationChannel.IN_APP],
            )

        assert notification.user_id == 1
        assert notification.title == "Test"
        assert notification.message == "Test message"

    @pytest.mark.asyncio
    async def test_create_notification_with_metadata(self):
        from src.domain.models.notification import NotificationChannel, NotificationPriority, NotificationType

        service = NotificationService(db=None)
        metadata = {"key": "value", "incident_id": 42}

        with patch.object(service, "_deliver_in_app", new_callable=AsyncMock):
            notification = await service.create_notification(
                user_id=1,
                notification_type=NotificationType.ASSIGNMENT,
                title="Test",
                message="Body",
                priority=NotificationPriority.LOW,
                metadata=metadata,
                channels=[NotificationChannel.IN_APP],
            )

        assert notification.extra_data == metadata


class TestProcessMentions:
    @pytest.mark.asyncio
    async def test_process_mentions_creates_notifications(self):
        from src.domain.models.notification import NotificationChannel

        service = NotificationService(db=None)

        with patch.object(service, "create_notification", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock()
            mentions = await service.process_mentions(
                text="@alice please check this",
                content_type="incident",
                content_id="INC-001",
                mentioned_by_user_id=1,
                user_lookup={"alice": 2},
            )

        assert len(mentions) == 1
        assert mentions[0].mentioned_user_id == 2
        assert mentions[0].mention_text == "alice"
        mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_mentions_skips_self_mention(self):
        service = NotificationService(db=None)

        with patch.object(service, "create_notification", new_callable=AsyncMock) as mock_create:
            mentions = await service.process_mentions(
                text="@alice checking my own work",
                content_type="incident",
                content_id="INC-001",
                mentioned_by_user_id=2,
                user_lookup={"alice": 2},
            )

        assert len(mentions) == 0
        mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_mentions_unknown_user_ignored(self):
        service = NotificationService(db=None)

        with patch.object(service, "create_notification", new_callable=AsyncMock) as mock_create:
            mentions = await service.process_mentions(
                text="@unknown_user check this",
                content_type="incident",
                content_id="INC-001",
                mentioned_by_user_id=1,
                user_lookup={"alice": 2},
            )

        assert len(mentions) == 0
        mock_create.assert_not_called()


class TestMarkAsRead:
    @pytest.mark.asyncio
    async def test_mark_as_read_no_db(self):
        service = NotificationService(db=None)
        result = await service.mark_as_read(notification_id=1, user_id=1)
        assert result is False

    @pytest.mark.asyncio
    async def test_mark_all_as_read_no_db(self):
        service = NotificationService(db=None)
        result = await service.mark_all_as_read(user_id=1)
        assert result == 0

    @pytest.mark.asyncio
    async def test_get_unread_count_no_db(self):
        service = NotificationService(db=None)
        result = await service.get_unread_count(user_id=1)
        assert result == 0

    @pytest.mark.asyncio
    async def test_get_notifications_no_db(self):
        service = NotificationService(db=None)
        result = await service.get_notifications(user_id=1)
        assert result == []
