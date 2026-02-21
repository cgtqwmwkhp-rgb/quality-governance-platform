"""
Notification Service - Enterprise Notification Management

Features:
- Real-time WebSocket delivery
- Email notifications with templates
- SMS alerts for critical incidents
- Push notifications
- Notification preferences
- Mention parsing and handling
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.domain.models.notification import (
    Assignment,
    Mention,
    Notification,
    NotificationChannel,
    NotificationPreference,
    NotificationPriority,
    NotificationType,
)
from src.infrastructure.websocket.connection_manager import connection_manager

logger = logging.getLogger(__name__)


# Mention regex pattern: @[username] or @username
MENTION_PATTERN = re.compile(r"@\[([^\]]+)\]|@(\w+)")


class NotificationService:
    """
    Comprehensive notification service for real-time alerts.

    Supports multiple delivery channels and respects user preferences.
    """

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
        self.sms_service: Any = None  # Lazy load
        self.email_service: Any = None  # Lazy load

    async def create_notification(
        self,
        user_id: int,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        action_url: Optional[str] = None,
        sender_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        channels: Optional[List[NotificationChannel]] = None,
    ) -> Notification:
        """
        Create and deliver a notification to a user.

        Args:
            user_id: Target user ID
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            priority: Priority level
            entity_type: Related entity type (incident, action, etc.)
            entity_id: Related entity ID
            action_url: URL to navigate to on click
            sender_id: User who triggered the notification
            metadata: Additional data
            channels: Specific channels to use (overrides preferences)

        Returns:
            Created Notification object
        """
        # Create notification record
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            priority=priority,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            action_url=action_url,
            sender_id=sender_id,
            extra_data=metadata or {},
            delivered_channels=[],
        )

        if self.db:
            self.db.add(notification)
            await self.db.commit()
            await self.db.refresh(notification)

        # Determine delivery channels
        delivery_channels = channels or await self._get_delivery_channels(user_id, notification_type, priority)

        # Deliver to each channel
        for channel in delivery_channels:
            try:
                if channel == NotificationChannel.IN_APP:
                    await self._deliver_in_app(notification)
                elif channel == NotificationChannel.EMAIL:
                    await self._deliver_email(notification)
                elif channel == NotificationChannel.SMS:
                    await self._deliver_sms(notification)
                elif channel == NotificationChannel.PUSH:
                    await self._deliver_push(notification)

                if notification.delivered_channels is not None:
                    notification.delivered_channels.append(channel.value)
            except Exception as e:
                logger.error(f"Failed to deliver via {channel}: {e}")

        # Update delivered channels
        if self.db:
            await self.db.commit()

        return notification

    async def create_bulk_notifications(
        self,
        user_ids: List[int],
        notification_type: NotificationType,
        title: str,
        message: str,
        **kwargs,
    ) -> List[Notification]:
        """Create notifications for multiple users"""
        notifications = []
        for user_id in user_ids:
            notification = await self.create_notification(
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                message=message,
                **kwargs,
            )
            notifications.append(notification)
        return notifications

    async def _get_delivery_channels(
        self,
        user_id: int,
        notification_type: NotificationType,
        priority: NotificationPriority,
    ) -> List[NotificationChannel]:
        """Determine which channels to use based on preferences"""
        channels = [NotificationChannel.IN_APP]  # Always in-app

        # Critical notifications always go to all enabled channels
        if priority == NotificationPriority.CRITICAL:
            channels.extend(
                [
                    NotificationChannel.EMAIL,
                    NotificationChannel.SMS,
                    NotificationChannel.PUSH,
                ]
            )
            return channels

        # Get user preferences
        if self.db:
            result = await self.db.execute(
                select(NotificationPreference).where(NotificationPreference.user_id == user_id)
            )
            prefs = result.scalar_one_or_none()

            if prefs:
                if prefs.email_enabled:
                    channels.append(NotificationChannel.EMAIL)
                if prefs.sms_enabled and priority in [
                    NotificationPriority.CRITICAL,
                    NotificationPriority.HIGH,
                ]:
                    channels.append(NotificationChannel.SMS)
                if prefs.push_enabled:
                    channels.append(NotificationChannel.PUSH)

        return channels

    async def _deliver_in_app(self, notification: Notification):
        """Deliver notification via WebSocket"""
        await connection_manager.send_to_user(
            user_id=notification.user_id,
            message=notification.to_dict(),
            event_type="notification",
        )
        logger.debug(f"In-app notification sent to user {notification.user_id}")

    async def _deliver_email(self, notification: Notification):
        """Deliver notification via email"""
        # Lazy load email service
        if self.email_service is None:
            from src.domain.services.email_service import EmailService

            self.email_service = EmailService()

        # TODO: Implement email delivery
        logger.debug(f"Email notification queued for user {notification.user_id}")

    async def _deliver_sms(self, notification: Notification):
        """Deliver notification via SMS"""
        # Lazy load SMS service
        if self.sms_service is None:
            from src.domain.services.sms_service import SMSService

            self.sms_service = SMSService()

        # Get user's phone number
        if self.db:
            result = await self.db.execute(
                select(NotificationPreference).where(NotificationPreference.user_id == notification.user_id)
            )
            prefs = result.scalar_one_or_none()

            if prefs and prefs.phone_number:
                await self.sms_service.send_sms(
                    to=prefs.phone_number,
                    message=f"{notification.title}\n\n{notification.message}",
                )
                logger.info(f"SMS sent to user {notification.user_id}")

    async def _deliver_push(self, notification: Notification):
        """Deliver notification via push notification"""
        # TODO: Implement push notifications (FCM/APNs)
        logger.debug(f"Push notification queued for user {notification.user_id}")

    # ==================== Mention Handling ====================

    def parse_mentions(self, text: str) -> List[str]:
        """
        Parse @mentions from text.

        Supports formats:
        - @username
        - @[Full Name]

        Returns list of mentioned usernames/names
        """
        mentions = []
        for match in MENTION_PATTERN.finditer(text):
            # Group 1 is [name], group 2 is username
            mention = match.group(1) or match.group(2)
            if mention:
                mentions.append(mention)
        return mentions

    async def process_mentions(
        self,
        text: str,
        content_type: str,
        content_id: str,
        mentioned_by_user_id: int,
        user_lookup: Dict[str, int],
        context_snippet: Optional[str] = None,
    ) -> List[Mention]:
        """
        Process mentions in text and create notifications.

        Args:
            text: Text containing @mentions
            content_type: Type of content (incident, action, etc.)
            content_id: ID of the content
            mentioned_by_user_id: User who wrote the text
            user_lookup: Dict mapping username/name to user_id
            context_snippet: Surrounding text for context

        Returns:
            List of created Mention records
        """
        mentions = []
        parsed = self.parse_mentions(text)

        for mention_text in parsed:
            user_id = user_lookup.get(mention_text.lower())
            if user_id and user_id != mentioned_by_user_id:
                # Create mention record
                mention = Mention(
                    content_type=content_type,
                    content_id=content_id,
                    mentioned_user_id=user_id,
                    mentioned_by_user_id=mentioned_by_user_id,
                    mention_text=mention_text,
                    context_snippet=context_snippet or text[:200],
                )

                if self.db:
                    self.db.add(mention)

                mentions.append(mention)

                # Create notification
                await self.create_notification(
                    user_id=user_id,
                    notification_type=NotificationType.MENTION,
                    title="You were mentioned",
                    message=f"You were mentioned in a {content_type}",
                    entity_type=content_type,
                    entity_id=content_id,
                    action_url=f"/{content_type}s/{content_id}",
                    sender_id=mentioned_by_user_id,
                    priority=NotificationPriority.MEDIUM,
                )

        if self.db and mentions:
            await self.db.commit()

        return mentions

    # ==================== Assignment Handling ====================

    async def create_assignment(
        self,
        entity_type: str,
        entity_id: str,
        assigned_to_user_id: int,
        assigned_by_user_id: int,
        due_date: Optional[datetime] = None,
        priority: str = "medium",
        notes: Optional[str] = None,
    ) -> Assignment:
        """
        Create an assignment and notify the assigned user.

        Args:
            entity_type: Type of entity being assigned
            entity_id: ID of the entity
            assigned_to_user_id: User being assigned
            assigned_by_user_id: User making the assignment
            due_date: Optional due date
            priority: Priority level
            notes: Optional notes

        Returns:
            Created Assignment record
        """
        assignment = Assignment(
            entity_type=entity_type,
            entity_id=entity_id,
            assigned_to_user_id=assigned_to_user_id,
            assigned_by_user_id=assigned_by_user_id,
            due_date=due_date,
            priority=priority,
            notes=notes,
        )

        if self.db:
            self.db.add(assignment)
            await self.db.commit()
            await self.db.refresh(assignment)

        # Notify assigned user
        await self.create_notification(
            user_id=assigned_to_user_id,
            notification_type=NotificationType.ASSIGNMENT,
            title=f"New {entity_type} assigned to you",
            message=notes or f"You have been assigned a {entity_type}",
            entity_type=entity_type,
            entity_id=entity_id,
            action_url=f"/{entity_type}s/{entity_id}",
            sender_id=assigned_by_user_id,
            priority=(NotificationPriority.MEDIUM if priority == "medium" else NotificationPriority.HIGH),
        )

        return assignment

    # ==================== Notification Management ====================

    async def mark_as_read(self, notification_id: int, user_id: int) -> bool:
        """Mark a notification as read"""
        if not self.db:
            return False

        result = await self.db.execute(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        )
        notification = result.scalar_one_or_none()

        if notification:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            await self.db.commit()
            return True

        return False

    async def mark_all_as_read(self, user_id: int) -> int:
        """Mark all notifications as read for a user"""
        if not self.db:
            return 0

        result = await self.db.execute(
            select(Notification).where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        )
        notifications = result.scalars().all()

        now = datetime.utcnow()
        for notification in notifications:
            notification.is_read = True
            notification.read_at = now

        await self.db.commit()
        return len(notifications)

    async def get_unread_count(self, user_id: int) -> int:
        """Get count of unread notifications for a user"""
        if not self.db:
            return 0

        from sqlalchemy import func

        result = await self.db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
        )
        return result.scalar() or 0

    async def get_notifications(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
        notification_types: Optional[List[NotificationType]] = None,
    ) -> List[Notification]:
        """Get notifications for a user"""
        if not self.db:
            return []

        query = select(Notification).where(Notification.user_id == user_id)

        if unread_only:
            query = query.where(Notification.is_read == False)  # noqa: E712

        if notification_types:
            query = query.where(Notification.type.in_(notification_types))

        query = query.order_by(Notification.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ==================== SOS/Emergency Notifications ====================

    async def send_sos_alert(
        self,
        reporter_id: int,
        reporter_name: str,
        location: str,
        gps_coordinates: Optional[str] = None,
        description: Optional[str] = None,
        safety_team_ids: Optional[List[int]] = None,
    ) -> List[Notification]:
        """
        Send SOS emergency alert to safety team.

        Args:
            reporter_id: User triggering SOS
            reporter_name: Name of the reporter
            location: Location description
            gps_coordinates: GPS coordinates if available
            description: Optional description
            safety_team_ids: List of safety team user IDs

        Returns:
            List of created notifications
        """
        message = f"""
🚨 EMERGENCY SOS ALERT

Reporter: {reporter_name}
Location: {location}
{f'GPS: {gps_coordinates}' if gps_coordinates else ''}
{f'Details: {description}' if description else ''}

Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

RESPOND IMMEDIATELY
        """.strip()

        notifications = []

        for user_id in safety_team_ids or []:
            notification = await self.create_notification(
                user_id=user_id,
                notification_type=NotificationType.SOS_ALERT,
                title="🚨 EMERGENCY SOS ALERT",
                message=message,
                priority=NotificationPriority.CRITICAL,
                entity_type="sos",
                sender_id=reporter_id,
                metadata={
                    "reporter_name": reporter_name,
                    "location": location,
                    "gps_coordinates": gps_coordinates,
                },
                channels=[
                    NotificationChannel.IN_APP,
                    NotificationChannel.SMS,
                    NotificationChannel.EMAIL,
                    NotificationChannel.PUSH,
                ],
            )
            notifications.append(notification)

        return notifications

    async def send_riddor_alert(
        self,
        incident_id: str,
        incident_type: str,
        location: str,
        compliance_team_ids: List[int],
    ) -> List[Notification]:
        """Send RIDDOR-reportable incident alert to compliance team"""
        message = f"""
⚠️ RIDDOR REPORTABLE INCIDENT

Incident ID: {incident_id}
Type: {incident_type}
Location: {location}

This incident must be reported to HSE within statutory timeframes.

Please review and submit RIDDOR report immediately.
        """.strip()

        notifications = []

        for user_id in compliance_team_ids:
            notification = await self.create_notification(
                user_id=user_id,
                notification_type=NotificationType.RIDDOR_INCIDENT,
                title="⚠️ RIDDOR Reportable Incident",
                message=message,
                priority=NotificationPriority.CRITICAL,
                entity_type="incident",
                entity_id=incident_id,
                action_url=f"/incidents/{incident_id}",
                channels=[
                    NotificationChannel.IN_APP,
                    NotificationChannel.SMS,
                    NotificationChannel.EMAIL,
                ],
            )
            notifications.append(notification)

        return notifications


# Singleton instance
notification_service = NotificationService()
