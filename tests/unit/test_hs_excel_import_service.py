"""Unit tests for tenant-scoped H&S workbook import identities."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.hs_excel_import_service import (
    HsExcelImportService,
    _complaint_import_reference,
    _legacy_near_miss_import_reference,
    _near_miss_import_reference,
)


def test_import_references_are_tenant_scoped_deterministic_and_bounded() -> None:
    key = f"excel:incident_log:{'x' * 200}"

    tenant_one_near_miss = _near_miss_import_reference(1, key)
    tenant_two_near_miss = _near_miss_import_reference(2, key)
    tenant_one_complaint = _complaint_import_reference(1, key)
    tenant_two_complaint = _complaint_import_reference(2, key)

    assert tenant_one_near_miss == _near_miss_import_reference(1, key)
    assert tenant_one_complaint == _complaint_import_reference(1, key)
    assert tenant_one_near_miss != tenant_two_near_miss
    assert tenant_one_complaint != tenant_two_complaint
    assert len(tenant_one_near_miss) <= 50
    assert len(tenant_one_complaint) <= 100


@pytest.mark.asyncio
async def test_created_records_use_tenant_scoped_import_references() -> None:
    db = MagicMock()
    service = HsExcelImportService(db)
    key = "excel:incident_log:42"
    common_row = {
        "external_key": key,
        "event_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "reporter": "Reporter",
        "customer": "Contract",
        "role_location": "Depot",
        "description": "Imported event",
        "person_involved": "",
        "closed": False,
        "notes": "",
    }

    await service._create_near_miss(common_row, tenant_id=7, user_id=3)
    with patch(
        "src.domain.services.hs_excel_import_service.ReferenceNumberService.generate",
        new=AsyncMock(return_value="COMP-2026-0001"),
    ):
        await service._create_complaint(common_row, tenant_id=7, user_id=3)

    near_miss, complaint = [call.args[0] for call in db.add.call_args_list]
    assert near_miss.reference_number == _near_miss_import_reference(7, key)
    assert complaint.external_ref == _complaint_import_reference(7, key)


@pytest.mark.asyncio
@pytest.mark.parametrize("module", ["near_miss", "complaint"])
async def test_exists_accepts_legacy_and_tenant_scoped_references(module: str) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    service = HsExcelImportService(db)
    key = "excel:incident_log:42"

    assert await service._exists(7, key, module) is False

    statement = db.execute.await_args.args[0]
    parameter_values = list(statement.compile().params.values())
    flattened_values = {
        value
        for parameter in parameter_values
        for value in (parameter if isinstance(parameter, (list, tuple)) else [parameter])
    }
    expected = (
        {_near_miss_import_reference(7, key), _legacy_near_miss_import_reference(key)}
        if module == "near_miss"
        else {_complaint_import_reference(7, key), key}
    )
    assert expected <= flattened_values
