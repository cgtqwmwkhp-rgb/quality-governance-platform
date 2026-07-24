"""Persisted Audit Builder Check & Challenge coach sessions."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import AuditTrailMixin, Base, CaseInsensitiveEnum, TimestampMixin


class AuditChallengeSessionStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AuditChallengeTurnRole(str, enum.Enum):
    USER = "user"
    CRITIC = "critic"
    AUTHOR = "author"
    SYSTEM = "system"


class AuditChallengeProposalDecision(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EDITED = "edited"


class AuditChallengeSession(Base, TimestampMixin, AuditTrailMixin):
    """One check-and-challenge job over a template snapshot."""

    __tablename__ = "audit_challenge_sessions"
    __table_args__ = (
        Index("ix_audit_challenge_sessions_tenant_status", "tenant_id", "status"),
        Index("ix_audit_challenge_sessions_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("audit_templates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[AuditChallengeSessionStatus] = mapped_column(
        CaseInsensitiveEnum(AuditChallengeSessionStatus),
        default=AuditChallengeSessionStatus.QUEUED,
        nullable=False,
        index=True,
    )
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    chip_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    user_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brief_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    template_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    models_used_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    grounding_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditChallengeTurn(Base, TimestampMixin):
    """One conversational / agent turn in a challenge session."""

    __tablename__ = "audit_challenge_turns"
    __table_args__ = (Index("ix_audit_challenge_turns_session", "session_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("audit_challenge_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    role: Mapped[AuditChallengeTurnRole] = mapped_column(
        CaseInsensitiveEnum(AuditChallengeTurnRole), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    chip_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    citations_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AuditChallengeProposal(Base, TimestampMixin):
    """Author-proposed section/question patch awaiting human decision."""

    __tablename__ = "audit_challenge_proposals"
    __table_args__ = (
        Index("ix_audit_challenge_proposals_session", "session_id"),
        Index("ix_audit_challenge_proposals_decision", "session_id", "decision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("audit_challenge_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    turn_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("audit_challenge_turns.id", ondelete="SET NULL"), nullable=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    proposal_key: Mapped[str] = mapped_column(String(80), nullable=False)
    target_path: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    change_type: Mapped[str] = mapped_column(String(80), nullable=False, default="revise_question")
    dimension: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    assessor_failure_mode: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    before_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    citations_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    decision: Mapped[AuditChallengeProposalDecision] = mapped_column(
        CaseInsensitiveEnum(AuditChallengeProposalDecision),
        default=AuditChallengeProposalDecision.PENDING,
        nullable=False,
    )
    edited_after_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
