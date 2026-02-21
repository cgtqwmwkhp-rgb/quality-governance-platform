"""Push Notification response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class SubscribePushNotificationResponse(BaseModel):
    success: bool
    subscription_id: int
    message: str


class UnsubscribePushNotificationResponse(BaseModel):
    success: bool
    message: str


class GetNotificationPreferencesResponse(BaseModel):
    push_enabled: bool
    email_enabled: bool
    sms_enabled: bool
    incident_alerts: bool
    action_reminders: bool
    audit_notifications: bool
    compliance_updates: bool
    mentions: bool
    digest_frequency: str
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None


class UpdateNotificationPreferencesResponse(BaseModel):
    success: bool
    message: str


class BulkSendResults(BaseModel):
    sent: int
    failed: int
    skipped: int


class SendNotificationResponse(BaseModel):
    success: bool
    results: BulkSendResults


class TestNotificationResponse(BaseModel):
    success: bool
    results: list[Any]
