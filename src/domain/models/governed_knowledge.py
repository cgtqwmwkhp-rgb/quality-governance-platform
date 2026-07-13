"""Governed Knowledge Bank models — discussions, quiz drafts, regulatory watch, AI audit log."""

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base, CaseInsensitiveEnum, TimestampMixin

_JSON = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class DiscussionThreadStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class QuizDraftStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    STALE = "stale"


class RegulatoryImpactStatus(str, enum.Enum):
    NEW = "new"
    TASK_CREATED = "task_created"
    DISMISSED = "dismissed"


class DocumentDiscussionThread(Base, TimestampMixin):
    """Threaded discussion on a document version."""

    __tablename__ = "document_discussion_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    status: Mapped[DiscussionThreadStatus] = mapped_column(
        CaseInsensitiveEnum(DiscussionThreadStatus),
        nullable=False,
        default=DiscussionThreadStatus.OPEN,
    )
    title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)


class DocumentDiscussionMessage(Base, TimestampMixin):
    """Message within a document discussion thread."""

    __tablename__ = "document_discussion_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    thread_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("document_discussion_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_ai_draft: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class DocumentQuizDraft(Base, TimestampMixin):
    """AI-generated quiz draft pending human approval."""

    __tablename__ = "document_quiz_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    questions: Mapped[list] = mapped_column(_JSON, nullable=False, default=list)
    pass_mark: Mapped[int] = mapped_column(Integer, nullable=False, default=70)
    status: Mapped[QuizDraftStatus] = mapped_column(
        CaseInsensitiveEnum(QuizDraftStatus),
        nullable=False,
        default=QuizDraftStatus.DRAFT,
    )
    created_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)


class RegulatoryWatchImpact(Base, TimestampMixin):
    """Regulatory update impact on a knowledge-bank document."""

    __tablename__ = "regulatory_watch_impacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    update_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    document_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("documents.id"), nullable=True, index=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[RegulatoryImpactStatus] = mapped_column(
        CaseInsensitiveEnum(RegulatoryImpactStatus),
        nullable=False,
        default=RegulatoryImpactStatus.NEW,
    )


class AiDecisionLog(Base, TimestampMixin):
    """Audit log for all AI-first governed knowledge decisions."""

    __tablename__ = "ai_decision_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    auto_applied: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(_JSON, nullable=True)
