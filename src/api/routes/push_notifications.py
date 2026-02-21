"""Push Notification API routes.

Thin controller layer — all business logic lives in PushNotificationServiceDomain.
DB models and request schemas remain here as they are route-level definitions.
"""

from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, select
from sqlalchemy.dialects.postgresql import JSONB

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.push_notification import (
    GetNotificationPreferencesResponse,
    SendNotificationResponse,
    SubscribePushNotificationResponse,
    TestNotificationResponse,
    UnsubscribePushNotificationResponse,
    UpdateNotificationPreferencesResponse,
)
from src.domain.models.user import User
from src.domain.services.push_notification_service import PushNotificationServiceDomain
from src.infrastructure.database import Base
from src.infrastructure.monitoring.azure_monitor import track_metric

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter(tags=["Push Notifications"])


# ============================================================================
# Database Models (kept here — tightly coupled to this feature)
# ============================================================================


class PushSubscription(Base):
    """Web Push subscription storage."""

    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)
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

    push_enabled = Column(Boolean, default=True)
    email_enabled = Column(Boolean, default=True)
    sms_enabled = Column(Boolean, default=False)

    incident_alerts = Column(Boolean, default=True)
    action_reminders = Column(Boolean, default=True)
    audit_notifications = Column(Boolean, default=True)
    compliance_updates = Column(Boolean, default=True)
    mentions = Column(Boolean, default=True)

    digest_frequency = Column(String(20), default="immediate")
    quiet_hours_start = Column(String(5), nullable=True)
    quiet_hours_end = Column(String(5), nullable=True)

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

    channel = Column(String(20), nullable=False)
    status = Column(String(20), default="pending")
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

    user_ids: Optional[list[int]] = None
    notification_type: str = Field(..., description="Type: incident, action, audit, compliance, mention")
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    url: Optional[str] = None
    data: Optional[dict] = None
    channels: list[str] = Field(default=["push"], description="Channels: push, email, sms")


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
    service = PushNotificationServiceDomain(db)
    user_id = current_user.id if current_user else None
    return await service.subscribe(subscription_data=subscription, user_id=user_id)


@router.delete("/unsubscribe", response_model=UnsubscribePushNotificationResponse)
async def unsubscribe_from_push(
    endpoint: str,
    db: DbSession,
) -> dict[str, Any]:
    """Unsubscribe from push notifications."""
    service = PushNotificationServiceDomain(db)
    try:
        await service.unsubscribe(endpoint)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return {"success": True, "message": "Unsubscribed from push notifications"}


@router.get("/preferences", response_model=GetNotificationPreferencesResponse)
async def get_notification_preferences(
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get notification preferences for current user."""
    service = PushNotificationServiceDomain(db)
    return await service.get_preferences(current_user.id)


@router.put("/preferences", response_model=UpdateNotificationPreferencesResponse)
async def update_notification_preferences(
    updates: NotificationPreferenceUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("notification:update"))],
) -> dict[str, Any]:
    """Update notification preferences."""
    service = PushNotificationServiceDomain(db)
    return await service.update_preferences(current_user.id, updates)


@router.post("/send", response_model=SendNotificationResponse)
async def send_notification(
    request: SendNotificationRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("notification:create"))],
) -> dict[str, Any]:
    """Send notification to users (admin only)."""
    _span = tracer.start_span("send_push_notification") if tracer else None
    track_metric("push_notifications.sent")

    service = PushNotificationServiceDomain(db)

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
        results = await service.send_to_all(
            title=request.title,
            body=request.body,
            url=request.url,
            data=request.data,
            notification_type=request.notification_type,
        )

    if _span:
        _span.end()
    return {"success": True, "results": results}


@router.get("/test", response_model=TestNotificationResponse)
async def test_push_notification(
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Send a test push notification to current user."""
    service = PushNotificationServiceDomain(db)
    return await service.send_test(current_user.id)
