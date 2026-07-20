"""Route-level tests for GET /api/v1/uvdb/protocol/export."""

from __future__ import annotations

import json
import types

import pytest

from src.api.routes.uvdb import export_protocol_pack
from src.domain.uvdb.protocol_b2_v118 import UVDB_B2_SECTIONS


@pytest.mark.asyncio
async def test_export_protocol_pack_json_attachment() -> None:
    current_user = types.SimpleNamespace(id=7, email="auditor@example.com", tenant_id=42)

    response = await export_protocol_pack(current_user, export_format="json")

    assert response.media_type == "application/json"
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["x-uvdb-protocol-pack-version"] == "uvdb-protocol-1.1"

    pack = json.loads(response.body.decode("utf-8"))
    assert pack["pack_version"] == "uvdb-protocol-1.1"
    assert pack["exported_by"] == "auditor@example.com"
    assert pack["total_sections"] == 15
    assert pack["total_sections"] == len(UVDB_B2_SECTIONS)
    assert pack["version"] == "11.8-target"
    assert pack["content_coverage"]["status"] == "partial"
    assert pack["content_coverage"]["loaded_sections"] == ["1", "2", "12", "13", "14", "15"]
    assert pack["follow_on_exports"]["branded_pdf"] == "not_available"


@pytest.mark.asyncio
async def test_export_protocol_pack_xlsx_attachment() -> None:
    current_user = types.SimpleNamespace(id=7, email="auditor@example.com", tenant_id=42)

    response = await export_protocol_pack(current_user, export_format="xlsx")

    assert response.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert response.headers["content-disposition"].endswith('.xlsx"')
    assert len(response.body) > 1000
