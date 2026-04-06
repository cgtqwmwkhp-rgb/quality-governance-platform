"""Unit tests for CollaborationService — documents, sessions, comments, presence.

All database interactions are mocked via AsyncMock.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_db():
    return AsyncMock()


def _make_service(db=None):
    from src.domain.services.collaboration_service import CollaborationService

    if db is None:
        db = _make_db()
    return CollaborationService(db)


def _fake_document(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 10,
        "entity_type": "incident",
        "entity_id": "42",
        "field_name": "content",
        "yjs_state": b"",
        "yjs_state_vector": None,
        "version": 1,
        "is_locked": False,
        "locked_by_id": None,
        "locked_at": None,
        "lock_reason": None,
        "last_snapshot": None,
        "last_snapshot_at": None,
    }
    defaults.update(overrides)
    obj = MagicMock(**defaults)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _fake_session(**overrides):
    defaults = {
        "id": 1,
        "session_id": "abc123",
        "document_id": 1,
        "user_id": 5,
        "user_name": "Alice",
        "user_email": "alice@example.com",
        "user_avatar": None,
        "user_color": "#3B82F6",
        "is_active": True,
        "cursor_position": None,
        "selection_range": None,
        "current_field": None,
        "is_editing": False,
        "is_typing": False,
        "last_seen_at": datetime.now(timezone.utc),
        "left_at": None,
        "connection_id": None,
    }
    defaults.update(overrides)
    obj = MagicMock(**defaults)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _fake_comment(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 10,
        "entity_type": "incident",
        "entity_id": "42",
        "content": "Test comment",
        "author_id": 5,
        "author_name": "Alice",
        "status": "open",
        "is_deleted": False,
        "thread_id": None,
        "parent_id": None,
        "reactions": {},
        "resolved_by_id": None,
        "resolved_at": None,
    }
    defaults.update(overrides)
    obj = MagicMock(**defaults)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


# =========================================================================
# Document Management
# =========================================================================


class TestGetOrCreateDocument:
    @pytest.mark.asyncio
    async def test_returns_existing_document(self):
        doc = _fake_document()
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = doc
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.get_or_create_document(10, "incident", "42")
        assert result.id == 1
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_new_document_when_not_found(self):
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = _make_service(db)
        await svc.get_or_create_document(10, "incident", "42")
        db.add.assert_called_once()
        db.commit.assert_awaited()


class TestUpdateDocumentState:
    @pytest.mark.asyncio
    async def test_updates_state_and_increments_version(self):
        doc = _fake_document(version=3)
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = doc
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.update_document_state(1, b"new-state")
        assert result.yjs_state == b"new-state"
        assert result.version == 4
        db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_updates_state_vector_when_provided(self):
        doc = _fake_document()
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = doc
        db.execute.return_value = result_mock

        svc = _make_service(db)
        await svc.update_document_state(1, b"state", yjs_state_vector=b"vector")
        assert doc.yjs_state_vector == b"vector"

    @pytest.mark.asyncio
    async def test_raises_when_document_not_found(self):
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = _make_service(db)
        with pytest.raises(ValueError, match="Document 999 not found"):
            await svc.update_document_state(999, b"state")


class TestCreateSnapshot:
    @pytest.mark.asyncio
    async def test_snapshot_copies_current_state(self):
        doc = _fake_document(yjs_state=b"current")
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = doc
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.create_snapshot(1)
        assert result.last_snapshot == b"current"
        assert result.last_snapshot_at is not None

    @pytest.mark.asyncio
    async def test_snapshot_raises_when_not_found(self):
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = _make_service(db)
        with pytest.raises(ValueError):
            await svc.create_snapshot(999)


class TestLockDocument:
    @pytest.mark.asyncio
    async def test_lock_sets_fields(self):
        doc = _fake_document(is_locked=False)
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = doc
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.lock_document(1, user_id=5, reason="Review")
        assert result.is_locked is True
        assert result.locked_by_id == 5
        assert result.lock_reason == "Review"

    @pytest.mark.asyncio
    async def test_lock_by_another_user_raises(self):
        doc = _fake_document(is_locked=True, locked_by_id=99)
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = doc
        db.execute.return_value = result_mock

        svc = _make_service(db)
        with pytest.raises(ValueError, match="locked by another user"):
            await svc.lock_document(1, user_id=5)

    @pytest.mark.asyncio
    async def test_lock_same_user_succeeds(self):
        doc = _fake_document(is_locked=True, locked_by_id=5)
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = doc
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.lock_document(1, user_id=5)
        assert result.is_locked is True


class TestUnlockDocument:
    @pytest.mark.asyncio
    async def test_unlock_clears_fields(self):
        doc = _fake_document(is_locked=True, locked_by_id=5)
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = doc
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.unlock_document(1, user_id=5)
        assert result.is_locked is False
        assert result.locked_by_id is None

    @pytest.mark.asyncio
    async def test_unlock_by_wrong_user_raises(self):
        doc = _fake_document(is_locked=True, locked_by_id=99)
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = doc
        db.execute.return_value = result_mock

        svc = _make_service(db)
        with pytest.raises(ValueError, match="locked by another user"):
            await svc.unlock_document(1, user_id=5)


# =========================================================================
# Session Management
# =========================================================================


class TestJoinSession:
    @pytest.mark.asyncio
    async def test_join_creates_active_session(self):
        db = _make_db()
        svc = _make_service(db)
        await svc.join_session(1, user_id=5, user_name="Alice", user_email="alice@x.com")
        db.add.assert_called_once()
        db.commit.assert_awaited()


class TestLeaveSession:
    @pytest.mark.asyncio
    async def test_leave_deactivates_session(self):
        session = _fake_session(is_active=True)
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = session
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.leave_session("abc123")
        assert result.is_active is False
        assert result.left_at is not None

    @pytest.mark.asyncio
    async def test_leave_nonexistent_returns_none(self):
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.leave_session("nonexistent")
        assert result is None


class TestUpdateCursor:
    @pytest.mark.asyncio
    async def test_updates_cursor_position(self):
        session = _fake_session()
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = session
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.update_cursor("abc123", cursor_position={"line": 10})
        assert result.cursor_position == {"line": 10}

    @pytest.mark.asyncio
    async def test_raises_when_session_not_found(self):
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = _make_service(db)
        with pytest.raises(ValueError, match="Session .* not found"):
            await svc.update_cursor("nonexistent")


# =========================================================================
# Comments
# =========================================================================


class TestAddComment:
    @pytest.mark.asyncio
    async def test_creates_top_level_comment(self):
        db = _make_db()
        svc = _make_service(db)
        await svc.add_comment(10, "incident", "42", "Hello", author_id=5, author_name="Alice")
        db.add.assert_called_once()
        db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_reply_inherits_thread_id(self):
        parent = _fake_comment(id=10, thread_id=10)
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = parent
        db.execute.return_value = result_mock

        svc = _make_service(db)
        await svc.add_comment(10, "incident", "42", "Reply", author_id=6, author_name="Bob", parent_id=10)
        db.add.assert_called_once()


class TestResolveComment:
    @pytest.mark.asyncio
    async def test_resolve_sets_status_and_resolver(self):
        comment = _fake_comment(status="open")
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = comment
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.resolve_comment(1, resolved_by_id=5)
        assert result.status == "resolved"
        assert result.resolved_by_id == 5

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_raises(self):
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = _make_service(db)
        with pytest.raises(ValueError, match="Comment 999 not found"):
            await svc.resolve_comment(999, resolved_by_id=5)


class TestAddReaction:
    @pytest.mark.asyncio
    async def test_adds_new_reaction(self):
        comment = _fake_comment(reactions={})
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = comment
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.add_reaction(1, user_id=5, emoji="👍")
        assert 5 in result.reactions["👍"]

    @pytest.mark.asyncio
    async def test_does_not_duplicate_reaction(self):
        comment = _fake_comment(reactions={"👍": [5]})
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = comment
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.add_reaction(1, user_id=5, emoji="👍")
        assert result.reactions["👍"].count(5) == 1

    @pytest.mark.asyncio
    async def test_reaction_on_missing_comment_raises(self):
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = _make_service(db)
        with pytest.raises(ValueError):
            await svc.add_reaction(999, user_id=5, emoji="👍")


# =========================================================================
# Presence
# =========================================================================


class TestUpdatePresence:
    @pytest.mark.asyncio
    async def test_creates_new_presence_record(self):
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = _make_service(db)
        await svc.update_presence(10, user_id=5, status="online")
        db.add.assert_called_once()
        db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_updates_existing_presence(self):
        presence = MagicMock(user_id=5, status="online", went_away_at=None)
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = presence
        db.execute.return_value = result_mock

        svc = _make_service(db)
        await svc.update_presence(10, user_id=5, status="away")
        assert presence.status == "away"
        assert presence.went_away_at is not None

    @pytest.mark.asyncio
    async def test_online_clears_went_away(self):
        presence = MagicMock(user_id=5, status="away", went_away_at=datetime.now(timezone.utc))
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = presence
        db.execute.return_value = result_mock

        svc = _make_service(db)
        await svc.update_presence(10, user_id=5, status="online")
        assert presence.went_away_at is None


class TestSetOffline:
    @pytest.mark.asyncio
    async def test_sets_status_offline(self):
        presence = MagicMock(status="online")
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = presence
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.set_offline(5)
        assert result.status == "offline"

    @pytest.mark.asyncio
    async def test_offline_for_nonexistent_returns_none(self):
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.set_offline(999)
        assert result is None


# =========================================================================
# Helpers
# =========================================================================


class TestGenerateUserColor:
    def test_returns_valid_hex_color(self):
        svc = _make_service()
        color = svc._generate_user_color(1)
        assert color.startswith("#")
        assert len(color) == 7

    def test_different_ids_can_produce_different_colors(self):
        svc = _make_service()
        colors = {svc._generate_user_color(i) for i in range(10)}
        assert len(colors) == 10

    def test_wraps_around_for_large_ids(self):
        svc = _make_service()
        assert svc._generate_user_color(0) == svc._generate_user_color(10)
        assert svc._generate_user_color(1) == svc._generate_user_color(11)
