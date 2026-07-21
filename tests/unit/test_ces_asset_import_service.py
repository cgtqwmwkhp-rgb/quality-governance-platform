"""Unit tests for CES Calibrations XLSX import."""

from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from openpyxl import Workbook

from src.domain.services.ces_asset_import_parser import normalise_ces_row, normalise_status, split_location
from src.domain.services.ces_asset_import_service import CesAssetImportService, ValidatedCesRow


def _row(**overrides):
    raw = {
        "__row__": 2,
        "location": "Plantexpand; Engineer: Jane Smith",
        "equipment_type": "Gas Detector",
        "make": "MSA",
        "model": "Altair",
        "capacity": "4 gas",
        "serial_number": "CES-001",
        "asset_id": "A-1",
        "qr_code": "PLA-QR-1",
        "last_inspection": "01/07/2026",
        "next_inspection": "01/07/2027",
        "status": "Pass",
    }
    raw.update(overrides)
    return normalise_ces_row(raw)


def _service(existing=None):
    service = CesAssetImportService(MagicMock(), asset_service=MagicMock())
    asset_type = SimpleNamespace(id=10, name="Gas Detector")
    location = SimpleNamespace(id=5, name="Main Depot")
    service._lookups = AsyncMock(
        return_value=(
            {"gas detector": asset_type},
            {"main depot": location},
            {"jane smith": 21},
            existing or {},
        )
    )
    return service


def test_location_split_extracts_engineer_and_vehicle():
    assert split_location("Plantexpand; Engineer: Jane Smith")["engineer_name"] == "Jane Smith"
    vehicle = split_location("Plantexpand; AB12 CDE")
    assert vehicle["vehicle_reg"] == "AB12CDE"
    assert vehicle["company"] == "Plantexpand"
    unlabelled = split_location("Plantexpand Ltd; Plantexpand AB12 CDE Jane Smith")
    assert unlabelled["vehicle_reg"] == "AB12CDE"
    assert unlabelled["engineer_name"] == "Jane Smith"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Fail", "quarantined"),
        ("Removed From Service", "decommissioned"),
        ("Pass", "active"),
        ("Pass with Advisory", "active"),
        ("Pass after adjustment", "active"),
        ("Pass With Observation", "active"),
    ],
)
def test_status_map(source, expected):
    assert normalise_status(source)[0] == expected


@pytest.mark.asyncio
async def test_dry_run_marks_existing_serial_as_update():
    existing = SimpleNamespace(id=99, asset_type_id=10, qr_code_data="PLA-QR-1")
    report, validated = await _service({"CES-001": [existing]}).validate_rows([_row()], tenant_id=3, dry_run=True)

    assert report.ok is True
    assert report.creates == 0
    assert report.updates == 1
    assert validated[0].existing_id == 99
    assert validated[0].owner_user_id == 21
    assert validated[0].payload()["site"] is None


@pytest.mark.asyncio
async def test_dry_run_rejects_ambiguous_serial():
    first = SimpleNamespace(id=99, asset_type_id=10, qr_code_data="QR-A")
    second = SimpleNamespace(id=100, asset_type_id=10, qr_code_data="QR-B")
    report, _ = await _service({"CES-001": [first, second]}).validate_rows(
        [_row(qr_code="")], tenant_id=3, dry_run=True
    )

    assert report.ok is False
    assert any(issue.code == "AMBIGUOUS_SERIAL" for issue in report.errors)


def test_update_payload_preserves_unmapped_assignments():
    row = ValidatedCesRow(
        row=2,
        action="update",
        asset_type_id=10,
        asset_number="CES-001",
        name="Gas Detector",
        serial_number="CES-001",
        status="active",
        existing_id=99,
        owner_user_id=None,
        location_id=None,
        vehicle_reg=None,
        site=None,
    )
    payload = row.payload(for_update=True)
    assert "owner_user_id" not in payload
    assert "location_id" not in payload
    assert "vehicle_reg" not in payload
    assert "site" not in payload
    assert "asset_number" not in payload


@pytest.mark.asyncio
async def test_same_serial_different_type_creates_when_existing_type_mismatches():
    """One existing Gas Detector must not absorb a Torch row with the same serial."""
    existing = SimpleNamespace(id=99, asset_type_id=10, qr_code_data="PLA-QR-1")
    service = _service({"CES-001": [existing]})
    gas = SimpleNamespace(id=10, name="Gas Detector")
    torch = SimpleNamespace(id=11, name="Torch")
    service._lookups = AsyncMock(
        return_value=(
            {"gas detector": gas, "torch": torch},
            {"main depot": SimpleNamespace(id=5, name="Main Depot")},
            {"jane smith": 21},
            {"CES-001": [existing]},
        )
    )
    report, validated = await service.validate_rows(
        [
            _row(equipment_type="Gas Detector", qr_code="PLA-QR-1"),
            _row(
                __row__=3,
                equipment_type="Torch",
                qr_code="PLA-QR-2",
                make="LedLenser",
                model="P7",
            ),
        ],
        tenant_id=3,
        dry_run=True,
    )

    assert report.ok is True
    assert report.updates == 1
    assert report.creates == 1
    assert {item.action for item in validated} == {"update", "create"}
    assert next(item for item in validated if item.action == "update").existing_id == 99
    assert next(item for item in validated if item.action == "create").existing_id is None


def test_parse_workbook_uses_equipment_list_sheet():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Equipment List"
    sheet.append(
        [
            "Location",
            "Equipment Type",
            "Make",
            "Model",
            "Capacity",
            "Serial",
            "Asset ID",
            "QR",
            "",
            "Last",
            "Next",
            "Status",
        ]
    )
    sheet.append(
        [
            "Plantexpand; Main Depot",
            "Gas Detector",
            "MSA",
            "Altair",
            "4 gas",
            "CES-1",
            None,
            "PLA-1",
            None,
            "01/07/2026",
            "01/07/2027",
            "Pass",
        ]
    )
    output = io.BytesIO()
    workbook.save(output)

    rows = CesAssetImportService.parse_workbook(output.getvalue())
    assert rows[0]["serial_number"] == "CES-1"
    assert rows[0]["assignment_text"] == "Main Depot"
