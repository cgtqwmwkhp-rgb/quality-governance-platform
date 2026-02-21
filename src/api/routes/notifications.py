"""
Notification API Routes

Features:
- List user notifications
- Mark as read
- Notification preferences
- Mention search
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, update

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.notification import (
    DeleteNotificationResponse,
    MarkAllReadResponse,
    MarkNotificationReadResponse,
    MarkNotificationUnreadResponse,
    NotificationPreferencesResponse,
    TestNotificationResponse,
    UnreadCountResponse,
    UpdatePreferencesResponse,
)
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.notification import Notification, NotificationPreference, NotificationPriority, NotificationType
from src.domain.models.user import User
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

try:
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter()


# ============================================================================
# SCHEMAS
# ============================================================================


class NotificationResponse(BaseModel):
    """Notification response schema"""

    id: int
    type: str
    priority: str
    title: str
    message: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    action_url: Optional[str] = None
    sender_id: Optional[int] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Paginated notification list"""

    items: List[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int


class NotificationPreferencesUpdate(BaseModel):
    """Update notification preferences"""

    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    phone_number: Optional[str] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    email_digest_enabled: Optional[bool] = None
    email_digest_frequency: Optional[str] = None


class CreateNotificationRequest(BaseModel):
    """Request to create a notification"""

    user_id: int
    type: NotificationType
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.MEDIUM
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    action_url: Optional[str] = None


class MentionSearchResult(BaseModel):
    """User mention search result"""

    id: int
    display_name: str
    email: str
    avatar_url: Optional[str] = None


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    notification_type: Optional[str] = None,
):
    """
    List notifications for the current user.

    Supports filtering by read status and notification type.
    Tenant scoping is implicit through user ownership (user_id).
    """
    query = select(Notification).where(Notification.user_id == current_user.id)

    if unread_only:
        query = query.where(Notification.is_read == False)
    if notification_type:
        query = query.where(Notification.type == notification_type)

    unread_query = select(func.count(Notification.id)).where(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
    )
    unread_count = await db.scalar(unread_query) or 0

    query = query.order_by(Notification.created_at.desc())
    params = PaginationParams(page=page, page_size=page_size)
    paginated = await paginate(db, query, params)

    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in paginated.items],
        total=paginated.total,
        unread_count=unread_count,
        page=paginated.page,
        page_size=paginated.page_size,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(db: DbSession, current_user: CurrentUser):
    """Get the count of unread notifications for the current user.

    Tenant scoping is implicit through user ownership (user_id).
    """
    count = (
        await db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == current_user.id,
                Notification.is_read == False,
            )
        )
        or 0
    )
    return {"unread_count": count}


@router.post("/{notification_id}/read", response_model=MarkNotificationReadResponse)
async def mark_notification_read(notification_id: int, db: DbSession, current_user: CurrentUser):
    """Mark a specific notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    notification.is_read = True
    notification.read_at = datetime.utcnow()
    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "notifications")
    track_metric("notification.mutation", 1)
    return {"success": True, "notification_id": notification_id}


@router.post("/{notification_id}/unread", response_model=MarkNotificationUnreadResponse)
async def mark_notification_unread(notification_id: int, db: DbSession, current_user: CurrentUser):
    """Mark a specific notification as unread."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    notification.is_read = False
    notification.read_at = None
    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "notifications")
    track_metric("notification.mutation", 1)
    return {"success": True, "notification_id": notification_id}


@router.post("/read-all", response_model=MarkAllReadResponse)
async def mark_all_notifications_read(db: DbSession, current_user: CurrentUser):
    """Mark all notifications as read for the current user."""
    _span = tracer.start_span("mark_all_notifications_read") if tracer else None
    result = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        .values(is_read=True, read_at=datetime.utcnow())
    )
    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "notifications")
    track_metric("notification.mutation", 1)
    track_metric("notifications.marked_read", 1)
    if _span:
        _span.end()
    return {"success": True, "count": result.rowcount}


@router.delete("/{notification_id}", response_model=DeleteNotificationResponse)
async def delete_notification(notification_id: int, db: DbSession, current_user: CurrentSuperuser):
    """Delete a specific notification."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    await db.delete(notification)
    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "notifications")
    track_metric("notification.mutation", 1)
    return {"success": True, "notification_id": notification_id}


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(db: DbSession, current_user: CurrentUser):
    """Get notification preferences for the current user."""
    result = await db.execute(select(NotificationPreference).where(NotificationPreference.user_id == current_user.id))
    prefs = result.scalar_one_or_none()

    if not prefs:
        return {
            "email_enabled": True,
            "sms_enabled": False,
            "push_enabled": True,
            "phone_number": None,
            "quiet_hours_enabled": False,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
            "email_digest_enabled": True,
            "email_digest_frequency": "daily",
            "category_preferences": {},
        }

    return {
        "email_enabled": prefs.email_enabled,
        "sms_enabled": prefs.sms_enabled,
        "push_enabled": prefs.push_enabled,
        "phone_number": prefs.phone_number,
        "quiet_hours_enabled": prefs.quiet_hours_enabled,
        "quiet_hours_start": prefs.quiet_hours_start,
        "quiet_hours_end": prefs.quiet_hours_end,
        "email_digest_enabled": prefs.email_digest_enabled,
        "email_digest_frequency": prefs.email_digest_frequency,
        "category_preferences": prefs.category_preferences or {},
    }


@router.put("/preferences", response_model=UpdatePreferencesResponse)
async def update_notification_preferences(
    preferences: NotificationPreferencesUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update notification preferences for the current user."""
    result = await db.execute(select(NotificationPreference).where(NotificationPreference.user_id == current_user.id))
    prefs = result.scalar_one_or_none()

    if not prefs:
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)

    update_data = apply_updates(prefs, preferences, set_updated_at=False)

    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "notifications")
    track_metric("notification.mutation", 1)
    return {"success": True, "preferences": update_data}


@router.get("/mentions/search", response_model=List[MentionSearchResult])
async def search_users_for_mention(
    db: DbSession,
    current_user: CurrentUser,
    q: str = Query(..., min_length=1, max_length=50),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Search users for @mention autocomplete.

    Returns active users matching the query by name or email.
    """
    search_pattern = f"%{q}%"
    result = await db.execute(
        select(User)
        .where(
            User.is_active == True,
            (User.first_name.ilike(search_pattern))
            | (User.last_name.ilike(search_pattern))
            | (User.email.ilike(search_pattern)),
        )
        .order_by(User.first_name, User.last_name)
        .limit(limit)
    )
    users = result.scalars().all()

    return [
        MentionSearchResult(
            id=u.id,
            display_name=f"{u.first_name} {u.last_name}",
            email=u.email,
            avatar_url=None,
        )
        for u in users
    ]


@router.post("/test-notification", response_model=TestNotificationResponse)
async def send_test_notification(current_user: CurrentUser):
    """
    Send a test notification to the current user.

    Useful for testing WebSocket and notification delivery.
    """
    from src.infrastructure.websocket.connection_manager import connection_manager

    await connection_manager.send_to_user(
        user_id=current_user.id,
        message={
            "id": 999,
            "type": "system_announcement",
            "priority": "low",
            "title": "Test Notification",
            "message": "This is a test notification. WebSocket is working!",
            "created_at": datetime.utcnow().isoformat(),
        },
        event_type="notification",
    )

    return {"success": True, "message": "Test notification sent"}
