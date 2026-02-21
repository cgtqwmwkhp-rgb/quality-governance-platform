"""Policy Acknowledgment Models.

Provides read/acknowledgment tracking for policies and documents,
ensuring compliance with regulatory requirements.
"""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import TimestampMixin
from src.infrastructure.database import Base


class AcknowledgmentType(str, enum.Enum):
    """Type of acknowledgment required."""

    READ_ONLY = "read_only"  # Just need to confirm they've read it
    ACCEPT = "accept"  # Need to accept terms/conditions
    QUIZ = "quiz"  # Must pass a quiz to confirm understanding
    SIGN = "sign"  # Digital signature required


class AcknowledgmentStatus(str, enum.Enum):
    """Status of an acknowledgment."""

    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"
    OVERDUE = "overdue"


class PolicyAcknowledgmentRequirement(Base, TimestampMixin):
    """Defines acknowledgment requirements for a policy."""

    __tablename__ = "policy_acknowledgment_requirements"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Link to policy
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Requirement details
    acknowledgment_type: Mapped[AcknowledgmentType] = mapped_column(
        SQLEnum(AcknowledgmentType, native_enum=False),
        default=AcknowledgmentType.READ_ONLY,
    )

    # Who needs to acknowledge
    required_for_all: Mapped[bool] = mapped_column(Boolean, default=False)
    required_departments: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True
    )  # List of departments
    required_roles: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True
    )  # List of roles
    required_user_ids: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True
    )  # Specific user IDs

    # Timing
    due_within_days: Mapped[int] = mapped_column(
        Integer, default=30
    )  # Days after assignment
    reminder_days_before: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True
    )  # [7, 3, 1] = remind at 7, 3, 1 days before due

    # Re-acknowledgment
    re_acknowledge_on_update: Mapped[bool] = mapped_column(Boolean, default=True)
    re_acknowledge_period_months: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # Periodic re-read

    # Quiz settings (if acknowledgment_type is QUIZ)
    quiz_questions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    quiz_passing_score: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # Percentage

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    acknowledgments: Mapped[List["PolicyAcknowledgment"]] = relationship(
        "PolicyAcknowledgment",
        back_populates="requirement",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<PolicyAcknowledgmentRequirement(id={self.id}, policy_id={self.policy_id})>"


class PolicyAcknowledgment(Base, TimestampMixin):
    """Individual user's acknowledgment of a policy."""

    __tablename__ = "policy_acknowledgments"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Links
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("policy_acknowledgment_requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Policy version tracking
    policy_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Status
    status: Mapped[AcknowledgmentStatus] = mapped_column(
        SQLEnum(AcknowledgmentStatus, native_enum=False),
        default=AcknowledgmentStatus.PENDING,
    )

    # Timing
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    due_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Completion
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Read tracking
    first_opened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    time_spent_seconds: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # Track reading time

    # Quiz results (if applicable)
    quiz_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quiz_attempts: Mapped[int] = mapped_column(Integer, default=0)
    quiz_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Acceptance/Signature
    acceptance_statement: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # What they agreed to
    signature_data: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Digital signature (base64 or reference)
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # For audit trail
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )  # Browser info

    # Reminders sent
    reminders_sent: Mapped[int] = mapped_column(Integer, default=0)
    last_reminder_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    requirement: Mapped["PolicyAcknowledgmentRequirement"] = relationship(
        "PolicyAcknowledgmentRequirement", back_populates="acknowledgments"
    )

    def __repr__(self) -> str:
        return f"<PolicyAcknowledgment(id={self.id}, user_id={self.user_id}, status={self.status})>"


class DocumentReadLog(Base, TimestampMixin):
    """Track when users read/view documents for compliance."""

    __tablename__ = "document_read_logs"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # What was read
    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # policy, procedure, standard
    document_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    document_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Who read it
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # When
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Duration
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # What percentage was viewed (for long documents)
    scroll_percentage: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # 0-100

    # Access context
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    device_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # desktop, mobile, tablet

    def __repr__(self) -> str:
        return f"<DocumentReadLog(id={self.id}, doc={self.document_type}:{self.document_id}, user={self.user_id})>"
