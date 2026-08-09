"""Route-level tests for Export Center sync APIs (PX-160 + WA-3 IMS052)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from src.api.routes.exports import create_sync_export, download_module_csv, get_export_catalog
from src.api.schemas.exports import CreateExportRequest
from src.domain.services.export_center_service import SyncExportResult


def _user(tenant_id: int = 42):
    return SimpleNamespace(id=7, email="exporter@example.com", tenant_id=tenant_id)


def _csv_result(**overrides):
    base = dict(
        module="incidents",
        filename="incidents_export_20260727.csv",
        content=b"id,title\n1,Spill\n",
        media_type="text/csv; charset=utf-8",
        row_count=1,
        truncated=False,
        total_available=1,
    )
    base.update(overrides)
    return SyncExportResult(**base)


@pytest.mark.asyncio
async def test_catalog_route_returns_modules():
    payload = {
        "modules": [
            {
                "id": "incidents",
                "name": "Incidents",
                "description": "Tenant incident register (CSV sync)",
                "record_count": 3,
                "formats": ["csv"],
                "sync_available": True,
            },
            {
                "id": "documents",
                "name": "Documents (IMS052 Register)",
                "description": "Master Document Register evidence pack",
                "record_count": 9,
                "formats": ["csv", "xlsx", "pdf"],
                "sync_available": True,
            },
        ],
        "capabilities": {
            "sync_csv": True,
            "job_history": False,
            "scheduled_templates": False,
            "max_sync_rows": 10000,
        },
    }
    db = SimpleNamespace()
    with patch(
        "src.api.routes.exports.ExportCenterService.get_catalog",
        new=AsyncMock(return_value=payload),
    ):
        response = await get_export_catalog(db, _user())

    assert response.capabilities.job_history is False
    assert response.modules[0].record_count == 3
    assert response.modules[0].id == "incidents"
    assert response.modules[1].formats == ["csv", "xlsx", "pdf"]


@pytest.mark.asyncio
async def test_create_sync_export_streams_csv():
    result = _csv_result()
    db = SimpleNamespace()
    with patch(
        "src.api.routes.exports.ExportCenterService.build_sync_csv",
        new=AsyncMock(return_value=result),
    ) as mocked:
        response = await create_sync_export(
            CreateExportRequest(module="incidents", format="csv"),
            db,
            _user(),
        )
        mocked.assert_awaited_once()
        assert mocked.await_args.kwargs.get("user") is not None or (len(mocked.await_args.args) >= 1)

    assert response.media_type.startswith("text/csv")
    assert "incidents_export_20260727.csv" in response.headers["content-disposition"]
    assert response.headers["x-export-mode"] == "sync"
    assert response.headers["x-export-truncated"] == "false"
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk if isinstance(chunk, (bytes, bytearray)) else str(chunk).encode("utf-8"))
    assert b"Spill" in b"".join(chunks)


@pytest.mark.asyncio
async def test_create_sync_export_streams_xlsx_for_documents():
    result = SyncExportResult(
        module="documents",
        filename="ims052_document_register_20260809.xlsx",
        content=b"PK\x03\x04fake-xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        row_count=2,
        truncated=False,
        total_available=2,
    )
    with patch(
        "src.api.routes.exports.ExportCenterService.build_sync_csv",
        new=AsyncMock(return_value=result),
    ):
        response = await create_sync_export(
            CreateExportRequest(module="documents", format="xlsx"),
            db=SimpleNamespace(),
            current_user=_user(),
        )

    assert "spreadsheetml" in response.media_type
    assert "ims052_document_register_20260809.xlsx" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_download_module_csv_route():
    result = _csv_result(
        module="risks",
        filename="risks_export_20260727.csv",
        content=b"id\n1\n",
        truncated=True,
        total_available=12,
    )
    with patch(
        "src.api.routes.exports.ExportCenterService.build_sync_csv",
        new=AsyncMock(return_value=result),
    ):
        response = await download_module_csv("risks", SimpleNamespace(), _user(), export_format="csv")

    assert response.headers["x-export-module"] == "risks"
    assert response.headers["x-export-truncated"] == "true"
    assert response.headers["x-export-total-available"] == "12"


def test_create_export_request_forbids_columns_picker():
    with pytest.raises(ValidationError):
        CreateExportRequest(
            module="documents",
            format="csv",
            columns=["Document Name"],  # type: ignore[call-arg]
        )
