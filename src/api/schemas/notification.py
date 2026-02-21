"""Notification API response schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

# ============================================================================
# Read / Unread
# ============================================================================


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkNotificationReadResponse(BaseModel):
    success: bool
    notification_id: int


class MarkNotificationUnreadResponse(BaseModel):
    success: bool
    notification_id: int


class MarkAllReadResponse(BaseModel):
    success: bool
    count: int


class DeleteNotificationResponse(BaseModel):
    success: bool
    notification_id: int


# ============================================================================
# Preferences
# ============================================================================


class NotificationPreferencesResponse(BaseModel):
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    phone_number: Optional[str] = None
    quiet_hours_enabled: bool
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    email_digest_enabled: bool
    email_digest_frequency: Optional[str] = None
    category_preferences: dict[str, Any] = {}


class UpdatePreferencesResponse(BaseModel):
    success: bool
    preferences: dict[str, Any] = {}


# ============================================================================
# Test
# ============================================================================


class TestNotificationResponse(BaseModel):
    success: bool
    message: str
