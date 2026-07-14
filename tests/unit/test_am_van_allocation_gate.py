"""Unit tests for AM-VAN allocation_gate Asset consult + dual-read expiry."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models.asset import AssetCategory, AssetStatus
from src.domain.models.vehicle_registry import FleetStatus
from src.domain.services import allocation_gate as gate


def _asset(
    *,
    id: int = 1,
    asset_number: str = "KIT-001",
    name: str = "Kit item",
    type_name: str = "Fire Extinguisher",
    category: AssetCategory = AssetCategory.SAFETY,
    status: AssetStatus = AssetStatus.ACTIVE,
    expiry_date: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        asset_number=asset_number,
        name=name,
        asset_type_id=10,
        asset_type=SimpleNamespace(name=type_name, category=category),
        status=status,
        expiry_date=expiry_date,
        vehicle_reg="AB12CDE",
    )


def _vehicle(**overrides):
    now = datetime.now(timezone.utc)
    base = {
        "vehicle_reg": "AB12CDE",
        "fleet_status": FleetStatus.ACTIVE,
        "asset_id": None,
        "last_daily_check_at": now - timedelta(hours=2),
        "road_tax_expiry": now + timedelta(days=90),
        "fire_extinguisher_expiry": now + timedelta(days=60),
        "tooling_calibration_expiry": now + timedelta(days=60),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _mock_db_for_gate(
    vehicle,
    *,
    open_p1: int = 0,
    open_p2: int = 0,
    child_assets: list | None = None,
    linked_asset=None,
):
    db = MagicMock()
    child_assets = child_assets or []

    vehicle_result = MagicMock()
    vehicle_result.scalar_one_or_none.return_value = vehicle

    p1_result = MagicMock()
    p1_result.scalar.return_value = open_p1
    p2_result = MagicMock()
    p2_result.scalar.return_value = open_p2

    child_result = MagicMock()
    child_result.scalars.return_value.all.return_value = child_assets

    linked_result = MagicMock()
    linked_result.scalar_one_or_none.return_value = linked_asset

    # check_allocation execute order:
    # 1 vehicle, 2 p1 count, 3 p2 count, 4 child assets, 5 linked asset (optional)
    execute_returns = [vehicle_result, p1_result, p2_result, child_result]
    if vehicle is not None and getattr(vehicle, "asset_id", None) is not None:
        execute_returns.append(linked_result)

    db.execute = AsyncMock(side_effect=execute_returns)
    return db


def test_dual_read_prefers_child_asset_expiry():
    now = datetime.now(timezone.utc)
    registry = now + timedelta(days=90)
    child = now + timedelta(days=10)
    assets = [_asset(expiry_date=child, type_name="Fire Extinguisher")]

    expiry, source = gate.dual_read_expiry(registry, assets, gate.FIRE_EXTINGUISHER_TYPE_HINTS)
    assert source == "asset"
    assert expiry == child


def test_dual_read_falls_back_to_registry():
    now = datetime.now(timezone.utc)
    registry = now + timedelta(days=45)
    expiry, source = gate.dual_read_expiry(registry, [], gate.FIRE_EXTINGUISHER_TYPE_HINTS)
    assert source == "registry"
    assert expiry == registry


def test_build_kit_compliance_payload_marks_kit_assets():
    now = datetime.now(timezone.utc)
    vehicle = _vehicle(fire_extinguisher_expiry=now + timedelta(days=40))
    assets = [
        _asset(id=7, type_name="First Aid Kit", expiry_date=now + timedelta(days=5)),
        _asset(id=8, type_name="Fire Extinguisher", expiry_date=now - timedelta(days=1)),
    ]
    payload = gate.build_kit_compliance_payload(vehicle, assets)
    assert payload["fire_extinguisher_expiry_source"] == "asset"
    assert payload["fire_extinguisher_expiry_status"] == "overdue"
    assert len(payload["assets"]) == 2
    assert all(item["is_kit_asset"] for item in payload["assets"])


@pytest.mark.asyncio
async def test_gate_blocks_linked_asset_vor():
    vehicle = _vehicle(asset_id=99)
    linked = _asset(id=99, asset_number="VAN-ASSET", status=AssetStatus.VOR, type_name="Van")
    db = _mock_db_for_gate(vehicle, linked_asset=linked, child_assets=[])

    decision = await gate.check_allocation(db, "AB12CDE", tenant_id=1)
    assert decision.allowed is False
    assert any("VOR" in r.upper() or "vor" in r for r in decision.reasons)


@pytest.mark.asyncio
async def test_gate_blocks_quarantined_child_asset():
    vehicle = _vehicle()
    child = _asset(status=AssetStatus.QUARANTINED, type_name="First Aid Kit")
    db = _mock_db_for_gate(vehicle, child_assets=[child])

    decision = await gate.check_allocation(db, "AB12CDE", tenant_id=1)
    assert decision.allowed is False
    assert any("quarantined" in r for r in decision.reasons)


@pytest.mark.asyncio
async def test_gate_blocks_overdue_child_asset_expiry():
    now = datetime.now(timezone.utc)
    vehicle = _vehicle(fire_extinguisher_expiry=now + timedelta(days=90))
    child = _asset(
        type_name="Fire Extinguisher",
        expiry_date=now - timedelta(days=2),
    )
    db = _mock_db_for_gate(vehicle, child_assets=[child])

    decision = await gate.check_allocation(db, "AB12CDE", tenant_id=1)
    assert decision.allowed is False
    assert any("overdue" in r.lower() for r in decision.reasons)


@pytest.mark.asyncio
async def test_gate_uses_registry_fire_expiry_when_no_child():
    now = datetime.now(timezone.utc)
    vehicle = _vehicle(fire_extinguisher_expiry=now - timedelta(days=1))
    db = _mock_db_for_gate(vehicle, child_assets=[])

    decision = await gate.check_allocation(db, "AB12CDE", tenant_id=1)
    assert decision.allowed is False
    assert any("Fire extinguisher expired" in r for r in decision.reasons)


@pytest.mark.asyncio
async def test_gate_warns_tooling_registry_expired():
    now = datetime.now(timezone.utc)
    vehicle = _vehicle(
        fire_extinguisher_expiry=now + timedelta(days=90),
        tooling_calibration_expiry=now - timedelta(days=1),
    )
    db = _mock_db_for_gate(vehicle, child_assets=[])

    decision = await gate.check_allocation(db, "AB12CDE", tenant_id=1)
    assert decision.allowed is True
    assert any("Tooling calibration expired" in w for w in decision.expiry_warnings)
