"""
Real-time Collaboration Models

Provides live co-editing with:
- Yjs CRDT document state
- Cursor positions
- Awareness (who's viewing/editing)
- Collaborative sessions
- Change synchronization
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, JSON, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base


class CollaborativeDocument(Base):
    """
    A document that supports real-time collaboration.

    Stores Yjs CRDT state for conflict-free synchronization.
    """

    __tablename__ = "collaborative_documents"

    __table_args__ = (Index("ix_collab_doc_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Multi-tenancy
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False)

    # Linked entity
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)  # incident, audit, risk, etc.
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), default="content")  # Which field this document represents

    # Yjs state
    yjs_state: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)  # Encoded Yjs document state
    yjs_state_vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)  # State vector for sync

    # Version tracking
    version: Mapped[int] = mapped_column(Integer, default=0)

    # Snapshots (periodic saves of the full document)
    last_snapshot: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    last_snapshot_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Status
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    lock_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sessions = relationship("CollaborativeSession", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<CollaborativeDocument {self.entity_type}:{self.entity_id}>"


class CollaborativeSession(Base):
    """
    An active collaboration session.

    Tracks who is currently viewing/editing a document.
    """

    __tablename__ = "collaborative_sessions"

    __table_args__ = (Index("ix_collab_session_active", "is_active", "last_seen_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("collaborative_documents.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Session identity
    session_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # User display info (denormalized for real-time performance)
    user_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    user_avatar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    user_color: Mapped[str] = mapped_column(String(7), default="#3B82F6")  # Unique color for cursor

    # Cursor position
    cursor_position: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {start, end, path}
    selection_range: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Current view
    current_field: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Which field user is editing
    is_editing: Mapped[bool] = mapped_column(Boolean, default=False)
    is_typing: Mapped[bool] = mapped_column(Boolean, default=False)

    # Connection info
    connection_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # WebSocket connection ID
    client_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    document = relationship("CollaborativeDocument", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<CollaborativeSession {self.session_id} user={self.user_id}>"


class CollaborativeChange(Base):
    """
    Individual change in a collaborative document.

    Records each atomic change for history and undo/redo.
    """

    __tablename__ = "collaborative_changes"

    __table_args__ = (Index("ix_collab_change_doc", "document_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("collaborative_documents.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Change details
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)  # insert, delete, format, etc.
    change_data: Mapped[dict] = mapped_column(JSON, nullable=False)  # Yjs update or structured change

    # Position
    path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # JSON path to change location
    offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Version
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CollaborativeChange {self.id} {self.change_type}>"


class Comment(Base):
    """
    Comments on collaborative documents.

    Supports threaded discussions and mentions.
    """

    __tablename__ = "document_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Multi-tenancy
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False)

    # Linked entity
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Thread structure
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("document_comments.id"), nullable=True)
    thread_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Root comment ID for the thread

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Rendered HTML

    # Position (for inline comments)
    anchor_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # JSON path
    anchor_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    anchor_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quoted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Mentions
    mentions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # List of user IDs mentioned

    # Author
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)  # Denormalized

    # Status
    status: Mapped[str] = mapped_column(String(20), default="open")  # open, resolved, archived
    resolved_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Reactions
    reactions: Mapped[dict] = mapped_column(JSON, default=dict)  # {"👍": [user_ids], "❤️": [user_ids]}

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Comment {self.id} on {self.entity_type}:{self.entity_id}>"


class Presence(Base):
    """
    Real-time presence tracking.

    Shows who is online and what they're viewing.
    """

    __tablename__ = "user_presence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="online")  # online, away, busy, offline
    custom_status: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Current location
    current_page: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    current_entity_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    current_entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Device info
    device_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # desktop, mobile, tablet
    browser: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Connection
    connection_count: Mapped[int] = mapped_column(Integer, default=1)  # Number of active connections

    # Timestamps
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    went_away_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Presence user={self.user_id} status={self.status}>"
