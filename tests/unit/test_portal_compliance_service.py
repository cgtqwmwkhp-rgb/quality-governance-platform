"""Unit tests for portal tool + van compliance helpers and clear-state."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.models.asset import AssetStatus
from src.domain.services.portal_compliance_service import (
    PortalComplianceService,
    derive_clear_state,
    exclusive_expiry_band,
    tool_display_band,
)


class _ScalarResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value


class _ScalarsResult:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def scalars(self) -> "_ScalarsResult":
        return self

    def all(self) -> list[object]:
        return self.values


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
    assert derive_clear_state(overdue=0, quarantined=1, due_30=0, open_p1=0, open_other_defects=0) == "blocked"
    assert derive_clear_state(overdue=0, quarantined=0, due_30=0, open_p1=1, open_other_defects=0) == "blocked"


def test_derive_clear_state_attention() -> None:
    assert derive_clear_state(overdue=1, quarantined=0, due_30=0, open_p1=0, open_other_defects=0) == "attention"
    assert derive_clear_state(overdue=0, quarantined=0, due_30=1, open_p1=0, open_other_defects=0) == "attention"
    assert derive_clear_state(overdue=0, quarantined=0, due_30=0, open_p1=0, open_other_defects=2) == "attention"
    assert (
        derive_clear_state(
            overdue=0,
            quarantined=0,
            due_30=0,
            open_p1=0,
            open_other_defects=0,
            van_assignment_issue=True,
        )
        == "attention"
    )


def test_derive_clear_state_clear() -> None:
    assert derive_clear_state(overdue=0, quarantined=0, due_30=0, open_p1=0, open_other_defects=0) == "clear"


@pytest.mark.parametrize("allocated_vehicle", [None, SimpleNamespace(vehicle_reg="OLD-VAN", assigned_driver_id=99)])
async def test_resolve_van_prefers_single_registry_claim_when_profile_allocation_is_stale(
    allocated_vehicle: object | None,
) -> None:
    profile = SimpleNamespace(allocated_vehicle_reg="OLD-VAN")
    claimed_vehicle = SimpleNamespace(vehicle_reg="NEW-VAN", assigned_driver_id=7)
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _ScalarResult(profile),
                _ScalarsResult([claimed_vehicle]),
                _ScalarResult(allocated_vehicle),
            ]
        )
    )

    resolved_profile, vehicle, empty_reason, conflict, claimed_regs = await PortalComplianceService(db)._resolve_van(
        user_id=7, tenant_id=3
    )

    assert resolved_profile is profile
    assert vehicle is claimed_vehicle
    assert empty_reason is None
    assert conflict is True
    assert claimed_regs == ["NEW-VAN"]


async def test_resolve_van_prefers_single_registry_claim_over_unassigned_profile_vehicle() -> None:
    profile = SimpleNamespace(allocated_vehicle_reg="OLD-VAN")
    claimed_vehicle = SimpleNamespace(vehicle_reg="NEW-VAN", assigned_driver_id=7)
    allocated_vehicle = SimpleNamespace(vehicle_reg="OLD-VAN", assigned_driver_id=None)
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _ScalarResult(profile),
                _ScalarsResult([claimed_vehicle]),
                _ScalarResult(allocated_vehicle),
            ]
        )
    )

    _, vehicle, empty_reason, conflict, claimed_regs = await PortalComplianceService(db)._resolve_van(
        user_id=7, tenant_id=3
    )

    assert vehicle is claimed_vehicle
    assert empty_reason is None
    assert conflict is True
    assert claimed_regs == ["NEW-VAN"]


async def test_resolve_van_keeps_valid_profile_vehicle_when_registry_has_multiple_claims() -> None:
    profile = SimpleNamespace(allocated_vehicle_reg="OLD-VAN")
    allocated_vehicle = SimpleNamespace(vehicle_reg="OLD-VAN", assigned_driver_id=7)
    extra_vehicle = SimpleNamespace(vehicle_reg="EXTRA-VAN", assigned_driver_id=7)
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _ScalarResult(profile),
                _ScalarsResult([allocated_vehicle, extra_vehicle]),
                _ScalarResult(allocated_vehicle),
            ]
        )
    )

    _, vehicle, empty_reason, conflict, claimed_regs = await PortalComplianceService(db)._resolve_van(
        user_id=7, tenant_id=3
    )

    assert vehicle is allocated_vehicle
    assert empty_reason is None
    assert conflict is True
    assert claimed_regs == ["OLD-VAN", "EXTRA-VAN"]
