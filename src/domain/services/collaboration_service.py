"""
Real-time Collaboration Service

Provides live co-editing with:
- Yjs CRDT synchronization
- Cursor/selection tracking
- Presence awareness
- Change history
- Conflict resolution
"""

import secrets
import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional, Callable

from sqlalchemy import and_, or_, desc
from sqlalchemy.orm import Session

from src.domain.models.collaboration import (
    CollaborativeDocument,
    CollaborativeSession,
    CollaborativeChange,
    Comment,
    Presence,
)


class CollaborationService:
    """
    Real-time collaboration management.
    """

    # Session timeout (consider user offline after this)
    SESSION_TIMEOUT_SECONDS = 60

    # Presence timeout (consider user away after this)
    PRESENCE_AWAY_SECONDS = 300

    def __init__(self, db: Session):
        self.db = db
        self._broadcast_handlers: dict[str, Callable] = {}

    # =========================================================================
    # Document Management
    # =========================================================================

    def get_or_create_document(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: str,
        field_name: str = "content",
    ) -> CollaborativeDocument:
        """Get or create a collaborative document for an entity."""
        doc = (
            self.db.query(CollaborativeDocument)
            .filter(
                CollaborativeDocument.tenant_id == tenant_id,
                CollaborativeDocument.entity_type == entity_type,
                CollaborativeDocument.entity_id == entity_id,
                CollaborativeDocument.field_name == field_name,
            )
            .first()
        )

        if not doc:
            doc = CollaborativeDocument(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                field_name=field_name,
            )
            self.db.add(doc)
            self.db.commit()
            self.db.refresh(doc)

        return doc

    def update_document_state(
        self,
        document_id: int,
        yjs_state: bytes,
        yjs_state_vector: Optional[bytes] = None,
    ) -> CollaborativeDocument:
        """Update the Yjs state of a document."""
        doc = self.db.query(CollaborativeDocument).get(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        doc.yjs_state = yjs_state
        if yjs_state_vector:
            doc.yjs_state_vector = yjs_state_vector
        doc.version += 1

        self.db.commit()
        self.db.refresh(doc)

        return doc

    def create_snapshot(self, document_id: int) -> CollaborativeDocument:
        """Create a snapshot of the current document state."""
        doc = self.db.query(CollaborativeDocument).get(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        doc.last_snapshot = doc.yjs_state
        doc.last_snapshot_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(doc)

        return doc

    def lock_document(
        self,
        document_id: int,
        user_id: int,
        reason: Optional[str] = None,
    ) -> CollaborativeDocument:
        """Lock a document for exclusive editing."""
        doc = self.db.query(CollaborativeDocument).get(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        if doc.is_locked and doc.locked_by_id != user_id:
            raise ValueError("Document is locked by another user")

        doc.is_locked = True
        doc.locked_by_id = user_id
        doc.locked_at = datetime.utcnow()
        doc.lock_reason = reason

        self.db.commit()
        self.db.refresh(doc)

        return doc

    def unlock_document(self, document_id: int, user_id: int) -> CollaborativeDocument:
        """Unlock a document."""
        doc = self.db.query(CollaborativeDocument).get(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        if doc.is_locked and doc.locked_by_id != user_id:
            raise ValueError("Document is locked by another user")

        doc.is_locked = False
        doc.locked_by_id = None
        doc.locked_at = None
        doc.lock_reason = None

        self.db.commit()
        self.db.refresh(doc)

        return doc

    # =========================================================================
    # Session Management
    # =========================================================================

    def join_session(
        self,
        document_id: int,
        user_id: int,
        user_name: str,
        user_email: str,
        user_avatar: Optional[str] = None,
        connection_id: Optional[str] = None,
    ) -> CollaborativeSession:
        """Join a collaborative editing session."""
        # Generate unique session ID
        session_id = secrets.token_urlsafe(16)

        # Generate unique color for user
        user_color = self._generate_user_color(user_id)

        session = CollaborativeSession(
            document_id=document_id,
            user_id=user_id,
            session_id=session_id,
            user_name=user_name,
            user_email=user_email,
            user_avatar=user_avatar,
            user_color=user_color,
            connection_id=connection_id,
            is_active=True,
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        return session

    def leave_session(self, session_id: str) -> Optional[CollaborativeSession]:
        """Leave a collaborative editing session."""
        session = self.db.query(CollaborativeSession).filter(CollaborativeSession.session_id == session_id).first()

        if session:
            session.is_active = False
            session.left_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(session)

        return session

    def update_cursor(
        self,
        session_id: str,
        cursor_position: Optional[dict] = None,
        selection_range: Optional[dict] = None,
        current_field: Optional[str] = None,
        is_editing: bool = False,
        is_typing: bool = False,
    ) -> CollaborativeSession:
        """Update cursor/selection position for a session."""
        session = self.db.query(CollaborativeSession).filter(CollaborativeSession.session_id == session_id).first()

        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.cursor_position = cursor_position
        session.selection_range = selection_range
        session.current_field = current_field
        session.is_editing = is_editing
        session.is_typing = is_typing
        session.last_seen_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(session)

        return session

    def get_active_sessions(self, document_id: int) -> list[CollaborativeSession]:
        """Get all active sessions for a document."""
        timeout = datetime.utcnow() - timedelta(seconds=self.SESSION_TIMEOUT_SECONDS)

        return (
            self.db.query(CollaborativeSession)
            .filter(
                CollaborativeSession.document_id == document_id,
                CollaborativeSession.is_active == True,
                CollaborativeSession.last_seen_at >= timeout,
            )
            .all()
        )

    def cleanup_stale_sessions(self) -> int:
        """Clean up stale sessions. Returns count of cleaned sessions."""
        timeout = datetime.utcnow() - timedelta(seconds=self.SESSION_TIMEOUT_SECONDS * 2)

        stale = (
            self.db.query(CollaborativeSession)
            .filter(
                CollaborativeSession.is_active == True,
                CollaborativeSession.last_seen_at < timeout,
            )
            .all()
        )

        for session in stale:
            session.is_active = False
            session.left_at = datetime.utcnow()

        self.db.commit()

        return len(stale)

    # =========================================================================
    # Change Tracking
    # =========================================================================

    def record_change(
        self,
        document_id: int,
        session_id: str,
        user_id: int,
        change_type: str,
        change_data: dict,
        version: int,
        path: Optional[str] = None,
        offset: Optional[int] = None,
        length: Optional[int] = None,
    ) -> CollaborativeChange:
        """Record a change to a collaborative document."""
        change = CollaborativeChange(
            document_id=document_id,
            session_id=session_id,
            user_id=user_id,
            change_type=change_type,
            change_data=change_data,
            version=version,
            path=path,
            offset=offset,
            length=length,
        )

        self.db.add(change)
        self.db.commit()
        self.db.refresh(change)

        return change

    def get_changes(
        self,
        document_id: int,
        since_version: Optional[int] = None,
        limit: int = 100,
    ) -> list[CollaborativeChange]:
        """Get changes for a document, optionally since a version."""
        query = self.db.query(CollaborativeChange).filter(CollaborativeChange.document_id == document_id)

        if since_version is not None:
            query = query.filter(CollaborativeChange.version > since_version)

        return query.order_by(CollaborativeChange.version).limit(limit).all()

    # =========================================================================
    # Comments
    # =========================================================================

    def add_comment(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: str,
        content: str,
        author_id: int,
        author_name: str,
        parent_id: Optional[int] = None,
        anchor_path: Optional[str] = None,
        anchor_offset: Optional[int] = None,
        quoted_text: Optional[str] = None,
        mentions: Optional[list[int]] = None,
    ) -> Comment:
        """Add a comment to an entity."""
        # Determine thread ID
        thread_id = None
        if parent_id:
            parent = self.db.query(Comment).get(parent_id)
            if parent:
                thread_id = parent.thread_id or parent.id

        comment = Comment(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            parent_id=parent_id,
            thread_id=thread_id,
            content=content,
            author_id=author_id,
            author_name=author_name,
            anchor_path=anchor_path,
            anchor_offset=anchor_offset,
            quoted_text=quoted_text,
            mentions=mentions,
        )

        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)

        # Set thread_id if this is a new thread
        if not parent_id and not comment.thread_id:
            comment.thread_id = comment.id
            self.db.commit()

        return comment

    def get_comments(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: str,
        include_resolved: bool = False,
    ) -> list[Comment]:
        """Get comments for an entity."""
        query = self.db.query(Comment).filter(
            Comment.tenant_id == tenant_id,
            Comment.entity_type == entity_type,
            Comment.entity_id == entity_id,
            Comment.is_deleted == False,
        )

        if not include_resolved:
            query = query.filter(Comment.status != "resolved")

        return query.order_by(Comment.created_at).all()

    def resolve_comment(
        self,
        comment_id: int,
        resolved_by_id: int,
    ) -> Comment:
        """Resolve a comment."""
        comment = self.db.query(Comment).get(comment_id)
        if not comment:
            raise ValueError(f"Comment {comment_id} not found")

        comment.status = "resolved"
        comment.resolved_by_id = resolved_by_id
        comment.resolved_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(comment)

        return comment

    def add_reaction(
        self,
        comment_id: int,
        user_id: int,
        emoji: str,
    ) -> Comment:
        """Add a reaction to a comment."""
        comment = self.db.query(Comment).get(comment_id)
        if not comment:
            raise ValueError(f"Comment {comment_id} not found")

        reactions = comment.reactions.copy()
        if emoji not in reactions:
            reactions[emoji] = []
        if user_id not in reactions[emoji]:
            reactions[emoji].append(user_id)
        comment.reactions = reactions

        self.db.commit()
        self.db.refresh(comment)

        return comment

    # =========================================================================
    # Presence
    # =========================================================================

    def update_presence(
        self,
        tenant_id: int,
        user_id: int,
        status: str = "online",
        current_page: Optional[str] = None,
        current_entity_type: Optional[str] = None,
        current_entity_id: Optional[str] = None,
        device_type: Optional[str] = None,
        custom_status: Optional[str] = None,
    ) -> Presence:
        """Update user presence."""
        presence = self.db.query(Presence).filter(Presence.user_id == user_id).first()

        if not presence:
            presence = Presence(
                tenant_id=tenant_id,
                user_id=user_id,
            )
            self.db.add(presence)

        presence.status = status
        presence.current_page = current_page
        presence.current_entity_type = current_entity_type
        presence.current_entity_id = current_entity_id
        presence.device_type = device_type
        presence.custom_status = custom_status
        presence.last_seen_at = datetime.utcnow()

        if status == "away":
            presence.went_away_at = datetime.utcnow()
        else:
            presence.went_away_at = None

        self.db.commit()
        self.db.refresh(presence)

        return presence

    def get_online_users(self, tenant_id: int) -> list[Presence]:
        """Get all online users in a tenant."""
        timeout = datetime.utcnow() - timedelta(seconds=self.SESSION_TIMEOUT_SECONDS)

        return (
            self.db.query(Presence)
            .filter(
                Presence.tenant_id == tenant_id,
                Presence.status != "offline",
                Presence.last_seen_at >= timeout,
            )
            .all()
        )

    def get_users_viewing_entity(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: str,
    ) -> list[Presence]:
        """Get users currently viewing a specific entity."""
        timeout = datetime.utcnow() - timedelta(seconds=self.SESSION_TIMEOUT_SECONDS)

        return (
            self.db.query(Presence)
            .filter(
                Presence.tenant_id == tenant_id,
                Presence.current_entity_type == entity_type,
                Presence.current_entity_id == entity_id,
                Presence.status != "offline",
                Presence.last_seen_at >= timeout,
            )
            .all()
        )

    def set_offline(self, user_id: int) -> Optional[Presence]:
        """Set user as offline."""
        presence = self.db.query(Presence).filter(Presence.user_id == user_id).first()

        if presence:
            presence.status = "offline"
            self.db.commit()
            self.db.refresh(presence)

        return presence

    # =========================================================================
    # Helpers
    # =========================================================================

    def _generate_user_color(self, user_id: int) -> str:
        """Generate a unique color for a user based on their ID."""
        colors = [
            "#3B82F6",  # Blue
            "#10B981",  # Emerald
            "#F59E0B",  # Amber
            "#EF4444",  # Red
            "#8B5CF6",  # Purple
            "#EC4899",  # Pink
            "#06B6D4",  # Cyan
            "#F97316",  # Orange
            "#84CC16",  # Lime
            "#14B8A6",  # Teal
        ]
        return colors[user_id % len(colors)]
