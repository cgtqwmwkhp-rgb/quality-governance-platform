"""
Notification and Mention Models - Real-Time Notification System

Supports:
- Real-time notifications via WebSocket
- @mentions in any content
- Assignment tracking
- Notification preferences
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, Boolean, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base


class NotificationType(str, Enum):
    """Types of notifications"""

    # Mentions
    MENTION = "mention"

    # Assignments
    ASSIGNMENT = "assignment"
    REASSIGNMENT = "reassignment"

    # Incidents
    INCIDENT_NEW = "incident_new"
    INCIDENT_UPDATE = "incident_update"
    INCIDENT_ESCALATED = "incident_escalated"

    # Actions
    ACTION_ASSIGNED = "action_assigned"
    ACTION_DUE_SOON = "action_due_soon"
    ACTION_OVERDUE = "action_overdue"
    ACTION_COMPLETED = "action_completed"

    # Audits
    AUDIT_SCHEDULED = "audit_scheduled"
    AUDIT_STARTED = "audit_started"
    AUDIT_COMPLETED = "audit_completed"
    AUDIT_FINDING = "audit_finding"

    # Approvals
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"

    # Compliance
    COMPLIANCE_ALERT = "compliance_alert"
    CERTIFICATE_EXPIRING = "certificate_expiring"
    CERTIFICATE_EXPIRED = "certificate_expired"

    # SOS/Emergency
    SOS_ALERT = "sos_alert"
    RIDDOR_INCIDENT = "riddor_incident"

    # System
    SYSTEM_ANNOUNCEMENT = "system_announcement"
    REPORT_READY = "report_ready"


class NotificationPriority(str, Enum):
    """Notification priority levels"""

    CRITICAL = "critical"  # SOS, RIDDOR - immediate
    HIGH = "high"  # Escalations, overdue
    MEDIUM = "medium"  # Assignments, updates
    LOW = "low"  # FYI, completed items


class NotificationChannel(str, Enum):
    """Delivery channels"""

    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class Notification(Base):
    """Notification model for real-time alerts"""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Recipient
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # Notification content
    type: Mapped[NotificationType] = mapped_column(SQLEnum(NotificationType), nullable=False, index=True)
    priority: Mapped[NotificationPriority] = mapped_column(
        SQLEnum(NotificationPriority),
        nullable=False,
        default=NotificationPriority.MEDIUM,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Related entity
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Action URL
    action_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Sender (if applicable)
    sender_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Additional data (JSON)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Delivery tracking
    delivered_channels: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type={self.type}, user_id={self.user_id})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for WebSocket delivery"""
        return {
            "id": self.id,
            "type": self.type.value,
            "priority": self.priority.value,
            "title": self.title,
            "message": self.message,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "action_url": self.action_url,
            "sender_id": self.sender_id,
            "metadata": self.extra_data,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Mention(Base):
    """Mention model for @mentions in content"""

    __tablename__ = "mentions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Content reference
    content_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    content_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Users involved
    mentioned_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    mentioned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Context
    mention_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Position in content
    start_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Mention(id={self.id}, user={self.mentioned_user_id}, content={self.content_type}/{self.content_id})>"


class Assignment(Base):
    """Assignment model for task/entity assignments"""

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Entity reference
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Assignment details
    assigned_to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    assigned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Due date and priority
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")

    # Status
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<Assignment(id={self.id}, entity={self.entity_type}/{self.entity_id}, user={self.assigned_to_user_id})>"
        )


class NotificationPreference(Base):
    """User notification preferences"""

    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)

    # Channel preferences
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Phone for SMS
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Quiet hours
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    quiet_hours_start: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # HH:MM
    quiet_hours_end: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)

    # Category preferences (JSON map of type -> channels)
    category_preferences: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Email digest
    email_digest_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    email_digest_frequency: Mapped[str] = mapped_column(String(20), default="daily")

    # Timestamps
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<NotificationPreference(user_id={self.user_id})>"
