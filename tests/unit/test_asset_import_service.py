"""Unit tests for AM-IMPORT CSV asset import service."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.exceptions import BadRequestError, ValidationError
from src.domain.models.asset import AssetStatus
from src.domain.services.asset_import_service import AssetImportService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "asset_import"


@pytest.fixture
def valid_csv() -> bytes:
    return (FIXTURES / "valid_tools.csv").read_bytes()


@pytest.fixture
def invalid_csv() -> bytes:
    return (FIXTURES / "invalid_tools.csv").read_bytes()


def _service_with_lookups(
    *,
    types: list | None = None,
    locations: list | None = None,
    users_by_email: dict | None = None,
    users_by_id: dict | None = None,
    existing_numbers: set | None = None,
    asset_service: MagicMock | None = None,
) -> AssetImportService:
    db = MagicMock()
    service = AssetImportService(db, asset_service=asset_service)
    fire = SimpleNamespace(id=10, name="Fire Extinguisher")
    toolkit = SimpleNamespace(id=11, name="Engineer Tool Kit")
    type_list = types if types is not None else [fire, toolkit]
    setattr(service, "_load_asset_types", AsyncMock()
        return_value={t.name.lower(): t for t in type_list}
    )
    loc_list = locations if locations is not None else [SimpleNamespace(id=5, name="Main Depot")]
    setattr(service, "_load_locations", AsyncMock()
        return_value={loc.name.lower(): loc for loc in loc_list}
    )
    setattr(service, "_load_users_by_email", AsyncMock()
        return_value=(
            users_by_email
            if users_by_email is not None
            else {"owner@example.com": SimpleNamespace(id=12, email="owner@example.com")}
        )
    )
    setattr(service, "_load_users_by_id", AsyncMock()
        return_value=users_by_id if users_by_id is not None else {}
    )
    setattr(service, "_existing_asset_numbers", AsyncMock()
        return_value=existing_numbers if existing_numbers is not None else set()
    )
    return service


def test_parse_csv_normalises_aliases(valid_csv: bytes):
    rows = AssetImportService.parse_csv(valid_csv)
    assert len(rows) == 2
    assert rows[0]["asset_number"] == "FE-100"
    assert rows[0]["type"] == "Fire Extinguisher"
    assert rows[0]["serial"] == "SN-100"
    assert rows[1]["vehicle_reg"] == "AB12 CDE"
    assert rows[1]["location_name"] == ""


def test_parse_csv_accepts_asset_type_alias(invalid_csv: bytes):
    rows = AssetImportService.parse_csv(invalid_csv)
    assert "type" in rows[0]
    assert rows[0]["type"] == "Fire Extinguisher"


def test_parse_csv_requires_headers():
    with pytest.raises(BadRequestError, match="required column"):
        AssetImportService.parse_csv(b"asset_number,name\nA1,Tool\n")


def test_parse_csv_rejects_empty():
    with pytest.raises(BadRequestError, match="empty"):
        AssetImportService.parse_csv(b"")


@pytest.mark.asyncio
async def test_dry_run_valid_report(valid_csv: bytes):
    service = _service_with_lookups()
    report = await service.dry_run(valid_csv, tenant_id=3)

    assert report.dry_run is True
    assert report.ok is True
    assert report.total_rows == 2
    assert report.valid_rows == 2
    assert report.error_rows == 0
    assert report.preview[0]["asset_number"] == "FE-100"
    assert report.preview[0]["location_id"] == 5
    assert report.preview[0]["owner_user_id"] == 12
    assert report.preview[1]["vehicle_reg"] == "AB12 CDE"
    assert report.preview[1]["location_id"] is None


@pytest.mark.asyncio
async def test_dry_run_collects_row_errors(invalid_csv: bytes):
    service = _service_with_lookups(types=[SimpleNamespace(id=10, name="Fire Extinguisher")])
    report = await service.dry_run(invalid_csv, tenant_id=3)

    assert report.ok is False
    assert report.error_rows >= 5
    codes = {e.code for e in report.errors}
    assert "REQUIRED" in codes
    assert "DUPLICATE_IN_FILE" in codes
    assert "ASSIGNMENT_XOR" in codes
    assert "UNKNOWN_TYPE" in codes
    assert "INVALID_STATUS" in codes
    assert "INVALID_DATE" in codes


@pytest.mark.asyncio
async def test_dry_run_flags_existing_asset_number(valid_csv: bytes):
    service = _service_with_lookups(existing_numbers={"FE-100"})
    report = await service.dry_run(valid_csv, tenant_id=3)
    assert report.ok is False
    assert any(e.code == "DUPLICATE_EXISTING" for e in report.errors)


@pytest.mark.asyncio
async def test_commit_rejects_invalid(invalid_csv: bytes):
    service = _service_with_lookups(types=[SimpleNamespace(id=10, name="Fire Extinguisher")])

    with pytest.raises(ValidationError) as exc_info:
        await service.commit(invalid_csv, user_id=1, tenant_id=3)

    assert exc_info.value.code == "ASSET_IMPORT_VALIDATION_FAILED"
    assert exc_info.value.details["error_rows"] >= 1


@pytest.mark.asyncio
async def test_commit_creates_assets(valid_csv: bytes):
    asset_service = MagicMock()
    created: list = []

    async def _create(data, *, user_id, tenant_id):
        asset = SimpleNamespace(id=100 + len(created), **data)
        created.append(asset)
        return asset

    asset_service.create_asset = AsyncMock(side_effect=_create)
    service = _service_with_lookups(asset_service=asset_service)

    result = await service.commit(valid_csv, user_id=7, tenant_id=3)
    assert result.created_count == 2
    assert result.created_asset_ids == [100, 101]
    assert asset_service.create_asset.await_count == 2
    first_kwargs = asset_service.create_asset.await_args_list[0].kwargs
    assert first_kwargs["user_id"] == 7
    assert first_kwargs["tenant_id"] == 3
    payload = asset_service.create_asset.await_args_list[0].args[0]
    assert payload["asset_number"] == "FE-100"
    assert payload["location_id"] == 5
    assert payload["owner_user_id"] == 12
    assert payload["status"] == AssetStatus.ACTIVE.value
    assert isinstance(payload["expiry_date"], datetime)
    assert payload["expiry_date"].tzinfo is not None


def test_schema_validation_report_response():
    from src.api.schemas.asset import AssetImportCommitResponse, AssetImportValidationReportResponse

    report = AssetImportValidationReportResponse(
        dry_run=True,
        total_rows=1,
        valid_rows=1,
        error_rows=0,
        ok=True,
        errors=[],
        preview=[],
    )
    assert report.ok is True

    commit = AssetImportCommitResponse(
        created_count=1,
        created_asset_ids=[9],
        report=report.model_copy(update={"dry_run": False}),
    )
    assert commit.created_count == 1
