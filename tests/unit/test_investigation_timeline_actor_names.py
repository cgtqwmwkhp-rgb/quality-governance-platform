"""Unit tests: GET /investigations/{id}/timeline resolves actor names (PX-142).

The timeline response carried only `actor_id`, so the UI had nothing to render but
an opaque "Actor #11". The actor is a plain FK to `users`; this covers the join.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.investigations import _actor_names_for_events, get_investigation_timeline


def _user(user_id: int, first: str, last: str, email: str):
    user = SimpleNamespace(id=user_id, first_name=first, last_name=last, email=email)
    user.full_name = f"{first} {last}"
    return user


def _db_returning_users(users):
    db = AsyncMock()
    result = MagicMock()
    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=users)))
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_resolves_display_names_for_the_page_of_events():
    events = [SimpleNamespace(actor_id=11), SimpleNamespace(actor_id=12)]
    db = _db_returning_users(
        [_user(11, "Dana", "Whitfield", "dana@example.com"), _user(12, "Ilse", "Byrne", "ilse@example.com")]
    )

    assert await _actor_names_for_events(db, events) == {11: "Dana Whitfield", 12: "Ilse Byrne"}


@pytest.mark.asyncio
async def test_falls_back_to_email_when_the_user_has_no_name():
    events = [SimpleNamespace(actor_id=11)]
    db = _db_returning_users([_user(11, "", "", "nameless@example.com")])

    assert await _actor_names_for_events(db, events) == {11: "nameless@example.com"}


@pytest.mark.asyncio
async def test_skips_the_user_query_entirely_when_no_event_has_an_actor():
    db = _db_returning_users([])

    assert await _actor_names_for_events(db, [SimpleNamespace(actor_id=None)]) == {}
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_timeline_response_carries_actor_name_alongside_actor_id():
    event = SimpleNamespace(
        id=1,
        event_type="STATUS_CHANGED",
        field_path="status",
        old_value="in_progress",
        new_value="closed",
        actor_id=11,
        event_metadata=None,
        version=3,
        created_at=datetime(2026, 7, 20, 9, 0, 0),
    )

    db = AsyncMock()
    events_result = MagicMock()
    events_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[event])))
    db.execute = AsyncMock(return_value=events_result)
    db.scalar = AsyncMock(return_value=1)

    with (
        patch("src.api.routes.investigations._get_investigation_or_404", new=AsyncMock()),
        patch(
            "src.api.routes.investigations._actor_names_for_events",
            new=AsyncMock(return_value={11: "Dana Whitfield"}),
        ),
    ):
        response = await get_investigation_timeline(
            investigation_id=42,
            db=db,
            current_user=SimpleNamespace(id=11, tenant_id=7),
            page=1,
            page_size=20,
            event_type=None,
        )

    assert response["items"][0]["actor_id"] == 11
    assert response["items"][0]["actor_name"] == "Dana Whitfield"


@pytest.mark.asyncio
async def test_actor_name_is_null_when_the_event_has_no_actor():
    event = SimpleNamespace(
        id=1,
        event_type="CREATED",
        field_path=None,
        old_value=None,
        new_value=None,
        actor_id=None,
        event_metadata=None,
        version=1,
        created_at=datetime(2026, 7, 20, 9, 0, 0),
    )

    db = AsyncMock()
    events_result = MagicMock()
    events_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[event])))
    db.execute = AsyncMock(return_value=events_result)
    db.scalar = AsyncMock(return_value=1)

    with patch("src.api.routes.investigations._get_investigation_or_404", new=AsyncMock()):
        response = await get_investigation_timeline(
            investigation_id=42,
            db=db,
            current_user=SimpleNamespace(id=11, tenant_id=7),
            page=1,
            page_size=20,
            event_type=None,
        )

    assert response["items"][0]["actor_name"] is None
