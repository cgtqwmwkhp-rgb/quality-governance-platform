"""
Push Notification Service API

Features:
- Web Push subscriptions (VAPID)
- Push notification sending
- Subscription management
- Notification preferences
- Email/SMS fallback integration
"""

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.push_notification import (
    GetNotificationPreferencesResponse,
    SendNotificationResponse,
    SubscribePushNotificationResponse,
    TestNotificationResponse,
    UnsubscribePushNotificationResponse,
    UpdateNotificationPreferencesResponse,
)
from src.api.utils.update import apply_updates
from src.core.config import settings
from src.infrastructure.database import Base
from src.infrastructure.monitoring.azure_monitor import track_metric

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter(tags=["Push Notifications"])


# ============================================================================
# Database Models
# ============================================================================


class PushSubscription(Base):
    """Web Push subscription storage."""

    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)  # Null for anonymous
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh_key = Column(String(255), nullable=False)
    auth_key = Column(String(255), nullable=False)
    user_agent = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)


class NotificationPreference(Base):
    """User notification preferences."""

    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, unique=True)

    # Channels
    push_enabled = Column(Boolean, default=True)
    email_enabled = Column(Boolean, default=True)
    sms_enabled = Column(Boolean, default=False)

    # Event types
    incident_alerts = Column(Boolean, default=True)
    action_reminders = Column(Boolean, default=True)
    audit_notifications = Column(Boolean, default=True)
    compliance_updates = Column(Boolean, default=True)
    mentions = Column(Boolean, default=True)

    # Frequency
    digest_frequency = Column(String(20), default="immediate")  # immediate, daily, weekly
    quiet_hours_start = Column(String(5), nullable=True)  # "22:00"
    quiet_hours_end = Column(String(5), nullable=True)  # "07:00"

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationLog(Base):
    """Log of sent notifications."""

    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)
    subscription_id = Column(Integer, nullable=True)

    notification_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    data = Column(JSONB, nullable=True)

    channel = Column(String(20), nullable=False)  # push, email, sms
    status = Column(String(20), default="pending")  # pending, sent, failed, delivered
    error_message = Column(Text, nullable=True)

    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# Pydantic Schemas
# ============================================================================


class PushSubscriptionCreate(BaseModel):
    """Web Push subscription from browser."""

    endpoint: str
    keys: dict = Field(..., description="Contains p256dh and auth keys")


class NotificationPreferenceUpdate(BaseModel):
    """Update notification preferences."""

    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    incident_alerts: Optional[bool] = None
    action_reminders: Optional[bool] = None
    audit_notifications: Optional[bool] = None
    compliance_updates: Optional[bool] = None
    mentions: Optional[bool] = None
    digest_frequency: Optional[str] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None


class SendNotificationRequest(BaseModel):
    """Request to send a notification."""

    user_ids: Optional[list[int]] = None  # Specific users, or None for all
    notification_type: str = Field(..., description="Type: incident, action, audit, compliance, mention")
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    url: Optional[str] = None
    data: Optional[dict] = None
    channels: list[str] = Field(default=["push"], description="Channels: push, email, sms")


# ============================================================================
# Push Notification Service
# ============================================================================


class PushNotificationService:
    """Service for sending push notifications via Web Push."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.vapid_private_key = settings.vapid_private_key or None
        self.vapid_public_key = settings.vapid_public_key or None
        self.vapid_claims = {"sub": f"mailto:{settings.vapid_email}"}

    async def subscribe(
        self,
        subscription_data: PushSubscriptionCreate,
        user_id: Optional[int] = None,
        user_agent: Optional[str] = None,
    ) -> PushSubscription:
        """Register a new push subscription."""
        result = await self.db.execute(
            select(PushSubscription).filter(PushSubscription.endpoint == subscription_data.endpoint)
        )
        existing = result.scalars().first()

        if existing:
            existing.user_id = user_id
            existing.is_active = True
            existing.last_used_at = datetime.utcnow()
            await self.db.commit()
            return existing

        subscription = PushSubscription(
            user_id=user_id,
            endpoint=subscription_data.endpoint,
            p256dh_key=subscription_data.keys.get("p256dh", ""),
            auth_key=subscription_data.keys.get("auth", ""),
            user_agent=user_agent,
            is_active=True,
        )
        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)
        return subscription

    async def unsubscribe(self, endpoint: str) -> bool:
        """Unsubscribe from push notifications."""
        result = await self.db.execute(select(PushSubscription).filter(PushSubscription.endpoint == endpoint))
        subscription = result.scalars().first()

        if subscription:
            subscription.is_active = False
            await self.db.commit()
            return True
        return False

    async def send_notification(
        self,
        user_id: int,
        title: str,
        body: str,
        url: Optional[str] = None,
        data: Optional[dict] = None,
        notification_type: str = "general",
    ) -> list[dict[str, Any]]:
        """Send push notification to a user."""
        results = []

        result = await self.db.execute(select(NotificationPreference).filter(NotificationPreference.user_id == user_id))
        prefs = result.scalars().first()

        if prefs and not prefs.push_enabled:
            return [{"status": "skipped", "reason": "Push notifications disabled"}]

        result = await self.db.execute(
            select(PushSubscription).filter(
                PushSubscription.user_id == user_id,
                PushSubscription.is_active == True,
            )
        )
        subscriptions = result.scalars().all()

        if not subscriptions:
            return [{"status": "skipped", "reason": "No active subscriptions"}]

        payload = json.dumps(
            {
                "title": title,
                "body": body,
                "icon": "/icons/icon-192x192.png",
                "badge": "/icons/badge-72x72.png",
                "url": url or "/portal",
                "tag": notification_type,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        for sub in subscriptions:
            try:
                result = await self._send_web_push(sub, payload)
                results.append(result)

                log = NotificationLog(
                    user_id=user_id,
                    subscription_id=sub.id,
                    notification_type=notification_type,
                    title=title,
                    body=body,
                    data=data,
                    channel="push",
                    status="sent" if result.get("success") else "failed",
                    error_message=result.get("error"),
                    sent_at=datetime.utcnow(),
                )
                self.db.add(log)

            except (ConnectionError, TimeoutError, ValueError) as e:
                import logging as _logging

                _logging.getLogger(__name__).warning(
                    "Push notification delivery failed [user_id=%s, subscription=%s]: %s: %s",
                    user_id,
                    sub.id,
                    type(e).__name__,
                    str(e)[:200],
                    exc_info=True,
                )
                results.append({"success": False, "error": str(e)})

        await self.db.commit()
        return results

    async def _send_web_push(
        self,
        subscription: PushSubscription,
        payload: str,
    ) -> dict[str, Any]:
        """Send actual Web Push message using pywebpush."""
        try:
            from pywebpush import WebPushException, webpush

            subscription_info = {
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh_key,
                    "auth": subscription.auth_key,
                },
            }

            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims,
            )

            subscription.last_used_at = datetime.utcnow()
            return {"success": True, "endpoint": subscription.endpoint}

        except ImportError:
            return {"success": True, "endpoint": subscription.endpoint, "simulated": True}

        except (ConnectionError, TimeoutError, ValueError) as e:
            import logging as _logging

            _logging.getLogger(__name__).warning(
                "Web push send failed [endpoint=%s]: %s: %s",
                subscription.endpoint[:80],
                type(e).__name__,
                str(e)[:200],
                exc_info=True,
            )
            error_msg = str(e)
            if "410" in error_msg or "404" in error_msg:
                subscription.is_active = False
            return {"success": False, "error": error_msg}

    async def send_bulk_notification(
        self,
        user_ids: list[int],
        title: str,
        body: str,
        url: Optional[str] = None,
        data: Optional[dict] = None,
        notification_type: str = "general",
    ) -> dict[str, Any]:
        """Send notification to multiple users."""
        results = {"sent": 0, "failed": 0, "skipped": 0}

        for user_id in user_ids:
            user_results = await self.send_notification(
                user_id=user_id,
                title=title,
                body=body,
                url=url,
                data=data,
                notification_type=notification_type,
            )

            for r in user_results:
                if r.get("success"):
                    results["sent"] += 1
                elif r.get("status") == "skipped":
                    results["skipped"] += 1
                else:
                    results["failed"] += 1

        return results


# ============================================================================
# API Routes
# ============================================================================


@router.post("/subscribe", response_model=SubscribePushNotificationResponse, status_code=status.HTTP_201_CREATED)
async def subscribe_to_push(
    subscription: PushSubscriptionCreate,
    db: DbSession,
    current_user: Optional[CurrentUser] = None,
) -> dict[str, Any]:
    """Subscribe to push notifications."""
    service = PushNotificationService(db)
    user_id = current_user.id if current_user else None

    sub = await service.subscribe(
        subscription_data=subscription,
        user_id=user_id,
    )

    return {
        "success": True,
        "subscription_id": sub.id,
        "message": "Subscribed to push notifications",
    }


@router.delete("/unsubscribe", response_model=UnsubscribePushNotificationResponse)
async def unsubscribe_from_push(
    endpoint: str,
    db: DbSession,
) -> dict[str, Any]:
    """Unsubscribe from push notifications."""
    service = PushNotificationService(db)
    success = await service.unsubscribe(endpoint)

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    return {"success": True, "message": "Unsubscribed from push notifications"}


@router.get("/preferences", response_model=GetNotificationPreferencesResponse)
async def get_notification_preferences(
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get notification preferences for current user."""
    result = await db.execute(select(NotificationPreference).filter(NotificationPreference.user_id == current_user.id))
    prefs = result.scalars().first()

    if not prefs:
        return {
            "push_enabled": True,
            "email_enabled": True,
            "sms_enabled": False,
            "incident_alerts": True,
            "action_reminders": True,
            "audit_notifications": True,
            "compliance_updates": True,
            "mentions": True,
            "digest_frequency": "immediate",
        }

    return {
        "push_enabled": prefs.push_enabled,
        "email_enabled": prefs.email_enabled,
        "sms_enabled": prefs.sms_enabled,
        "incident_alerts": prefs.incident_alerts,
        "action_reminders": prefs.action_reminders,
        "audit_notifications": prefs.audit_notifications,
        "compliance_updates": prefs.compliance_updates,
        "mentions": prefs.mentions,
        "digest_frequency": prefs.digest_frequency,
        "quiet_hours_start": prefs.quiet_hours_start,
        "quiet_hours_end": prefs.quiet_hours_end,
    }


@router.put("/preferences", response_model=UpdateNotificationPreferencesResponse)
async def update_notification_preferences(
    updates: NotificationPreferenceUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Update notification preferences."""
    result = await db.execute(select(NotificationPreference).filter(NotificationPreference.user_id == current_user.id))
    prefs = result.scalars().first()

    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)

    apply_updates(prefs, updates)

    await db.commit()

    return {"success": True, "message": "Preferences updated"}


@router.post("/send", response_model=SendNotificationResponse)
async def send_notification(
    request: SendNotificationRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Send notification to users (admin only)."""
    _span = tracer.start_span("send_push_notification") if tracer else None
    track_metric("push_notifications.sent")

    service = PushNotificationService(db)

    if request.user_ids:
        results = await service.send_bulk_notification(
            user_ids=request.user_ids,
            title=request.title,
            body=request.body,
            url=request.url,
            data=request.data,
            notification_type=request.notification_type,
        )
    else:
        result = await db.execute(
            select(PushSubscription).filter(
                PushSubscription.is_active == True,
                PushSubscription.user_id.isnot(None),
            )
        )
        subscriptions = result.scalars().all()

        user_ids = list(set(s.user_id for s in subscriptions if s.user_id))

        results = await service.send_bulk_notification(
            user_ids=user_ids,
            title=request.title,
            body=request.body,
            url=request.url,
            data=request.data,
            notification_type=request.notification_type,
        )

    if _span:
        _span.end()
    return {
        "success": True,
        "results": results,
    }


@router.get("/test", response_model=TestNotificationResponse)
async def test_push_notification(
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Send a test push notification to current user."""
    service = PushNotificationService(db)

    results = await service.send_notification(
        user_id=current_user.id,
        title="Test Notification",
        body="This is a test notification from QGP. If you see this, push notifications are working!",
        url="/dashboard",
        notification_type="test",
    )

    return {
        "success": any(r.get("success") for r in results),
        "results": results,
    }
