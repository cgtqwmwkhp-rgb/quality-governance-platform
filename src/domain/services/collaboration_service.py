"""
Real-time Collaboration Service

Provides live co-editing with:
- Yjs CRDT synchronization
- Cursor/selection tracking
- Presence awareness
- Change history
- Conflict resolution
"""

import asyncio
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.collaboration import (
    CollaborativeChange,
    CollaborativeDocument,
    CollaborativeSession,
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

    def __init__(self, db: AsyncSession):
        self.db = db
        self._broadcast_handlers: dict[str, Callable] = {}

    # =========================================================================
    # Document Management
    # =========================================================================

    async def get_or_create_document(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: str,
        field_name: str = "content",
    ) -> CollaborativeDocument:
        """Get or create a collaborative document for an entity."""
        result = await self.db.execute(
            select(CollaborativeDocument).where(
                CollaborativeDocument.tenant_id == tenant_id,
                CollaborativeDocument.entity_type == entity_type,
                CollaborativeDocument.entity_id == entity_id,
                CollaborativeDocument.field_name == field_name,
            )
        )
        doc = result.scalar_one_or_none()

        if not doc:
            doc = CollaborativeDocument(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                field_name=field_name,
            )
            self.db.add(doc)
            await self.db.commit()
            await self.db.refresh(doc)

        return doc

    async def update_document_state(
        self,
        document_id: int,
        yjs_state: bytes,
        yjs_state_vector: Optional[bytes] = None,
    ) -> CollaborativeDocument:
        """Update the Yjs state of a document."""
        result = await self.db.execute(select(CollaborativeDocument).where(CollaborativeDocument.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        doc.yjs_state = yjs_state
        if yjs_state_vector:
            doc.yjs_state_vector = yjs_state_vector
        doc.version += 1

        await self.db.commit()
        await self.db.refresh(doc)

        return doc

    async def create_snapshot(self, document_id: int) -> CollaborativeDocument:
        """Create a snapshot of the current document state."""
        result = await self.db.execute(select(CollaborativeDocument).where(CollaborativeDocument.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        doc.last_snapshot = doc.yjs_state
        doc.last_snapshot_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(doc)

        return doc

    async def lock_document(
        self,
        document_id: int,
        user_id: int,
        reason: Optional[str] = None,
    ) -> CollaborativeDocument:
        """Lock a document for exclusive editing."""
        result = await self.db.execute(select(CollaborativeDocument).where(CollaborativeDocument.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        if doc.is_locked and doc.locked_by_id != user_id:
            raise ValueError("Document is locked by another user")

        doc.is_locked = True
        doc.locked_by_id = user_id
        doc.locked_at = datetime.now(timezone.utc)
        doc.lock_reason = reason

        await self.db.commit()
        await self.db.refresh(doc)

        return doc

    async def unlock_document(self, document_id: int, user_id: int) -> CollaborativeDocument:
        """Unlock a document."""
        result = await self.db.execute(select(CollaborativeDocument).where(CollaborativeDocument.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        if doc.is_locked and doc.locked_by_id != user_id:
            raise ValueError("Document is locked by another user")

        doc.is_locked = False
        doc.locked_by_id = None
        doc.locked_at = None
        doc.lock_reason = None

        await self.db.commit()
        await self.db.refresh(doc)

        return doc

    # =========================================================================
    # Session Management
    # =========================================================================

    async def join_session(
        self,
        document_id: int,
        user_id: int,
        user_name: str,
        user_email: str,
        user_avatar: Optional[str] = None,
        connection_id: Optional[str] = None,
    ) -> CollaborativeSession:
        """Join a collaborative editing session."""
        session_id = secrets.token_urlsafe(16)

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
        await self.db.commit()
        await self.db.refresh(session)

        return session

    async def leave_session(self, session_id: str) -> Optional[CollaborativeSession]:
        """Leave a collaborative editing session."""
        result = await self.db.execute(
            select(CollaborativeSession).where(CollaborativeSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()

        if session:
            session.is_active = False
            session.left_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(session)

        return session

    async def update_cursor(
        self,
        session_id: str,
        cursor_position: Optional[dict] = None,
        selection_range: Optional[dict] = None,
        current_field: Optional[str] = None,
        is_editing: bool = False,
        is_typing: bool = False,
    ) -> CollaborativeSession:
        """Update cursor/selection position for a session."""
        result = await self.db.execute(
            select(CollaborativeSession).where(CollaborativeSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()

        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.cursor_position = cursor_position
        session.selection_range = selection_range
        session.current_field = current_field
        session.is_editing = is_editing
        session.is_typing = is_typing
        session.last_seen_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(session)

        return session

    async def get_active_sessions(self, document_id: int) -> list[CollaborativeSession]:
        """Get all active sessions for a document."""
        timeout = datetime.now(timezone.utc) - timedelta(seconds=self.SESSION_TIMEOUT_SECONDS)

        result = await self.db.execute(
            select(CollaborativeSession).where(
                CollaborativeSession.document_id == document_id,
                CollaborativeSession.is_active == True,
                CollaborativeSession.last_seen_at >= timeout,
            )
        )
        return list(result.scalars().all())

    async def cleanup_stale_sessions(self) -> int:
        """Clean up stale sessions. Returns count of cleaned sessions."""
        timeout = datetime.now(timezone.utc) - timedelta(seconds=self.SESSION_TIMEOUT_SECONDS * 2)

        result = await self.db.execute(
            select(CollaborativeSession).where(
                CollaborativeSession.is_active == True,
                CollaborativeSession.last_seen_at < timeout,
            )
        )
        stale = list(result.scalars().all())

        for session in stale:
            session.is_active = False
            session.left_at = datetime.now(timezone.utc)

        await self.db.commit()

        return len(stale)

    # =========================================================================
    # Change Tracking
    # =========================================================================

    async def record_change(
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
        await self.db.commit()
        await self.db.refresh(change)

        return change

    async def get_changes(
        self,
        document_id: int,
        since_version: Optional[int] = None,
        limit: int = 100,
    ) -> list[CollaborativeChange]:
        """Get changes for a document, optionally since a version."""
        stmt = select(CollaborativeChange).where(CollaborativeChange.document_id == document_id)

        if since_version is not None:
            stmt = stmt.where(CollaborativeChange.version > since_version)

        stmt = stmt.order_by(CollaborativeChange.version).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # =========================================================================
    # Comments
    # =========================================================================

    async def add_comment(
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
        thread_id = None
        if parent_id:
            result = await self.db.execute(select(Comment).where(Comment.id == parent_id))
            parent = result.scalar_one_or_none()
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
        await self.db.commit()
        await self.db.refresh(comment)

        # Set thread_id if this is a new thread
        if not parent_id and not comment.thread_id:
            comment.thread_id = comment.id
            await self.db.commit()

        return comment

    async def get_comments(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: str,
        include_resolved: bool = False,
    ) -> list[Comment]:
        """Get comments for an entity."""
        stmt = select(Comment).where(
            Comment.tenant_id == tenant_id,
            Comment.entity_type == entity_type,
            Comment.entity_id == entity_id,
            Comment.is_deleted == False,
        )

        if not include_resolved:
            stmt = stmt.where(Comment.status != "resolved")

        stmt = stmt.order_by(Comment.created_at)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def resolve_comment(
        self,
        comment_id: int,
        resolved_by_id: int,
    ) -> Comment:
        """Resolve a comment."""
        result = await self.db.execute(select(Comment).where(Comment.id == comment_id))
        comment = result.scalar_one_or_none()
        if not comment:
            raise ValueError(f"Comment {comment_id} not found")

        comment.status = "resolved"
        comment.resolved_by_id = resolved_by_id
        comment.resolved_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(comment)

        return comment

    async def add_reaction(
        self,
        comment_id: int,
        user_id: int,
        emoji: str,
    ) -> Comment:
        """Add a reaction to a comment."""
        result = await self.db.execute(select(Comment).where(Comment.id == comment_id))
        comment = result.scalar_one_or_none()
        if not comment:
            raise ValueError(f"Comment {comment_id} not found")

        reactions = comment.reactions.copy()
        if emoji not in reactions:
            reactions[emoji] = []
        if user_id not in reactions[emoji]:
            reactions[emoji].append(user_id)
        comment.reactions = reactions

        await self.db.commit()
        await self.db.refresh(comment)

        return comment

    # =========================================================================
    # Presence
    # =========================================================================

    async def update_presence(
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
        result = await self.db.execute(select(Presence).where(Presence.user_id == user_id))
        presence = result.scalar_one_or_none()

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
        presence.last_seen_at = datetime.now(timezone.utc)

        if status == "away":
            presence.went_away_at = datetime.now(timezone.utc)
        else:
            presence.went_away_at = None

        await self.db.commit()
        await self.db.refresh(presence)

        return presence

    async def get_online_users(self, tenant_id: int) -> list[Presence]:
        """Get all online users in a tenant."""
        timeout = datetime.now(timezone.utc) - timedelta(seconds=self.SESSION_TIMEOUT_SECONDS)

        result = await self.db.execute(
            select(Presence).where(
                Presence.tenant_id == tenant_id,
                Presence.status != "offline",
                Presence.last_seen_at >= timeout,
            )
        )
        return list(result.scalars().all())

    async def get_users_viewing_entity(
        self,
        tenant_id: int,
        entity_type: str,
        entity_id: str,
    ) -> list[Presence]:
        """Get users currently viewing a specific entity."""
        timeout = datetime.now(timezone.utc) - timedelta(seconds=self.SESSION_TIMEOUT_SECONDS)

        result = await self.db.execute(
            select(Presence).where(
                Presence.tenant_id == tenant_id,
                Presence.current_entity_type == entity_type,
                Presence.current_entity_id == entity_id,
                Presence.status != "offline",
                Presence.last_seen_at >= timeout,
            )
        )
        return list(result.scalars().all())

    async def set_offline(self, user_id: int) -> Optional[Presence]:
        """Set user as offline."""
        result = await self.db.execute(select(Presence).where(Presence.user_id == user_id))
        presence = result.scalar_one_or_none()

        if presence:
            presence.status = "offline"
            await self.db.commit()
            await self.db.refresh(presence)

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
