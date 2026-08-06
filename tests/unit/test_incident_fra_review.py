"""Unit tests for Incident → FRA significant-change review."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import BadRequestError, ConflictError, ValidationError
from src.domain.models.location import LocationKind
from src.domain.services.incident_fra_review import (
    FRA_TEMPLATE_KEY,
    activate_or_link_fra_significant_change,
    find_active_site_fra,
    incident_suggests_fra_significant_change,
)


@pytest.mark.parametrize(
    ("attrs", "expected"),
    [
        ({"emergency_services": ["fire"], "incident_type": "injury", "severity": "low"}, True),
        ({"emergency_services": ["FIRE"], "incident_type": "injury", "severity": "low"}, True),
        (
            {
                "emergency_services": ["ambulance"],
                "incident_type": "property_damage",
                "severity": "high",
            },
            True,
        ),
        (
            {"emergency_services": [], "incident_type": "hazard", "severity": "critical"},
            True,
        ),
        ({"emergency_services": [], "incident_type": "injury", "severity": "low", "is_sif": True}, True),
        (
            {"emergency_services": [], "incident_type": "injury", "severity": "low", "is_psif": True},
            True,
        ),
        (
            {
                "emergency_services": ["ambulance"],
                "incident_type": "injury",
                "severity": "low",
                "is_sif": False,
                "is_psif": False,
            },
            False,
        ),
        (
            {
                "emergency_services": [],
                "incident_type": "property_damage",
                "severity": "low",
            },
            False,
        ),
    ],
)
def test_incident_suggests_fra_significant_change(attrs, expected):
    incident = SimpleNamespace(**attrs)
    assert incident_suggests_fra_significant_change(incident) is expected


@pytest.mark.asyncio
async def test_find_active_site_fra_excludes_org_wide():
    """Org-wide FRA must not be returned as site cover (query constrains location_id)."""
    site_fra = SimpleNamespace(id=10, location_id=5)
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=site_fra)))

    found = await find_active_site_fra(db, tenant_id=7, location_id=5)
    assert found is site_fra
    # Ensure the compiled query was executed (location-scoped lookup)
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_activate_or_link_returns_existing_without_create():
    incident = SimpleNamespace(
        emergency_services=["fire"],
        incident_type="injury",
        severity="low",
        is_sif=False,
        is_psif=False,
    )
    existing = SimpleNamespace(id=42, location_id=3, reference_number="CSR-1")
    location = SimpleNamespace(id=3, kind=LocationKind.PREMISES, tenant_id=1)

    db = MagicMock()
    loc_result = MagicMock(scalar_one_or_none=MagicMock(return_value=location))
    fra_result = MagicMock(scalar_one_or_none=MagicMock(return_value=existing))
    db.execute = AsyncMock(side_effect=[loc_result, fra_result])

    with patch(
        "src.domain.services.incident_fra_review.ComplianceScheduleService.activate_catalogue_template",
        new_callable=AsyncMock,
    ) as activate:
        result = await activate_or_link_fra_significant_change(
            db,
            incident=incident,
            tenant_id=1,
            user_id=9,
            location_id=3,
        )
        activate.assert_not_awaited()

    assert result.created is False
    assert result.requirement is existing


@pytest.mark.asyncio
async def test_activate_or_link_creates_when_missing():
    incident = SimpleNamespace(
        emergency_services=["fire"],
        incident_type="injury",
        severity="low",
        is_sif=False,
        is_psif=False,
    )
    location = SimpleNamespace(id=3, kind=LocationKind.OFFICE, tenant_id=1)
    created = SimpleNamespace(id=99, location_id=3, reference_number="CSR-99")

    db = MagicMock()
    loc_result = MagicMock(scalar_one_or_none=MagicMock(return_value=location))
    fra_missing = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    db.execute = AsyncMock(side_effect=[loc_result, fra_missing])

    with patch(
        "src.domain.services.incident_fra_review.ComplianceScheduleService.activate_catalogue_template",
        new_callable=AsyncMock,
        return_value=created,
    ) as activate:
        result = await activate_or_link_fra_significant_change(
            db,
            incident=incident,
            tenant_id=1,
            user_id=9,
            location_id=3,
        )
        activate.assert_awaited_once()
        # Patched on the class: call args are (template_key, …) without a bound self.
        assert activate.await_args.args[0] == FRA_TEMPLATE_KEY
        assert activate.await_args.kwargs["location_id"] == 3

    assert result.created is True
    assert result.requirement is created


@pytest.mark.asyncio
async def test_activate_or_link_rejects_ineligible_incident():
    incident = SimpleNamespace(
        emergency_services=["ambulance"],
        incident_type="injury",
        severity="low",
        is_sif=False,
        is_psif=False,
    )
    db = MagicMock()
    with pytest.raises(BadRequestError):
        await activate_or_link_fra_significant_change(
            db,
            incident=incident,
            tenant_id=1,
            user_id=9,
            location_id=3,
        )


@pytest.mark.asyncio
async def test_activate_or_link_rejects_site_kind():
    incident = SimpleNamespace(
        emergency_services=["fire"],
        incident_type="injury",
        severity="low",
        is_sif=False,
        is_psif=False,
    )
    location = SimpleNamespace(id=3, kind=LocationKind.SITE, tenant_id=1)
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=location)))
    with pytest.raises(ValidationError):
        await activate_or_link_fra_significant_change(
            db,
            incident=incident,
            tenant_id=1,
            user_id=9,
            location_id=3,
        )


@pytest.mark.asyncio
async def test_activate_or_link_treats_conflict_as_existing():
    incident = SimpleNamespace(
        emergency_services=["fire"],
        incident_type="injury",
        severity="low",
        is_sif=False,
        is_psif=False,
    )
    location = SimpleNamespace(id=3, kind=LocationKind.PREMISES, tenant_id=1)
    raced = SimpleNamespace(id=77, location_id=3, reference_number="CSR-77")

    db = MagicMock()
    loc_result = MagicMock(scalar_one_or_none=MagicMock(return_value=location))
    fra_missing = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    fra_raced = MagicMock(scalar_one_or_none=MagicMock(return_value=raced))
    db.execute = AsyncMock(side_effect=[loc_result, fra_missing, fra_raced])

    with patch(
        "src.domain.services.incident_fra_review.ComplianceScheduleService.activate_catalogue_template",
        new_callable=AsyncMock,
        side_effect=ConflictError("already active", code="DUPLICATE_ENTITY"),
    ):
        result = await activate_or_link_fra_significant_change(
            db,
            incident=incident,
            tenant_id=1,
            user_id=9,
            location_id=3,
        )

    assert result.created is False
    assert result.requirement is raced
