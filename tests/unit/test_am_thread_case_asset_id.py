"""Unit tests for AM-THREAD case ↔ asset golden-thread FKs."""

from __future__ import annotations

from datetime import datetime, timezone

from src.api.schemas.incident import IncidentCreate, IncidentResponse, IncidentUpdate
from src.api.schemas.near_miss import NearMissCreate, NearMissResponse, NearMissUpdate
from src.api.schemas.rta import RTACreate, RTAResponse, RTAUpdate
from src.domain.models.incident import Incident, IncidentSeverity, IncidentStatus, IncidentType
from src.domain.models.near_miss import NearMiss
from src.domain.models.rta import RoadTrafficCollision, RTASeverity, RTAStatus


def test_incident_model_has_nullable_asset_id_fk():
    assert hasattr(Incident, "asset_id")
    column = Incident.__table__.c.asset_id
    assert column.nullable is True
    fks = list(column.foreign_keys)
    assert any(fk.column.table.name == "assets" for fk in fks)


def test_near_miss_model_has_nullable_asset_id_and_legacy_text():
    assert hasattr(NearMiss, "asset_id")
    assert hasattr(NearMiss, "asset_number")
    assert hasattr(NearMiss, "asset_type")
    column = NearMiss.__table__.c.asset_id
    assert column.nullable is True
    fks = list(column.foreign_keys)
    assert any(fk.column.table.name == "assets" for fk in fks)


def test_rta_model_has_nullable_asset_id_fk():
    assert hasattr(RoadTrafficCollision, "asset_id")
    column = RoadTrafficCollision.__table__.c.asset_id
    assert column.nullable is True
    fks = list(column.foreign_keys)
    assert any(fk.column.table.name == "assets" for fk in fks)


def test_incident_schemas_accept_asset_id():
    create = IncidentCreate(
        title="Forklift tip",
        description="Near tip in bay A",
        incident_date=datetime.now(timezone.utc),
        asset_id=42,
    )
    assert create.asset_id == 42

    update = IncidentUpdate(asset_id=42)
    assert update.asset_id == 42

    response = IncidentResponse(
        id=1,
        reference_number="INC-2026-0001",
        title="Forklift tip",
        description="Near tip in bay A",
        incident_type=IncidentType.OTHER,
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.REPORTED,
        incident_date=datetime.now(timezone.utc),
        reported_date=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        asset_id=42,
    )
    assert response.asset_id == 42


def test_near_miss_schemas_retain_legacy_and_accept_asset_id():
    create = NearMissCreate(
        reporter_name="Alex",
        contract="Main",
        location="Bay B",
        event_date=datetime.now(timezone.utc),
        description="Almost hit racking with pallet",
        asset_number="FE-001",
        asset_type="extinguisher",
        asset_id=7,
    )
    assert create.asset_id == 7
    assert create.asset_number == "FE-001"
    assert create.asset_type == "extinguisher"

    update = NearMissUpdate(asset_id=7, asset_number="FE-001")
    assert update.asset_id == 7
    assert update.asset_number == "FE-001"

    response = NearMissResponse(
        id=1,
        reference_number="NM-2026-0001",
        reporter_name="Alex",
        was_involved=True,
        contract="Main",
        location="Bay B",
        event_date=datetime.now(timezone.utc),
        description="Almost hit racking with pallet",
        witnesses_present=False,
        asset_number="FE-001",
        asset_type="extinguisher",
        asset_id=7,
        status="REPORTED",
        priority="MEDIUM",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert response.asset_id == 7
    assert response.asset_number == "FE-001"


def test_rta_schemas_accept_asset_id():
    now = datetime.now(timezone.utc)
    create = RTACreate(
        title="Depot collision",
        description="Low-speed contact",
        collision_date=now,
        reported_date=now,
        location="Depot gate",
        asset_id=99,
    )
    assert create.asset_id == 99

    update = RTAUpdate(asset_id=99)
    assert update.asset_id == 99

    response = RTAResponse(
        id=1,
        reference_number="RTA-2026-0001",
        title="Depot collision",
        description="Low-speed contact",
        severity=RTASeverity.DAMAGE_ONLY,
        status=RTAStatus.REPORTED,
        collision_date=now,
        reported_date=now,
        location="Depot gate",
        created_at=now,
        updated_at=now,
        asset_id=99,
    )
    assert response.asset_id == 99


def test_am_thread_migration_targets_case_tables():
    from pathlib import Path

    migration = Path("alembic/versions/20260714_am_thread_case_asset_id.py").read_text()
    assert 'revision: str = "20260714_am_thread"' in migration
    assert 'down_revision' in migration and "20260714_safety_am_model" in migration
    assert '"incidents"' in migration
    assert '"near_misses"' in migration
    assert '"road_traffic_collisions"' in migration
    assert "asset_id" in migration
