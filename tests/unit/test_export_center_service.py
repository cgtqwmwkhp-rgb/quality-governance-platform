"""Unit tests for Export Center sync CSV service (PX-160 + WA-3 IMS052)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.exceptions import BadRequestError
from src.domain.services.document_register_export import IMS052_COLUMNS
from src.domain.services.export_center_service import (
    REGISTER_EXPORT_MODULE,
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
    assert catalog["modules"][0]["formats"] == ["csv"]
    assert catalog["modules"][6]["id"] == "documents"
    assert catalog["modules"][6]["record_count"] == 6
    assert catalog["modules"][6]["formats"] == ["csv", "xlsx", "pdf"]
    assert catalog["modules"][7]["id"] == "compliance_schedule"
    assert catalog["modules"][7]["record_count"] == 7


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
    assert result.media_type.startswith("text/csv")
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


@pytest.mark.asyncio
async def test_documents_export_rejects_xlsx_for_incidents_but_allows_for_documents():
    service = ExportCenterService(SimpleNamespace(execute=AsyncMock()))
    with pytest.raises(BadRequestError, match="Supported: csv"):
        await service.build_sync_csv(1, "incidents", "xlsx")

    user = SimpleNamespace(is_superuser=True)
    with patch(
        "src.domain.services.export_center_service.build_document_register_rows",
        new=AsyncMock(return_value=([], 0, False)),
    ):
        result = await service.build_sync_csv(1, "documents", "xlsx", user=user)
    assert result.filename.endswith(".xlsx")
    assert "spreadsheetml" in result.media_type


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


@pytest.mark.asyncio
async def test_documents_export_uses_fixed_ims052_header_ignoring_picker():
    """L-07: documents export always emits IMS052 columns — never a picker subset."""
    user = SimpleNamespace(is_superuser=True)
    ims_row = [
        "PEL-IT-0001",
        "",
        "",
        "Policy",
        "DOC-1",
        "1.0",
        "approved",
        "IT",
        "Policies",
        "",
        "",
        "",
        "all_staff",
        "",
        "/documents/1",
    ]
    with patch(
        "src.domain.services.export_center_service.build_document_register_rows",
        new=AsyncMock(return_value=([ims_row], 1, False)),
    ):
        service = ExportCenterService(SimpleNamespace())
        result = await service.build_sync_csv(7, "documents", "csv", user=user)

    assert result.filename.startswith("ims052_document_register_")
    header = result.csv_text.splitlines()[0]
    assert header == ",".join(IMS052_COLUMNS)
    assert "Policy" in result.csv_text
    assert "file_name" not in header
    assert "created_at" not in header


@pytest.mark.asyncio
async def test_documents_export_requires_user_for_acl():
    service = ExportCenterService(SimpleNamespace())
    with pytest.raises(BadRequestError, match="authenticated user"):
        await service.build_sync_csv(1, "documents", "csv", user=None)


def test_register_overlay_covers_only_registers_that_are_a_whole_module():
    """REG-SSOT-E1: mirrors registerExportOverlay.ts. Subset registers stay out."""
    assert REGISTER_EXPORT_MODULE == {
        "PEL-HSEQ-5010": "incidents",
        "PEL-HSEQ-5021": "risks",
        "PEL-HSEQ-5059": "actions",
        "PEL-HSEQ-5060": "complaints",
    }


@pytest.mark.asyncio
async def test_register_overlay_tags_filename_without_narrowing_rows():
    incident = SimpleNamespace(
        id=4,
        reference_number="INC-2026-0004",
        title="Trip",
        incident_type=SimpleNamespace(value="injury"),
        severity=SimpleNamespace(value="low"),
        status=SimpleNamespace(value="closed"),
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

    result = await service.build_sync_csv(42, "incidents", "csv", register="PEL-HSEQ-5010")

    assert result.register == "PEL-HSEQ-5010"
    assert result.filename.startswith("incidents_export_PEL-HSEQ-5010_")
    assert result.filename.endswith(".csv")
    # Same rows as the untagged module export — the tag is a label, not a filter.
    assert result.row_count == 1
    assert result.total_available == 1
    assert "INC-2026-0004" in result.csv_text


@pytest.mark.asyncio
async def test_register_overlay_rejects_a_register_that_is_not_this_module():
    service = ExportCenterService(SimpleNamespace(execute=AsyncMock()))

    with pytest.raises(BadRequestError, match="is the 'risks' register, not 'incidents'"):
        await service.build_sync_csv(1, "incidents", "csv", register="PEL-HSEQ-5021")


@pytest.mark.asyncio
async def test_register_overlay_rejects_a_subset_register():
    """RIDDOR names fewer rows than the incidents module holds — refuse the label."""
    service = ExportCenterService(SimpleNamespace(execute=AsyncMock()))

    with pytest.raises(BadRequestError, match="no Export Center overlay"):
        await service.build_sync_csv(1, "incidents", "csv", register="PEL-HSEQ-5033")

    with pytest.raises(BadRequestError, match="no Export Center overlay"):
        await service.build_sync_csv(1, "incidents", "csv", register=' "; drop ')


@pytest.mark.asyncio
async def test_register_overlay_is_case_insensitive_and_optional():
    incident = SimpleNamespace(
        id=1,
        reference_number="INC-1",
        title="T",
        incident_type=SimpleNamespace(value="hazard"),
        severity="low",
        status=SimpleNamespace(value="reported"),
        incident_date=None,
        created_at=None,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _FakeResult(scalar=1),
                _FakeResult(values=[incident]),
                _FakeResult(scalar=1),
                _FakeResult(values=[incident]),
            ]
        )
    )
    service = ExportCenterService(db)

    tagged = await service.build_sync_csv(42, "incidents", "csv", register=" pel-hseq-5010 ")
    assert tagged.filename.startswith("incidents_export_PEL-HSEQ-5010_")

    untagged = await service.build_sync_csv(42, "incidents", "csv")
    assert untagged.register is None
    assert untagged.filename.startswith("incidents_export_2")
