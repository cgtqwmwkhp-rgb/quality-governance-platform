"""Unit tests for Compliance Schedule date/status policy (Wave 0)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from src.domain.services import compliance_schedule_policy as policy


def test_add_months_clamps_january_31_to_february_28_non_leap():
    assert policy.add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_add_months_clamps_january_31_to_february_29_leap_year():
    assert policy.add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)


def test_add_months_preserves_mid_month_day():
    assert policy.add_months(date(2026, 1, 15), 1) == date(2026, 2, 15)


def test_add_months_across_year_boundary():
    assert policy.add_months(date(2026, 11, 30), 2) == date(2027, 1, 30)


def test_derive_status_bands():
    now = date(2026, 6, 1)
    assert policy.derive_status(now, date(2026, 7, 15)) == "current"
    assert policy.derive_status(now, date(2026, 6, 20)) == "due_soon"
    assert policy.derive_status(now, date(2026, 5, 31)) == "overdue"
    assert policy.derive_status(now, None) is None


def test_derive_status_due_soon_boundary_inclusive():
    now = date(2026, 6, 1)
    assert policy.derive_status(now, date(2026, 7, 1), due_soon_days=30) == "due_soon"
    assert policy.derive_status(now, date(2026, 7, 2), due_soon_days=30) == "current"


def test_classify_due_band_windows():
    now = date(2026, 6, 1)
    assert policy.classify_due_band(date(2026, 5, 20), now=now) == "overdue"
    assert policy.classify_due_band(date(2026, 6, 5), now=now) == "due_7"
    assert policy.classify_due_band(date(2026, 6, 20), now=now) == "due_30"
    assert policy.classify_due_band(date(2026, 7, 10), now=now) == "due_60"
    assert policy.classify_due_band(date(2026, 9, 1), now=now) is None


def test_compute_next_due_schedule_preserves_anniversary():
    next_due = policy.compute_next_due(
        "schedule",
        previous_due=date(2026, 3, 1),
        completed_at=date(2026, 3, 20),  # late — must not shift anniversary
        frequency_months=12,
    )
    assert next_due == date(2027, 3, 1)


def test_compute_next_due_completion_resets_from_work():
    next_due = policy.compute_next_due(
        "completion",
        previous_due=date(2026, 3, 1),
        completed_at=date(2026, 3, 20),
        frequency_months=12,
    )
    assert next_due == date(2027, 3, 20)


def test_compute_next_due_completion_requires_completed_at():
    with pytest.raises(ValueError, match="completed_at"):
        policy.compute_next_due(
            "completion",
            previous_due=date(2026, 3, 1),
            frequency_months=12,
        )


def test_compute_next_due_supports_frequency_days():
    assert (
        policy.compute_next_due(
            "schedule",
            previous_due=date(2026, 1, 1),
            frequency_days=14,
        )
        == date(2026, 1, 15)
    )


def test_module_never_mentions_expired():
    source = Path(policy.__file__).read_text(encoding="utf-8")
    assert "Expired" not in source
    assert "expired" not in source.lower()


def test_datetime_inputs_normalise_to_dates():
    now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    assert policy.derive_status(now, datetime(2026, 5, 1, tzinfo=timezone.utc)) == "overdue"
    assert policy.add_months(datetime(2026, 1, 31, tzinfo=timezone.utc), 1) == date(2026, 2, 28)
