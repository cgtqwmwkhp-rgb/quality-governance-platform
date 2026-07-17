"""Unit tests for governance calendar feed helpers."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.calendar_feed_service import (
    CALENDAR_FEED_SOURCES,
    EVENT_TYPES,
    CalendarFeedService,
    _iso_date,
    _status_for,
)


def test_event_types_cover_ui_chips() -> None:
    assert EVENT_TYPES == frozenset({"audit", "deadline", "review", "training", "meeting"})


def test_status_for_overdue_today_upcoming() -> None:
    today = date(2026, 7, 16)
    past = datetime(2026, 7, 10, tzinfo=timezone.utc)
    same = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
    future = datetime(2026, 7, 20, tzinfo=timezone.utc)

    assert _status_for(past, "open", today=today) == "overdue"
    assert _status_for(same, "open", today=today) == "today"
    assert _status_for(future, "open", today=today) == "upcoming"
    assert _status_for(past, "completed", today=today) == "completed"


def test_iso_date_normalises_naive_utc() -> None:
    assert _iso_date(datetime(2026, 1, 5, 15, 0, 0)) == "2026-01-05"


@pytest.mark.asyncio
async def test_get_feed_fail_closed_without_tenant_id() -> None:
    db = AsyncMock()
    service = CalendarFeedService(db, tenant_id=None)

    feed = await service.get_feed(start=date(2026, 7, 1), end=date(2026, 7, 31))

    assert feed["total"] == 0
    assert feed["events"] == []
    assert feed["sources_ok"] == []
    assert feed["sources_failed"] == list(CALENDAR_FEED_SOURCES)
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_capa_href_uses_actions_source_type_contract() -> None:
    db = AsyncMock()
    due = datetime(2026, 7, 15, 12, 0, 0)
    capa_row = MagicMock(
        id=42,
        title="Fix guard rail",
        reference_number="CAPA-0042",
        due_date=due,
        status=MagicMock(value="open"),
        priority=MagicMock(value="high"),
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [capa_row]
    db.execute = AsyncMock(return_value=result)

    service = CalendarFeedService(db, tenant_id=10)
    events = await service._load_capa_actions(
        datetime(2026, 7, 1, tzinfo=timezone.utc),
        datetime(2026, 7, 31, tzinfo=timezone.utc),
        date(2026, 7, 16),
    )

    assert len(events) == 1
    assert events[0]["href"] == "/actions?sourceType=capa&sourceId=42"
    assert "source_type=" not in events[0]["href"]
