"""Unit tests for Export Center sync CSV service (PX-160)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.exceptions import BadRequestError
from src.domain.services.export_center_service import (
    SYNC_ROW_LIMIT,
    ExportCenterService,
    _compliance_schedule_row,
    _incident_row,
)


class _FakeScalars:
    def __init__(self, values):
        self._values = list(values)

    def all(self):
        return list(self._values)


class _FakeResult:
    def __init__(self, *, scalar=None, values=None):
        self._scalar = scalar
        self._values = list(values or [])

    def scalar_one(self):
        return self._scalar

    def scalars(self):
        return _FakeScalars(self._values)


@pytest.mark.asyncio
async def test_catalog_returns_live_counts_and_honest_capabilities():
    db = SimpleNamespace(execute=AsyncMock(side_effect=[_FakeResult(scalar=n) for n in range(8)]))
    service = ExportCenterService(db)

    catalog = await service.get_catalog(tenant_id=42)

    assert catalog["capabilities"]["sync_csv"] is True
    assert catalog["capabilities"]["job_history"] is False
    assert catalog["capabilities"]["scheduled_templates"] is False
    assert catalog["capabilities"]["max_sync_rows"] == SYNC_ROW_LIMIT
    assert len(catalog["modules"]) == 8
    assert catalog["modules"][0]["id"] == "incidents"
    assert catalog["modules"][0]["record_count"] == 0
    assert catalog["modules"][6]["id"] == "documents"
    assert catalog["modules"][6]["record_count"] == 6
    assert catalog["modules"][7]["id"] == "compliance_schedule"
    assert catalog["modules"][7]["record_count"] == 7
    assert all(m["formats"] == ["csv"] for m in catalog["modules"])


@pytest.mark.asyncio
async def test_build_sync_csv_writes_header_and_rows():
    incident = SimpleNamespace(
        id=9,
        reference_number="INC-2026-0009",
        title="Spill",
        incident_type=SimpleNamespace(value="environmental"),
        severity=SimpleNamespace(value="medium"),
        status=SimpleNamespace(value="reported"),
        incident_date=None,
        created_at=None,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _FakeResult(scalar=1),
                _FakeResult(values=[incident]),
            ]
        )
    )
    service = ExportCenterService(db)

    result = await service.build_sync_csv(42, "incidents", "csv")

    assert result.module == "incidents"
    assert result.row_count == 1
    assert result.truncated is False
    assert result.filename.startswith("incidents_export_")
    assert "reference_number" in result.csv_text.splitlines()[0]
    assert "INC-2026-0009" in result.csv_text
    assert "Spill" in result.csv_text


@pytest.mark.asyncio
async def test_build_sync_csv_rejects_unknown_module_and_format():
    service = ExportCenterService(SimpleNamespace(execute=AsyncMock()))

    with pytest.raises(BadRequestError, match="Unsupported export module"):
        await service.build_sync_csv(1, "not-a-module", "csv")

    with pytest.raises(BadRequestError, match="Unsupported export format"):
        await service.build_sync_csv(1, "incidents", "pdf")


def test_incident_row_mapper_handles_enums():
    row = SimpleNamespace(
        id=1,
        reference_number="INC-1",
        title="T",
        incident_type=SimpleNamespace(value="injury"),
        severity="high",
        status=SimpleNamespace(value="closed"),
        incident_date=None,
        created_at=None,
    )
    assert _incident_row(row)[3] == "injury"
    assert _incident_row(row)[4] == "high"


@pytest.mark.asyncio
async def test_build_sync_csv_compliance_schedule_writes_key_fields():
    requirement = SimpleNamespace(
        id=3,
        reference_number="CSR-2026-0003",
        title="Fire risk assessment",
        next_due_date=date(2026, 9, 1),
        owner_id=42,
        is_active=True,
        statutory=True,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _FakeResult(scalar=1),
                _FakeResult(values=[requirement]),
            ]
        )
    )
    service = ExportCenterService(db)

    result = await service.build_sync_csv(42, "compliance_schedule", "csv")

    assert result.module == "compliance_schedule"
    assert result.row_count == 1
    assert result.truncated is False
    assert result.filename.startswith("compliance_schedule_export_")
    header = result.csv_text.splitlines()[0]
    assert header == "id,reference_number,title,next_due_date,owner,is_active,statutory"
    assert "CSR-2026-0003" in result.csv_text
    assert "Fire risk assessment" in result.csv_text
    assert "2026-09-01" in result.csv_text
    assert "42" in result.csv_text


def test_compliance_schedule_row_mapper_key_fields():
    row = SimpleNamespace(
        id=1,
        reference_number="CSR-1",
        title="PAT testing",
        next_due_date=date(2026, 12, 31),
        owner_id=7,
        is_active=False,
        statutory=True,
    )
    mapped = _compliance_schedule_row(row)
    assert mapped == ["1", "CSR-1", "PAT testing", "2026-12-31", "7", "False", "True"]
