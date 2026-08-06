"""Unit tests for Wave 3 location FRA / fire-drill coverage gaps."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.compliance_schedule_service import ComplianceScheduleService


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


@pytest.mark.asyncio
async def test_location_coverage_gaps_marks_missing_fra_and_drill():
    loc_a = SimpleNamespace(id=1, name="Depot A", kind=SimpleNamespace(value="site"), is_active=True)
    loc_b = SimpleNamespace(id=2, name="Office B", kind=SimpleNamespace(value="office"), is_active=True)

    fra_req = SimpleNamespace(id=10, location_id=1)
    # Org-wide FRA must not cover any location
    org_fra = SimpleNamespace(id=99, location_id=None)

    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _Result([loc_a, loc_b]),
            MagicMock(
                all=MagicMock(
                    return_value=[
                        (fra_req, "fire_risk_assessment"),
                        (org_fra, "fire_risk_assessment"),
                    ]
                )
            ),
        ]
    )

    service = ComplianceScheduleService(db)
    data = await service.get_location_coverage_gaps(tenant_id=7)

    assert data["total_locations"] == 2
    assert data["missing_fra"] == 1
    assert data["missing_fire_drill"] == 2
    assert data["missing_both"] == 1

    by_id = {row["location_id"]: row for row in data["items"]}
    assert by_id[1]["has_fra"] is True
    assert by_id[1]["missing_fire_drill"] is True
    assert by_id[1]["fra_requirement_id"] == 10
    assert by_id[2]["missing_fra"] is True
    assert by_id[2]["missing_fire_drill"] is True


@pytest.mark.asyncio
async def test_location_coverage_gaps_fail_closed_without_tenant():
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_Result([]), MagicMock(all=MagicMock(return_value=[]))])
    service = ComplianceScheduleService(db)
    data = await service.get_location_coverage_gaps(tenant_id=None)  # type: ignore[arg-type]
    assert data["total_locations"] == 0
    assert data["items"] == []
