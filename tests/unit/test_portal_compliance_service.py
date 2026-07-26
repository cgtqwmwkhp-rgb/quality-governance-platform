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


def _clear_state(**overrides: object) -> str:
    kwargs: dict[str, object] = {
        "overdue": 0,
        "quarantined": 0,
        "due_30": 0,
        "open_p1": 0,
        "open_other_defects": 0,
        "has_tool_data": True,
        "has_van_data": True,
    }
    kwargs.update(overrides)
    return derive_clear_state(**kwargs)  # type: ignore[arg-type]


def test_derive_clear_state_blocked_on_p1_or_quarantine() -> None:
    assert _clear_state(quarantined=1) == "blocked"
    assert _clear_state(open_p1=1) == "blocked"


def test_derive_clear_state_attention() -> None:
    assert _clear_state(overdue=1) == "attention"
    assert _clear_state(due_30=1) == "attention"
    assert _clear_state(open_other_defects=2) == "attention"
    assert _clear_state(van_assignment_issue=True) == "attention"


def test_derive_clear_state_clear_requires_data() -> None:
    """PX-320: 'clear' must mean 'we checked and nothing is outstanding'.

    Previously this test asserted that all-zero counts yield "clear", which
    locked in the defect: a person with no assets and no van was told they were
    compliant. Zero counts only mean "clear" when there was something to count.
    """
    assert _clear_state() == "clear"
    assert _clear_state(has_tool_data=True, has_van_data=False) == "clear"
    assert _clear_state(has_tool_data=False, has_van_data=True) == "clear"


def test_derive_clear_state_no_data_is_not_clear() -> None:
    assert _clear_state(has_tool_data=False, has_van_data=False) == "no_data"


def test_derive_clear_state_real_findings_outrank_no_data() -> None:
    """A finding is evidence we hold data, even if the summaries look empty."""
    assert _clear_state(quarantined=1, has_tool_data=False, has_van_data=False) == "blocked"
    assert _clear_state(van_assignment_issue=True, has_tool_data=False, has_van_data=False) == "attention"


def _empty_tool_summary() -> dict[str, int]:
    return {
        "total": 0,
        "overdue": 0,
        "due_30": 0,
        "due_60": 0,
        "due_90": 0,
        "in_date": 0,
        "quarantined": 0,
        "mine": 0,
        "on_van": 0,
    }


def _van_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "linked_driver": False,
        "vehicle_reg": None,
        "assignment_conflict": False,
        "conflicting_regs": [],
        "empty_reason": "no_van",
        "daily_last_at": None,
        "daily_pass": None,
        "monthly_last_at": None,
        "open_defects": [],
        "defect_counts": {"p1": 0, "p2": 0, "p3": 0, "total": 0},
    }
    payload.update(overrides)
    return payload


async def test_my_compliance_reports_no_data_when_nothing_is_recorded() -> None:
    """PX-320: no assets and no van must not read as 'clear to work'."""
    service = PortalComplianceService(SimpleNamespace())
    service.my_tools = AsyncMock(  # type: ignore[method-assign]
        return_value={"items": [], "summary": _empty_tool_summary(), "empty_reason": "no_tools"}
    )
    service.my_van_status = AsyncMock(return_value=_van_payload())  # type: ignore[method-assign]

    payload = await service.my_compliance(user_id=7, tenant_id=3)

    assert payload["clear_state"] == "no_data"


async def test_my_compliance_is_clear_when_a_van_is_known_and_sound() -> None:
    service = PortalComplianceService(SimpleNamespace())
    service.my_tools = AsyncMock(  # type: ignore[method-assign]
        return_value={"items": [], "summary": _empty_tool_summary(), "empty_reason": "no_tools"}
    )
    service.my_van_status = AsyncMock(  # type: ignore[method-assign]
        return_value=_van_payload(vehicle_reg="AB12CDE", linked_driver=True, empty_reason=None)
    )

    payload = await service.my_compliance(user_id=7, tenant_id=3)

    assert payload["clear_state"] == "clear"


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
