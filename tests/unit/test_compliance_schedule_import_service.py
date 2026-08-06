"""Unit tests for Wave 3 Compliance Schedule CSV bulk import."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.exceptions import ConflictError, NotFoundError, ValidationError
from src.domain.services.compliance_schedule_import_service import ComplianceScheduleImportService


def _csv(text: str) -> bytes:
    return text.encode("utf-8")


@pytest.mark.asyncio
async def test_dry_run_valid_rows_preview():
    db = MagicMock()
    service = ComplianceScheduleImportService(db)
    template = SimpleNamespace(id=5, title="Fire Risk Assessment", template_key="fire_risk_assessment")
    loc = SimpleNamespace(id=12, name="Wickford")

    service.cs._get_template_by_key = AsyncMock(return_value=template)
    service._get_location_by_id = AsyncMock(return_value=loc)
    service.cs._assert_template_not_already_active = AsyncMock(return_value=None)
    service.cs._assert_owner_in_tenant = AsyncMock(return_value=None)

    content = _csv(
        "template_key,location_id,next_due_date\n"
        "fire_risk_assessment,12,2026-09-01\n"
        "fire_drill_evacuation,12,2026-10-01\n"
    )
    # second row needs its own template mock alternating
    drill = SimpleNamespace(id=6, title="Fire Drill", template_key="fire_drill_evacuation")
    service.cs._get_template_by_key = AsyncMock(side_effect=[template, drill])

    report = await service.dry_run(content, tenant_id=7, default_owner_id=41)
    assert report.ok is True
    assert report.creates == 2
    assert report.preview[0]["location_id"] == 12
    assert report.preview[0]["title"] == "Fire Risk Assessment"
    assert report.preview[1]["template_key"] == "fire_drill_evacuation"


@pytest.mark.asyncio
async def test_dry_run_unknown_location():
    db = MagicMock()
    service = ComplianceScheduleImportService(db)
    template = SimpleNamespace(id=5, title="FRA", template_key="fire_risk_assessment")
    service.cs._get_template_by_key = AsyncMock(return_value=template)
    service._get_location_by_id = AsyncMock(return_value=None)

    content = _csv("template_key,location_id\nfire_risk_assessment,999\n")
    report = await service.dry_run(content, tenant_id=7, default_owner_id=1)
    assert report.ok is False
    assert any(e.code == "LOCATION_NOT_FOUND" for e in report.errors)


@pytest.mark.asyncio
async def test_dry_run_inactive_template():
    db = MagicMock()
    service = ComplianceScheduleImportService(db)
    service.cs._get_template_by_key = AsyncMock(side_effect=NotFoundError("missing", code="ENTITY_NOT_FOUND"))
    service._get_location_by_id = AsyncMock(return_value=SimpleNamespace(id=1, name="A"))

    content = _csv("template_key,location_id\nunknown_key,1\n")
    report = await service.dry_run(content, tenant_id=7, default_owner_id=1)
    assert report.ok is False
    assert any(e.code == "TEMPLATE_NOT_FOUND" for e in report.errors)


@pytest.mark.asyncio
async def test_dry_run_duplicate_entity():
    db = MagicMock()
    service = ComplianceScheduleImportService(db)
    template = SimpleNamespace(id=5, title="FRA", template_key="fire_risk_assessment")
    service.cs._get_template_by_key = AsyncMock(return_value=template)
    service._get_location_by_id = AsyncMock(return_value=SimpleNamespace(id=12, name="Wickford"))
    service.cs._assert_template_not_already_active = AsyncMock(
        side_effect=ConflictError("already on the register as CSR-1", code="DUPLICATE_ENTITY")
    )

    content = _csv("template_key,location_id\nfire_risk_assessment,12\n")
    report = await service.dry_run(content, tenant_id=7, default_owner_id=1)
    assert report.ok is False
    assert any(e.code == "DUPLICATE_ENTITY" for e in report.errors)


@pytest.mark.asyncio
async def test_commit_fails_closed_on_errors():
    db = MagicMock()
    service = ComplianceScheduleImportService(db)
    service.cs._get_template_by_key = AsyncMock(side_effect=NotFoundError("missing", code="ENTITY_NOT_FOUND"))
    service._get_location_by_id = AsyncMock(return_value=SimpleNamespace(id=1, name="A"))

    with pytest.raises(ValidationError):
        await service.commit(
            _csv("template_key,location_id\nbad,1\n"),
            tenant_id=7,
            user_id=1,
        )


@pytest.mark.asyncio
async def test_commit_activates_valid_rows():
    db = MagicMock()
    service = ComplianceScheduleImportService(db)
    template = SimpleNamespace(id=5, title="FRA", template_key="fire_risk_assessment")
    service.cs._get_template_by_key = AsyncMock(return_value=template)
    service._get_location_by_id = AsyncMock(return_value=SimpleNamespace(id=12, name="Wickford"))
    service.cs._assert_template_not_already_active = AsyncMock(return_value=None)
    service.cs.activate_catalogue_template = AsyncMock(return_value=SimpleNamespace(id=101))

    result = await service.commit(
        _csv("template_key,location_id,next_due_date\nfire_risk_assessment,12,2026-09-01\n"),
        tenant_id=7,
        user_id=41,
    )
    assert result.created_count == 1
    assert result.created_requirement_ids == [101]
    service.cs.activate_catalogue_template.assert_awaited_once()
    kwargs = service.cs.activate_catalogue_template.await_args.kwargs
    assert kwargs["location_id"] == 12
    assert kwargs["owner_id"] == 41


@pytest.mark.asyncio
async def test_org_wide_rejected():
    db = MagicMock()
    service = ComplianceScheduleImportService(db)
    template = SimpleNamespace(id=5, title="FRA", template_key="fire_risk_assessment")
    service.cs._get_template_by_key = AsyncMock(return_value=template)

    report = await service.dry_run(
        _csv("template_key\nfire_risk_assessment\n"),
        tenant_id=7,
        default_owner_id=1,
    )
    assert report.ok is False
    assert any(e.code == "REQUIRED" for e in report.errors)
