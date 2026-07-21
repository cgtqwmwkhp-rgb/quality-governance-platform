"""Unit tests for portal tool + van compliance helpers and clear-state."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.domain.models.asset import AssetStatus
from src.domain.services.portal_compliance_service import (
    derive_clear_state,
    exclusive_expiry_band,
    tool_display_band,
)


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (-1, "overdue"),
        (0, "due_30"),
        (30, "due_30"),
        (31, "due_60"),
        (60, "due_60"),
        (61, "due_90"),
        (90, "due_90"),
        (91, "in_date"),
    ],
)
def test_exclusive_expiry_band(days: int, expected: str) -> None:
    now = datetime(2026, 7, 21, tzinfo=timezone.utc)
    expiry = now + timedelta(days=days)
    assert exclusive_expiry_band(expiry, now=now) == expected


def test_exclusive_expiry_band_none() -> None:
    assert exclusive_expiry_band(None) == "none"


def test_tool_display_band_quarantined_wins() -> None:
    asset = SimpleNamespace(status=AssetStatus.QUARANTINED, expiry_date=datetime.now(timezone.utc))
    assert tool_display_band(asset) == "quarantined"


def test_derive_clear_state_blocked_on_p1_or_quarantine() -> None:
    assert (
        derive_clear_state(overdue=0, quarantined=1, due_30=0, open_p1=0, open_other_defects=0)
        == "blocked"
    )
    assert (
        derive_clear_state(overdue=0, quarantined=0, due_30=0, open_p1=1, open_other_defects=0)
        == "blocked"
    )


def test_derive_clear_state_attention() -> None:
    assert (
        derive_clear_state(overdue=1, quarantined=0, due_30=0, open_p1=0, open_other_defects=0)
        == "attention"
    )
    assert (
        derive_clear_state(overdue=0, quarantined=0, due_30=1, open_p1=0, open_other_defects=0)
        == "attention"
    )
    assert (
        derive_clear_state(overdue=0, quarantined=0, due_30=0, open_p1=0, open_other_defects=2)
        == "attention"
    )


def test_derive_clear_state_clear() -> None:
    assert (
        derive_clear_state(overdue=0, quarantined=0, due_30=0, open_p1=0, open_other_defects=0)
        == "clear"
    )
