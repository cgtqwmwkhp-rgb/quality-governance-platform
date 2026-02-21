"""Notification API Routes — thin controller layer."""

from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession, require_permission
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
from src.domain.models.notification import NotificationPriority, NotificationType
from src.domain.models.user import User
from src.domain.services.notification_service import NotificationService
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
    """List notifications for the current user."""
    service = NotificationService(db)
    result = await service.list_notifications(
        current_user.id,
        page=page,
        page_size=page_size,
        unread_only=unread_only,
        notification_type=notification_type,
    )
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in result["items"]],
        total=result["total"],
        unread_count=result["unread_count"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(db: DbSession, current_user: CurrentUser):
    """Get the count of unread notifications for the current user."""
    service = NotificationService(db)
    count = await service.get_unread_count(current_user.id)
    return {"unread_count": count}


@router.post("/{notification_id}/read", response_model=MarkNotificationReadResponse)
async def mark_notification_read(
    notification_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("notification:update"))],
):
    """Mark a specific notification as read."""
    service = NotificationService(db)
    try:
        await service.mark_as_read(notification_id, current_user.id)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)
    await invalidate_tenant_cache(current_user.tenant_id, "notifications")
    track_metric("notification.mutation", 1)
    return {"success": True, "notification_id": notification_id}


@router.post("/{notification_id}/unread", response_model=MarkNotificationUnreadResponse)
async def mark_notification_unread(
    notification_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("notification:update"))],
):
    """Mark a specific notification as unread."""
    service = NotificationService(db)
    try:
        await service.mark_as_unread(notification_id, current_user.id)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)
    await invalidate_tenant_cache(current_user.tenant_id, "notifications")
    track_metric("notification.mutation", 1)
    return {"success": True, "notification_id": notification_id}


@router.post("/read-all", response_model=MarkAllReadResponse)
async def mark_all_notifications_read(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("notification:update"))],
):
    """Mark all notifications as read for the current user."""
    _span = tracer.start_span("mark_all_notifications_read") if tracer else None
    service = NotificationService(db)
    count = await service.mark_all_as_read(current_user.id)
    await invalidate_tenant_cache(current_user.tenant_id, "notifications")
    track_metric("notification.mutation", 1)
    track_metric("notifications.marked_read", 1)
    if _span:
        _span.end()
    return {"success": True, "count": count}


@router.delete("/{notification_id}", response_model=DeleteNotificationResponse)
async def delete_notification(
    notification_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
):
    """Delete a specific notification."""
    service = NotificationService(db)
    try:
        await service.delete_notification(notification_id, current_user.id)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)
    await invalidate_tenant_cache(current_user.tenant_id, "notifications")
    track_metric("notification.mutation", 1)
    return {"success": True, "notification_id": notification_id}


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(db: DbSession, current_user: CurrentUser):
    """Get notification preferences for the current user."""
    service = NotificationService(db)
    return await service.get_preferences(current_user.id)


@router.put("/preferences", response_model=UpdatePreferencesResponse)
async def update_notification_preferences(
    preferences: NotificationPreferencesUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("notification:update"))],
):
    """Update notification preferences for the current user."""
    service = NotificationService(db)
    update_data = await service.update_preferences(current_user.id, preferences)
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
    """Search users for @mention autocomplete."""
    service = NotificationService(db)
    results = await service.search_mentionable_users(q, limit)
    return [MentionSearchResult(**r) for r in results]


@router.post("/test-notification", response_model=TestNotificationResponse)
async def send_test_notification(
    current_user: Annotated[User, Depends(require_permission("notification:create"))],
):
    """Send a test notification to the current user."""
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
