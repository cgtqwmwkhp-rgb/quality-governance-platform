"""Unit tests for AM-MODEL Safety Asset Management spine extensions."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.routes.capa import CAPACreate
from src.api.schemas.asset import AssetCreate, AssetResponse, LocationCreate, LocationResponse
from src.api.schemas.capa import CAPAResponse
from src.domain.exceptions import BadRequestError
from src.domain.models.asset import AssetStatus
from src.domain.models.capa import CAPAAction, CAPAPriority, CAPAStatus, CAPAType
from src.domain.models.evidence_asset import EvidenceSourceModule
from src.domain.models.location import LocationKind
from src.domain.services.asset_service import AssetService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_db() -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)
    return db


# ---------------------------------------------------------------------------
# Enum / model surface
# ---------------------------------------------------------------------------


def test_asset_status_includes_quarantined():
    assert AssetStatus.QUARANTINED.value == "quarantined"
    assert {s.value for s in AssetStatus} >= {
        "active",
        "vor",
        "maintenance",
        "decommissioned",
        "quarantined",
    }


def test_evidence_source_module_accepts_asset():
    assert EvidenceSourceModule.ASSET.value == "asset"
    assert EvidenceSourceModule("asset") is EvidenceSourceModule.ASSET


def test_capa_action_has_asset_id_column():
    assert hasattr(CAPAAction, "asset_id")
    column = CAPAAction.__table__.c.asset_id
    assert column.nullable is True


def test_capa_create_and_response_accept_asset_id():
    create = CAPACreate(
        title="Replace extinguisher",
        capa_type=CAPAType.CORRECTIVE,
        priority=CAPAPriority.HIGH,
        asset_id=42,
    )
    assert create.asset_id == 42

    response = CAPAResponse(
        id=1,
        reference_number="CAPA-2026-0001",
        title="Replace extinguisher",
        capa_type=CAPAType.CORRECTIVE,
        status=CAPAStatus.OPEN,
        priority=CAPAPriority.HIGH,
        created_by_id=1,
        created_at=datetime.now(timezone.utc),
        asset_id=42,
    )
    assert response.asset_id == 42


# ---------------------------------------------------------------------------
# Location create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_location():
    db = _mock_db()

    async def _refresh(obj):
        obj.id = 11
        obj.created_at = datetime.now(timezone.utc)
        obj.updated_at = obj.created_at

    db.refresh = AsyncMock(side_effect=_refresh)

    service = AssetService(db)
    location = await service.create_location(
        {"name": "Main Depot", "kind": "site"},
        user_id=7,
        tenant_id=3,
    )

    assert db.add.call_count == 1
    created = db.add.call_args[0][0]
    assert created.name == "Main Depot"
    assert created.kind == LocationKind.SITE
    assert created.tenant_id == 3
    assert created.created_by_id == 7
    assert location.id == 11

    schema = LocationCreate(name="Main Depot", kind="site")
    assert schema.kind == "site"
    response = LocationResponse(
        id=11,
        name="Main Depot",
        kind="site",
        is_active=True,
        tenant_id=3,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert response.id == 11


# ---------------------------------------------------------------------------
# Asset with owner / expiry / location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_asset_with_owner_expiry_location():
    db = _mock_db()
    expiry = datetime(2026, 12, 1, tzinfo=timezone.utc)

    async def _refresh(obj):
        if not getattr(obj, "id", None):
            obj.id = 99
        if not getattr(obj, "external_id", None):
            obj.external_id = "ext-99"
        obj.created_at = datetime.now(timezone.utc)
        obj.updated_at = obj.created_at

    db.refresh = AsyncMock(side_effect=_refresh)

    service = AssetService(db)
    asset = await service.create_asset(
        {
            "asset_type_id": 1,
            "asset_number": "FE-001",
            "name": "Extinguisher Bay A",
            "location_id": 5,
            "owner_user_id": 12,
            "expiry_date": expiry,
            "status": "active",
        },
        user_id=7,
        tenant_id=3,
    )

    created_asset = next(c[0][0] for c in db.add.call_args_list if hasattr(c[0][0], "asset_number"))
    assert created_asset.location_id == 5
    assert created_asset.owner_user_id == 12
    assert created_asset.expiry_date == expiry
    assert created_asset.vehicle_reg is None
    assert asset.asset_number == "FE-001"

    # Initial assignment event recorded
    event = next(c[0][0] for c in db.add.call_args_list if c[0][0].__class__.__name__ == "AssetAssignmentEvent")
    assert event.to_location_id == 5
    assert event.to_owner_user_id == 12
    assert event.from_location_id is None

    schema = AssetCreate(
        asset_type_id=1,
        asset_number="FE-001",
        name="Extinguisher Bay A",
        location_id=5,
        owner_user_id=12,
        expiry_date=expiry,
    )
    assert schema.location_id == 5
    assert schema.owner_user_id == 12

    response = AssetResponse(
        id=99,
        external_id="ext-99",
        asset_type_id=1,
        asset_number="FE-001",
        name="Extinguisher Bay A",
        location_id=5,
        owner_user_id=12,
        expiry_date=expiry,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert response.location_id == 5
    assert response.expiry_date == expiry


# ---------------------------------------------------------------------------
# XOR assignment validation
# ---------------------------------------------------------------------------


def test_xor_assignment_rejects_both_location_and_vehicle():
    with pytest.raises(BadRequestError, match="location XOR vehicle"):
        AssetService._assert_location_xor_vehicle(10, "AB12CDE")


def test_xor_assignment_allows_location_only():
    AssetService._assert_location_xor_vehicle(10, None)
    AssetService._assert_location_xor_vehicle(10, "")
    AssetService._assert_location_xor_vehicle(10, "   ")


def test_xor_assignment_allows_vehicle_only():
    AssetService._assert_location_xor_vehicle(None, "AB12CDE")


@pytest.mark.asyncio
async def test_create_asset_rejects_location_and_vehicle():
    db = _mock_db()
    service = AssetService(db)
    with pytest.raises(BadRequestError, match="location XOR vehicle"):
        await service.create_asset(
            {
                "asset_type_id": 1,
                "asset_number": "FE-002",
                "name": "Bad assignment",
                "location_id": 3,
                "vehicle_reg": "AB12CDE",
            },
            user_id=1,
            tenant_id=1,
        )
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_update_asset_rejects_xor_violation():
    db = _mock_db()
    existing = SimpleNamespace(
        id=5,
        location_id=None,
        vehicle_reg="AB12CDE",
        owner_user_id=None,
        tenant_id=1,
        status="active",
        updated_by_id=None,
        updated_at=None,
    )

    service = AssetService(db)
    service._get_entity = AsyncMock(return_value=existing)  # type: ignore[method-assign]

    with pytest.raises(BadRequestError, match="location XOR vehicle"):
        await service.update_asset(
            5,
            {"location_id": 9},
            tenant_id=1,
            actor_user_id=2,
        )
