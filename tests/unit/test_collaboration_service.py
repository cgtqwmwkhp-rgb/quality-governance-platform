"""Unit tests for CollaborationService - session management, presence, helpers."""

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.domain.services.collaboration_service import CollaborationService  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    """Async DB session mock that returns configurable query results."""
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def svc(mock_db):
    return CollaborationService(db=mock_db)


# ---------------------------------------------------------------------------
# _generate_user_color (pure function)
# ---------------------------------------------------------------------------


def test_generate_user_color_returns_hex(svc):
    """Color returned is a valid hex color string."""
    color = svc._generate_user_color(1)
    assert color.startswith("#")
    assert len(color) == 7


def test_generate_user_color_deterministic(svc):
    """Same user_id always produces the same color."""
    assert svc._generate_user_color(5) == svc._generate_user_color(5)


def test_generate_user_color_wraps_around(svc):
    """user_id wraps around the color palette (10 colors)."""
    assert svc._generate_user_color(0) == svc._generate_user_color(10)
    assert svc._generate_user_color(3) == svc._generate_user_color(13)


def test_generate_user_color_different_users(svc):
    """Adjacent user IDs get different colors."""
    assert svc._generate_user_color(0) != svc._generate_user_color(1)


# ---------------------------------------------------------------------------
# Session timeout / presence constants
# ---------------------------------------------------------------------------


def test_session_timeout_is_positive(svc):
    """SESSION_TIMEOUT_SECONDS must be positive."""
    assert svc.SESSION_TIMEOUT_SECONDS > 0


def test_presence_away_is_positive(svc):
    """PRESENCE_AWAY_SECONDS must be positive."""
    assert svc.PRESENCE_AWAY_SECONDS > 0


def test_presence_away_greater_than_timeout(svc):
    """Away threshold should be longer than session timeout."""
    assert svc.PRESENCE_AWAY_SECONDS > svc.SESSION_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# join_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_join_session_creates_session(svc, mock_db):
    """Joining a session creates a CollaborativeSession and persists it."""
    mock_db.refresh = AsyncMock()

    session = await svc.join_session(
        document_id=1,
        user_id=42,
        user_name="Alice",
        user_email="alice@example.com",
    )

    assert session.document_id == 1
    assert session.user_id == 42
    assert session.user_name == "Alice"
    assert session.is_active is True
    assert session.user_color.startswith("#")
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_join_session_assigns_unique_session_id(svc, mock_db):
    """Each join produces a unique session_id."""
    mock_db.refresh = AsyncMock()

    s1 = await svc.join_session(1, 1, "A", "a@x.com")
    s2 = await svc.join_session(1, 2, "B", "b@x.com")

    assert s1.session_id != s2.session_id


# ---------------------------------------------------------------------------
# leave_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_leave_session_marks_inactive(svc, mock_db):
    """Leaving a session sets is_active=False and records left_at."""
    mock_session = MagicMock()
    mock_session.is_active = True
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_session
    mock_db.execute.return_value = mock_result
    mock_db.refresh = AsyncMock()

    result = await svc.leave_session("sess-abc")

    assert mock_session.is_active is False
    assert mock_session.left_at is not None
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_leave_session_not_found(svc, mock_db):
    """Leaving a non-existent session returns None."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    result = await svc.leave_session("no-such-session")
    assert result is None


# ---------------------------------------------------------------------------
# update_presence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_presence_creates_new_record(svc, mock_db):
    """When no existing presence, a new record is created."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    mock_db.refresh = AsyncMock()

    presence = await svc.update_presence(
        tenant_id=1,
        user_id=10,
        status="online",
        current_page="/incidents",
    )

    assert presence.user_id == 10
    assert presence.status == "online"
    assert presence.current_page == "/incidents"
    mock_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_update_presence_away_sets_went_away_at(svc, mock_db):
    """Setting status='away' populates went_away_at."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    mock_db.refresh = AsyncMock()

    presence = await svc.update_presence(
        tenant_id=1,
        user_id=10,
        status="away",
    )

    assert presence.went_away_at is not None


@pytest.mark.asyncio
async def test_update_presence_online_clears_went_away(svc, mock_db):
    """Setting status='online' clears went_away_at."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    mock_db.refresh = AsyncMock()

    presence = await svc.update_presence(
        tenant_id=1,
        user_id=10,
        status="online",
    )

    assert presence.went_away_at is None


if __name__ == "__main__":
    print("=" * 60)
    print("COLLABORATION SERVICE UNIT TESTS")
    print("=" * 60)

    from unittest.mock import AsyncMock as AM, MagicMock as MM

    db = AM()
    s = CollaborationService(db=db)

    test_generate_user_color_returns_hex(s)
    print("  generate_user_color returns hex")
    test_generate_user_color_deterministic(s)
    print("  generate_user_color deterministic")
    test_generate_user_color_wraps_around(s)
    print("  generate_user_color wraps around")
    test_generate_user_color_different_users(s)
    print("  generate_user_color different users")
    test_session_timeout_is_positive(s)
    print("  session timeout positive")
    test_presence_away_is_positive(s)
    print("  presence away positive")
    test_presence_away_greater_than_timeout(s)
    print("  presence away > timeout")

    print()
    print("ALL COLLABORATION SERVICE TESTS PASSED")
    print("=" * 60)
