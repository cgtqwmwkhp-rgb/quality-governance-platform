"""Document Campaign models — QGP engineer groups, campaigns, and assignments.

Provides the spine for pushing controlled documents (with an optional quiz and
e-signature) out to a defined audience of users, tracking per-user completion.
"""

import enum
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import Base, CaseInsensitiveEnum, TimestampMixin

DEFAULT_REMINDER_OFFSETS_HOURS = [24, 168, 336, 720]  # 24h, 7d, 14d, 30d


class CampaignStatus(str, enum.Enum):
    """Lifecycle status of a document campaign."""

    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class AssignmentStatus(str, enum.Enum):
    """Lifecycle status of an individual user's campaign assignment."""

    PENDING = "pending"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    EXPIRED = "expired"


class EngineerGroup(Base, TimestampMixin):
    """A named, reusable group of users (e.g. engineers) for targeting campaigns."""

    __tablename__ = "engineer_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    members: Mapped[List["EngineerGroupMember"]] = relationship(
        "EngineerGroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<EngineerGroup(id={self.id}, name='{self.name}')>"


class EngineerGroupMember(Base):
    """Membership of a user in an :class:`EngineerGroup`."""

    __tablename__ = "engineer_group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_engineer_group_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("engineer_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    added_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    group: Mapped["EngineerGroup"] = relationship("EngineerGroup", back_populates="members")

    def __repr__(self) -> str:
        return f"<EngineerGroupMember(group_id={self.group_id}, user_id={self.user_id})>"


class DocumentCampaign(Base, TimestampMixin):
    """A read/quiz/sign-off campaign for a single controlled document."""

    __tablename__ = "document_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    quiz_draft_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("document_quiz_drafts.id"), nullable=True, index=True
    )

    title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    status: Mapped[CampaignStatus] = mapped_column(
        CaseInsensitiveEnum(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False, index=True
    )

    due_within_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    require_quiz: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    require_sign: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reminder_offsets_hours: Mapped[list] = mapped_column(
        JSON, default=lambda: list(DEFAULT_REMINDER_OFFSETS_HOURS), nullable=False
    )

    # Audience spec, retained for audit / re-expansion on relaunch.
    audience_all_users: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    audience_department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    audience_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    audience_group_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    audience_user_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Snapshot of quiz content at creation time so later edits to the draft don't
    # retroactively change a campaign that has already been launched.
    quiz_questions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    quiz_pass_mark: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    launched_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    launched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    assignments: Mapped[List["CampaignAssignment"]] = relationship(
        "CampaignAssignment",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DocumentCampaign(id={self.id}, document_id={self.document_id}, status={self.status})>"


class CampaignAssignment(Base, TimestampMixin):
    """A single user's assignment within a :class:`DocumentCampaign`."""

    __tablename__ = "campaign_assignments"
    __table_args__ = (UniqueConstraint("campaign_id", "user_id", name="uq_campaign_assignment_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("document_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[AssignmentStatus] = mapped_column(
        CaseInsensitiveEnum(AssignmentStatus), default=AssignmentStatus.PENDING, nullable=False, index=True
    )

    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    first_opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Quiz attempts are tracked inline on the assignment (single active attempt record).
    quiz_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quiz_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    quiz_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quiz_review_needed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_quiz_answers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acceptance_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signature_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    reminders_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reminder_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    campaign: Mapped["DocumentCampaign"] = relationship("DocumentCampaign", back_populates="assignments")

    def __repr__(self) -> str:
        return f"<CampaignAssignment(id={self.id}, campaign_id={self.campaign_id}, user_id={self.user_id})>"
