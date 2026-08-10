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

import html
import logging
import re
from datetime import datetime, timezone
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
from src.domain.services.href_registry import absolute_href, assessment_run_href, induction_run_href
from src.domain.services.notification_preferences import (
    DEFAULT_QUIET_HOURS_TIMEZONE,
    ChannelDecision,
    PreferenceSnapshot,
    filter_channels,
)
from src.infrastructure.websocket.connection_manager import connection_manager

logger = logging.getLogger(__name__)


# Mention regex pattern: @[username] or @username
MENTION_PATTERN = re.compile(r"@\[([^\]]+)\]|@(\w+)")


def render_notification_email_html(
    message: str,
    action_url: str | None = None,
    *,
    cta_label: str = "Open in QGP",
) -> str:
    """Build HTML email body: escaped message + optional absolute deep-link CTA.

    ``action_url`` may be SPA-relative (``/compliance-schedule/3``); only a
    resolved ``http(s)`` absolute URL yields an ``<a href>``.
    """
    escaped = html.escape(message or "", quote=False)
    parts = [
        '<div style="white-space:pre-wrap;font-family:sans-serif;' f'font-size:14px;line-height:1.5">{escaped}</div>'
    ]
    absolute = absolute_href(action_url)
    if absolute:
        href = html.escape(absolute, quote=True)
        label = html.escape(cta_label, quote=False)
        parts.append(f'<p style="margin-top:16px"><a href="{href}">{label}</a></p>')
    return "\n".join(parts)


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
        tenant_id: Optional[int] = None,
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
            channels: Requested channels; still subject to category preferences
                and quiet hours (FR-NOTIF-ADMIN-03)
            tenant_id: Tenant scope for the notification row

        Returns:
            Created Notification object
        """
        # Resolve delivery before the insert: extra_data is a plain JSON column,
        # so the suppression audit trail has to be present at construction time
        # rather than mutated in afterwards.
        decision = await self._resolve_delivery_channels(user_id, notification_type, priority, channels)
        delivery_channels = decision.allowed

        extra_data: Dict[str, Any] = dict(metadata or {})
        if decision.has_suppressions:
            extra_data["suppressed_channels"] = dict(decision.suppressed)
            logger.info(
                "Notification preferences suppressed channels for user %s (%s): %s",
                user_id,
                notification_type.value,
                decision.suppressed,
            )

        # Create notification record
        notification = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            type=notification_type,
            priority=priority,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            action_url=action_url,
            sender_id=sender_id,
            extra_data=extra_data,
            delivered_channels=[],
        )

        if self.db:
            self.db.add(notification)
            await self.db.commit()
            await self.db.refresh(notification)

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
                logger.error(f"Failed to deliver via {channel}: {e}", exc_info=True)
                if notification.extra_data is None:
                    notification.extra_data = {}
                notification.extra_data.setdefault("failed_channels", []).append(channel.value)

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

    async def _load_preferences(self, user_id: int) -> Optional[NotificationPreference]:
        """Load a user's stored notification preferences, if any."""
        if not self.db:
            return None
        result = await self.db.execute(select(NotificationPreference).where(NotificationPreference.user_id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    def _channels_from_toggles(
        prefs: Optional[NotificationPreference],
        priority: NotificationPriority,
    ) -> List[NotificationChannel]:
        """Channels the user's top-level channel toggles opt them in to."""
        channels = [NotificationChannel.IN_APP]  # Always in-app

        # Critical notifications always go to all channels
        if priority == NotificationPriority.CRITICAL:
            channels.extend(
                [
                    NotificationChannel.EMAIL,
                    NotificationChannel.SMS,
                    NotificationChannel.PUSH,
                ]
            )
            return channels

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

    async def _resolve_delivery_channels(
        self,
        user_id: int,
        notification_type: NotificationType,
        priority: NotificationPriority,
        requested: Optional[List[NotificationChannel]] = None,
    ) -> ChannelDecision:
        """Resolve the channels a notification may actually use.

        Category preferences and quiet hours are applied to caller-supplied
        ``requested`` channels as well as to channels derived from the user's
        toggles. Callers pass explicit channels to say which channels a message
        *suits* (in-app only for a status change, for example), not to claim the
        user consented to being interrupted on them.
        """
        prefs = await self._load_preferences(user_id)
        base_channels = requested if requested else self._channels_from_toggles(prefs, priority)
        return filter_channels(
            base_channels,
            snapshot=PreferenceSnapshot.from_row(prefs),
            notification_type=notification_type,
            priority=priority,
            tz_name=self._quiet_hours_timezone(),
        )

    @staticmethod
    def _quiet_hours_timezone() -> Optional[str]:
        """Deployment-wide timezone for interpreting stored quiet-hours bounds."""
        try:
            from src.core.config import get_settings

            return get_settings().notification_quiet_hours_timezone
        except Exception:  # pragma: no cover - settings must never break dispatch
            logger.debug("Could not read quiet-hours timezone from settings; using module default")
            return DEFAULT_QUIET_HOURS_TIMEZONE

    async def _get_delivery_channels(
        self,
        user_id: int,
        notification_type: NotificationType,
        priority: NotificationPriority,
    ) -> List[NotificationChannel]:
        """Determine which channels to use based on preferences"""
        decision = await self._resolve_delivery_channels(user_id, notification_type, priority)
        return decision.allowed

    async def _deliver_in_app(self, notification: Notification):
        """Deliver notification via WebSocket"""
        await connection_manager.send_to_user(
            user_id=notification.user_id,
            message=notification.to_dict(),
            event_type="notification",
        )
        logger.debug(f"In-app notification sent to user {notification.user_id}")

    async def _deliver_email(self, notification: Notification):
        """Deliver notification via email (dispatched to Celery task)."""
        from src.domain.models.user import User
        from src.infrastructure.tasks.email_tasks import send_email

        if not self.db:
            raise RuntimeError(f"Cannot deliver email for user {notification.user_id}: no database session")

        result = await self.db.execute(select(User).where(User.id == notification.user_id))
        user = result.scalar_one_or_none()
        recipient = (user.email if user else None) or None
        if not recipient:
            raise ValueError(f"Cannot deliver email for user {notification.user_id}: missing recipient email")

        html_body = render_notification_email_html(
            notification.message or "",
            getattr(notification, "action_url", None),
        )
        try:
            send_email.delay(
                recipient,
                notification.title,
                html_body,
                True,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to enqueue email for user {notification.user_id}: {exc}") from exc

        logger.info("Email notification dispatched for user %d", notification.user_id)

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
                sms_result = await self.sms_service.send_sms(
                    to=prefs.phone_number,
                    message=f"{notification.title}\n\n{notification.message}",
                )
                if sms_result.success:
                    logger.info("SMS sent to user %s", notification.user_id)
                else:
                    error = sms_result.error_message or "SMS delivery failed"
                    logger.warning(
                        "SMS delivery failed for user %s: %s",
                        notification.user_id,
                        error,
                    )
                    raise RuntimeError(f"SMS delivery failed for user {notification.user_id}: {error}")

    async def _deliver_push(self, notification: Notification):
        """Deliver notification via Web Push (dispatched to Celery task)."""
        from src.infrastructure.tasks.notification_tasks import send_push_notification

        send_push_notification.delay(
            user_id=notification.user_id,
            title=notification.title,
            body=notification.message,
            data={"type": notification.type, "id": notification.id},
        )
        logger.info("Push notification dispatched for user %d", notification.user_id)

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

    async def create_status(
        self,
        *,
        user_id: int,
        entity_type: str,
        entity_id: str,
        to_status: str,
        title: str,
        message: str,
        from_status: Optional[str] = None,
        sender_id: Optional[int] = None,
        action_url: Optional[str] = None,
        notification_type: NotificationType = NotificationType.ACTION_COMPLETED,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
    ) -> Notification:
        """Notify a user that an entity status changed (in-app; SMTP optional elsewhere)."""
        return await self.create_notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=str(entity_id),
            action_url=action_url,
            sender_id=sender_id,
            priority=priority,
            metadata={
                "from_status": from_status,
                "to_status": to_status,
            },
            channels=[NotificationChannel.IN_APP],
        )

    # ==================== Workforce Governance Dispatchers ====================
    #
    # Engineer-directed notifications deliberately carry no ``action_url``: every
    # ``/workforce/**`` SPA route is gated by ``RequireRole(['admin','supervisor'])``,
    # so a deep link would silently bounce an engineer back to ``/dashboard``.

    ASSESSMENT_OUTCOME_MESSAGES = {
        "pass": "Your competency assessment has been marked as PASS.",
        "fail": "Your competency assessment has been marked as FAIL. CAPA actions will be generated.",
        "conditional": "Your competency assessment has been marked as CONDITIONAL. Follow-up required.",
    }

    async def notify_assessment_complete(
        self,
        assessment_run_id: str,
        engineer_user_id: Optional[int],
        supervisor_id: int,
        outcome: str,
        tenant_id: Optional[int] = None,
    ) -> List[Notification]:
        """Notify the engineer and supervisor that a competency assessment completed."""
        metadata = {"notification_type": "assessment_complete", "outcome": outcome}
        created: List[Notification] = []

        if engineer_user_id is not None:
            created.append(
                await self.create_notification(
                    user_id=engineer_user_id,
                    notification_type=NotificationType.AUDIT_COMPLETED,
                    title="Assessment Complete",
                    message=self.ASSESSMENT_OUTCOME_MESSAGES.get(
                        outcome, f"Assessment completed with outcome: {outcome}"
                    ),
                    priority=NotificationPriority.MEDIUM,
                    entity_type="assessment",
                    entity_id=assessment_run_id,
                    metadata=dict(metadata),
                    tenant_id=tenant_id,
                )
            )

        created.append(
            await self.create_notification(
                user_id=supervisor_id,
                notification_type=NotificationType.AUDIT_COMPLETED,
                title="Assessment Submitted",
                message=f"Assessment {assessment_run_id} completed with outcome: {outcome}",
                priority=NotificationPriority.MEDIUM,
                entity_type="assessment",
                entity_id=assessment_run_id,
                action_url=assessment_run_href(assessment_run_id),
                metadata=dict(metadata),
                tenant_id=tenant_id,
            )
        )

        logger.info("Notifications created for assessment %s", assessment_run_id)
        return created

    async def notify_induction_complete(
        self,
        induction_run_id: str,
        engineer_user_id: Optional[int],
        supervisor_id: int,
        not_yet_competent_count: int,
        tenant_id: Optional[int] = None,
    ) -> List[Notification]:
        """Notify the engineer and supervisor that an induction completed."""
        metadata = {
            "notification_type": "induction_complete",
            "not_yet_competent_count": not_yet_competent_count,
        }
        created: List[Notification] = []

        if engineer_user_id is not None:
            if not_yet_competent_count > 0:
                engineer_message = (
                    f"Your induction has been completed with {not_yet_competent_count} item(s) marked as "
                    "'Not Yet Competent'. CAPA actions will be generated."
                )
            else:
                engineer_message = "Congratulations! Your induction has been completed successfully."
            created.append(
                await self.create_notification(
                    user_id=engineer_user_id,
                    notification_type=NotificationType.COMPLIANCE_ALERT,
                    title="Induction Complete",
                    message=engineer_message,
                    priority=NotificationPriority.MEDIUM,
                    entity_type="induction",
                    entity_id=induction_run_id,
                    metadata=dict(metadata),
                    tenant_id=tenant_id,
                )
            )

        if not_yet_competent_count > 0:
            supervisor_message = (
                f"Induction {induction_run_id} completed with {not_yet_competent_count} item(s) marked as "
                "'Not Yet Competent'."
            )
        else:
            supervisor_message = f"Induction {induction_run_id} completed successfully."

        created.append(
            await self.create_notification(
                user_id=supervisor_id,
                notification_type=NotificationType.COMPLIANCE_ALERT,
                title="Induction Submitted",
                message=supervisor_message,
                priority=NotificationPriority.MEDIUM,
                entity_type="induction",
                entity_id=induction_run_id,
                action_url=induction_run_href(induction_run_id),
                metadata=dict(metadata),
                tenant_id=tenant_id,
            )
        )

        logger.info("Notification created for induction %s", induction_run_id)
        return created

    async def notify_competency_expiry(
        self,
        engineer_user_id: Optional[int],
        asset_type_id: int,
        days_until_expiry: int,
        tenant_id: Optional[int] = None,
    ) -> Optional[Notification]:
        """Warn an engineer that a competency is about to expire."""
        if engineer_user_id is None:
            return None

        return await self.create_notification(
            user_id=engineer_user_id,
            notification_type=NotificationType.CERTIFICATE_EXPIRING,
            title="Competency Expiring Soon",
            message=(
                f"Your competency for asset type {asset_type_id} expires in "
                f"{days_until_expiry} days. Please schedule a reassessment."
            ),
            priority=NotificationPriority.MEDIUM,
            entity_type="competency",
            entity_id=str(asset_type_id),
            metadata={"notification_type": "competency_expiry_warning"},
            tenant_id=tenant_id,
        )

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
            notification.read_at = datetime.now(timezone.utc)
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

        now = datetime.now(timezone.utc)
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

Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

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
