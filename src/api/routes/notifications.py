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

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser
from src.domain.models.notification import NotificationPriority, NotificationType
from src.domain.services.notification_service import notification_service
from src.infrastructure.database import get_db

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
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    notification_type: Optional[str] = None,
):
    """
    List notifications for the current user.

    Supports filtering by read status and notification type.
    """
    # Parse notification type filter
    type_filter = None
    if notification_type:
        try:
            type_filter = [NotificationType(notification_type)]
        except ValueError:
            pass

    # Create service with mock data for now
    # In production, pass actual database session
    notifications = []

    # Mock notifications for demonstration
    mock_notifications = [
        NotificationResponse(
            id=1,
            type="mention",
            priority="medium",
            title="You were mentioned",
            message="John Smith mentioned you in an incident report",
            entity_type="incident",
            entity_id="INC-001",
            action_url="/incidents/INC-001",
            sender_id=2,
            is_read=False,
            created_at=datetime.utcnow(),
        ),
        NotificationResponse(
            id=2,
            type="assignment",
            priority="high",
            title="Action assigned to you",
            message="Complete risk assessment for Site A",
            entity_type="action",
            entity_id="ACT-042",
            action_url="/actions/ACT-042",
            sender_id=3,
            is_read=False,
            created_at=datetime.utcnow(),
        ),
        NotificationResponse(
            id=3,
            type="action_due_soon",
            priority="medium",
            title="Action due tomorrow",
            message="Update safety documentation - due in 24 hours",
            entity_type="action",
            entity_id="ACT-038",
            action_url="/actions/ACT-038",
            sender_id=None,
            is_read=True,
            created_at=datetime.utcnow(),
        ),
    ]

    # Filter by read status
    if unread_only:
        mock_notifications = [n for n in mock_notifications if not n.is_read]

    total = len(mock_notifications)
    unread = len([n for n in mock_notifications if not n.is_read])

    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    items = mock_notifications[start:end]

    return NotificationListResponse(
        items=items,
        total=total,
        unread_count=unread,
        page=page,
        page_size=page_size,
    )


@router.get("/unread-count")
async def get_unread_count(current_user: CurrentUser):
    """Get the count of unread notifications for the current user."""
    # Mock count for demonstration
    return {"unread_count": 5}


@router.post("/{notification_id}/read")
async def mark_notification_read(notification_id: int, current_user: CurrentUser):
    """Mark a specific notification as read."""
    # In production, update database
    return {"success": True, "notification_id": notification_id}


@router.post("/read-all")
async def mark_all_notifications_read(current_user: CurrentUser):
    """Mark all notifications as read for the current user."""
    # In production, update database
    return {"success": True, "count": 5}


@router.delete("/{notification_id}")
async def delete_notification(notification_id: int, current_user: CurrentUser):
    """Delete a specific notification."""
    return {"success": True, "notification_id": notification_id}


@router.get("/preferences")
async def get_notification_preferences(current_user: CurrentUser):
    """Get notification preferences for the current user."""
    # Mock preferences
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
        "category_preferences": {
            "mention": ["in_app", "email"],
            "assignment": ["in_app", "email", "push"],
            "sos_alert": ["in_app", "email", "sms", "push"],
            "action_due_soon": ["in_app", "email"],
        },
    }


@router.put("/preferences")
async def update_notification_preferences(preferences: NotificationPreferencesUpdate, current_user: CurrentUser):
    """Update notification preferences for the current user."""
    # In production, update database
    return {"success": True, "preferences": preferences.dict(exclude_unset=True)}


@router.get("/mentions/search", response_model=List[MentionSearchResult])
async def search_users_for_mention(
    q: str = Query(..., min_length=1, max_length=50),
    limit: int = Query(10, ge=1, le=50),
    current_user: CurrentUser = None,
):
    """
    Search users for @mention autocomplete.

    Returns users matching the query by name or email.
    """
    # Mock users for demonstration
    mock_users = [
        MentionSearchResult(
            id=1,
            display_name="John Smith",
            email="john.smith@plantexpand.com",
            avatar_url=None,
        ),
        MentionSearchResult(
            id=2,
            display_name="Jane Doe",
            email="jane.doe@plantexpand.com",
            avatar_url=None,
        ),
        MentionSearchResult(
            id=3,
            display_name="Bob Wilson",
            email="bob.wilson@plantexpand.com",
            avatar_url=None,
        ),
        MentionSearchResult(
            id=4,
            display_name="Alice Brown",
            email="alice.brown@plantexpand.com",
            avatar_url=None,
        ),
        MentionSearchResult(
            id=5,
            display_name="Charlie Davis",
            email="charlie.davis@plantexpand.com",
            avatar_url=None,
        ),
    ]

    # Filter by query
    q_lower = q.lower()
    filtered = [u for u in mock_users if q_lower in u.display_name.lower() or q_lower in u.email.lower()]

    return filtered[:limit]


@router.post("/test-notification")
async def send_test_notification(current_user: CurrentUser):
    """
    Send a test notification to the current user.

    Useful for testing WebSocket and notification delivery.
    """
    from src.infrastructure.websocket.connection_manager import connection_manager

    # Send test notification via WebSocket
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
