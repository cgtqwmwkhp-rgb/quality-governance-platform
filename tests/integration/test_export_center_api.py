"""Route-level tests for Export Center sync APIs (PX-160)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.api.routes.exports import create_sync_export, download_module_csv, get_export_catalog
from src.api.schemas.exports import CreateExportRequest
from src.domain.services.export_center_service import SyncExportResult


def _user(tenant_id: int = 42):
    return SimpleNamespace(id=7, email="exporter@example.com", tenant_id=tenant_id)


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
            }
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


@pytest.mark.asyncio
async def test_create_sync_export_streams_csv():
    result = SyncExportResult(
        module="incidents",
        filename="incidents_export_20260727.csv",
        csv_text="id,title\n1,Spill\n",
        row_count=1,
        truncated=False,
        total_available=1,
    )
    db = SimpleNamespace()
    with patch(
        "src.api.routes.exports.ExportCenterService.build_sync_csv",
        new=AsyncMock(return_value=result),
    ):
        response = await create_sync_export(
            CreateExportRequest(module="incidents", format="csv"),
            db,
            _user(),
        )

    assert response.media_type.startswith("text/csv")
    assert "incidents_export_20260727.csv" in response.headers["content-disposition"]
    assert response.headers["x-export-mode"] == "sync"
    assert response.headers["x-export-truncated"] == "false"
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk if isinstance(chunk, (bytes, bytearray)) else str(chunk).encode("utf-8"))
    assert b"Spill" in b"".join(chunks)


@pytest.mark.asyncio
async def test_download_module_csv_route():
    result = SyncExportResult(
        module="risks",
        filename="risks_export_20260727.csv",
        csv_text="id\n1\n",
        row_count=1,
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
