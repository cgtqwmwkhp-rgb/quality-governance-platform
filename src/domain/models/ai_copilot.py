"""
AI Copilot Models

Provides conversational AI assistance with:
- Chat sessions and message history
- Context awareness
- Action execution
- Learning from feedback
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base


class CopilotSession(Base):
    """
    AI Copilot conversation session.
    """

    __tablename__ = "copilot_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Multi-tenancy
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Session info
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Context
    context_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # incident, audit, risk, etc.
    context_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    context_data: Mapped[dict] = mapped_column(JSON, default=dict)

    # Current page/location
    current_page: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    messages = relationship("CopilotMessage", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<CopilotSession {self.id} user={self.user_id}>"


class CopilotMessage(Base):
    """
    Individual message in a copilot conversation.
    """

    __tablename__ = "copilot_messages"

    __table_args__ = (Index("ix_copilot_msg_session", "session_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("copilot_sessions.id"), nullable=False)

    # Message content
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), default="text")  # text, action, error

    # For action messages
    action_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    action_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    action_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    action_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # pending, completed, failed

    # AI metadata
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # User feedback
    feedback_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("CopilotSession", back_populates="messages")

    def __repr__(self) -> str:
        return f"<CopilotMessage {self.id} role={self.role}>"


class CopilotAction(Base):
    """
    Executable action that the copilot can perform.
    """

    __tablename__ = "copilot_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Action identity
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Categorization
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # incident, audit, risk, navigation, etc.

    # Parameters schema
    parameters_schema: Mapped[dict] = mapped_column(JSON, default=dict)  # JSON Schema

    # Examples for AI understanding
    examples: Mapped[list] = mapped_column(JSON, default=list)

    # Permissions required
    required_permissions: Mapped[list] = mapped_column(JSON, default=list)

    # Status
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CopilotAction {self.name}>"


class CopilotKnowledge(Base):
    """
    Knowledge base for the copilot (RAG).
    """

    __tablename__ = "copilot_knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Multi-tenancy (null = global knowledge)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True)

    # Content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Categorization
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # policy, procedure, faq, compliance, etc.
    tags: Mapped[list] = mapped_column(JSON, default=list)

    # Source reference
    source_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # document, policy, manual
    source_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Embeddings for semantic search
    embedding: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # Vector embedding

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CopilotKnowledge {self.title}>"


class CopilotFeedback(Base):
    """
    Aggregated feedback for improving the copilot.
    """

    __tablename__ = "copilot_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    message_id: Mapped[int] = mapped_column(Integer, ForeignKey("copilot_messages.id"), nullable=False)

    # Feedback
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    feedback_type: Mapped[str] = mapped_column(String(50), nullable=False)  # helpful, inaccurate, inappropriate, etc.
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Context
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_response: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CopilotFeedback {self.id} rating={self.rating}>"
