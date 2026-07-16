"""Unit tests for governance calendar feed helpers."""

from datetime import date, datetime, timezone

from src.domain.services.calendar_feed_service import _status_for, _iso_date, EVENT_TYPES


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
