"""Unit tests for ComplianceScheduleService (Wave 1)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import ConflictError, NotFoundError, ValidationError
from src.domain.models.compliance_schedule import (
    ComplianceRecordOutcome,
    ComplianceRequirement,
    ComplianceRequirementTemplate,
    ComplianceScheduleAnchor,
)
from src.domain.services.compliance_schedule_policy import compute_next_due
from src.domain.services.compliance_schedule_service import ComplianceScheduleService


def _result(scalar=None, scalars_all=None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar
    result.scalar.return_value = scalar
    scalars = MagicMock()
    scalars.all.return_value = scalars_all if scalars_all is not None else ([] if scalar is None else [scalar])
    result.scalars.return_value = scalars
    return result


@pytest.fixture
def db():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_activate_unknown_catalogue_key_raises(db):
    db.execute = AsyncMock(return_value=_result(None))
    service = ComplianceScheduleService(db)
    with pytest.raises(NotFoundError):
        await service.activate_catalogue_template(
            "does-not-exist",
            tenant_id=1,
            user_id=9,
        )


@pytest.mark.asyncio
async def test_activate_rejects_cross_tenant_location(db):
    template = ComplianceRequirementTemplate(
        id=1,
        template_key="fire-risk-assessment",
        title="FRA",
        taxonomy_id="HS",
        frequency_months=12,
        frequency_days=None,
        anchor=ComplianceScheduleAnchor.SCHEDULE,
        statutory=True,
        is_active=True,
    )
    # First execute = template; second = location miss
    db.execute = AsyncMock(side_effect=[_result(template), _result(None)])
    service = ComplianceScheduleService(db)
    with pytest.raises(NotFoundError, match="Location"):
        await service.activate_catalogue_template(
            "fire-risk-assessment",
            tenant_id=1,
            user_id=9,
            location_id=999,
        )


@pytest.mark.asyncio
async def test_complete_rolls_next_due_on_schedule_anchor(db):
    requirement = ComplianceRequirement(
        id=10,
        tenant_id=1,
        reference_number="CSR-2026-0001",
        title="FRA",
        taxonomy_id="HS",
        frequency_months=12,
        frequency_days=None,
        anchor=ComplianceScheduleAnchor.SCHEDULE,
        statutory=True,
        next_due_date=date(2026, 3, 1),
        last_completed_at=None,
        is_active=True,
        external_id="ext",
    )
    # get_requirement; duplicate check; (ref gen uses execute); attach none
    db.execute = AsyncMock(
        side_effect=[
            _result(requirement),  # get_requirement
            _result(None),  # duplicate check
            _result("CSR-2026-0001"),  # max ref (ignored via patch)
            _result(0),  # count ref
        ]
    )

    service = ComplianceScheduleService(db)
    completed_at = datetime(2026, 3, 15, tzinfo=timezone.utc)

    with (
        patch(
            "src.domain.services.compliance_schedule_service.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CRC-2026-0001"),
        ),
        patch(
            "src.domain.services.compliance_schedule_service.record_audit_event",
            new=AsyncMock(),
        ),
    ):
        record = await service.complete_requirement(
            10,
            tenant_id=1,
            user_id=9,
            completed_at=completed_at,
            check_passed=True,
        )

    assert record.outcome == ComplianceRecordOutcome.COMPLETED
    assert record.due_date == date(2026, 3, 1)
    assert requirement.next_due_date == date(2027, 3, 1)  # schedule anchor from previous due
    assert requirement.last_completed_at == completed_at
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_complete_completion_anchor_uses_completed_at(db):
    requirement = ComplianceRequirement(
        id=11,
        tenant_id=1,
        reference_number="CSR-2026-0002",
        title="Drill",
        taxonomy_id="HS",
        frequency_months=6,
        frequency_days=None,
        anchor=ComplianceScheduleAnchor.COMPLETION,
        statutory=False,
        next_due_date=date(2026, 1, 1),
        last_completed_at=None,
        is_active=True,
        external_id="ext2",
    )
    db.execute = AsyncMock(side_effect=[_result(requirement), _result(None)])
    service = ComplianceScheduleService(db)
    completed_at = datetime(2026, 2, 10, tzinfo=timezone.utc)

    with (
        patch(
            "src.domain.services.compliance_schedule_service.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CRC-2026-0002"),
        ),
        patch(
            "src.domain.services.compliance_schedule_service.record_audit_event",
            new=AsyncMock(),
        ),
    ):
        await service.complete_requirement(
            11,
            tenant_id=1,
            user_id=9,
            completed_at=completed_at,
        )

    assert requirement.next_due_date == compute_next_due(
        "completion",
        previous_due=date(2026, 1, 1),
        completed_at=completed_at,
        frequency_months=6,
    )


@pytest.mark.asyncio
async def test_complete_duplicate_occurrence_conflicts(db):
    requirement = ComplianceRequirement(
        id=12,
        tenant_id=1,
        reference_number="CSR-2026-0003",
        title="X",
        taxonomy_id="HS",
        frequency_months=12,
        frequency_days=None,
        anchor=ComplianceScheduleAnchor.SCHEDULE,
        statutory=False,
        next_due_date=date(2026, 5, 1),
        is_active=True,
        external_id="ext3",
    )
    db.execute = AsyncMock(side_effect=[_result(requirement), _result(99)])
    service = ComplianceScheduleService(db)
    with pytest.raises(ConflictError):
        await service.complete_requirement(12, tenant_id=1, user_id=1)


@pytest.mark.asyncio
async def test_complete_inactive_requirement_rejected(db):
    requirement = ComplianceRequirement(
        id=13,
        tenant_id=1,
        reference_number="CSR-2026-0004",
        title="X",
        taxonomy_id="HS",
        frequency_months=12,
        frequency_days=None,
        anchor=ComplianceScheduleAnchor.SCHEDULE,
        statutory=False,
        next_due_date=date(2026, 5, 1),
        is_active=False,
        external_id="ext4",
    )
    db.execute = AsyncMock(return_value=_result(requirement))
    service = ComplianceScheduleService(db)
    with pytest.raises(ValidationError, match="inactive"):
        await service.complete_requirement(13, tenant_id=1, user_id=1)


@pytest.mark.asyncio
async def test_attach_evidence_missing_asset_fails_closed(db):
    record = SimpleNamespace(id=55, tenant_id=1)
    db.execute = AsyncMock(
        side_effect=[
            _result(record),  # get_record
            _result(scalars_all=[]),  # assets query
        ]
    )
    service = ComplianceScheduleService(db)
    with pytest.raises(NotFoundError, match="Evidence"):
        await service.attach_evidence_to_record(55, tenant_id=1, evidence_asset_ids=[7, 8])


# ---------------------------------------------------------------------------
# Owner tenancy
#
# The owner is a notification recipient, not a label. The reminder sweep scopes
# its admin fallback to the tenant but passes the owner through untouched, and
# notifications are read back filtered by user alone — so an owner id belonging
# to another tenant delivers one customer's obligation into another customer's
# inbox. Location was already guarded this way; the owner never was.
# ---------------------------------------------------------------------------


def _template() -> ComplianceRequirementTemplate:
    return ComplianceRequirementTemplate(
        id=1,
        template_key="fire-risk-assessment",
        title="FRA",
        taxonomy_id="HS",
        frequency_months=12,
        frequency_days=None,
        anchor=ComplianceScheduleAnchor.SCHEDULE,
        statutory=True,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_activate_rejects_cross_tenant_owner(db):
    # template hit, location skipped (None), owner miss
    db.execute = AsyncMock(side_effect=[_result(_template()), _result(None)])
    service = ComplianceScheduleService(db)
    with pytest.raises(NotFoundError, match="User"):
        await service.activate_catalogue_template(
            "fire-risk-assessment",
            tenant_id=1,
            user_id=9,
            owner_id=4242,
        )
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_rejects_cross_tenant_owner(db):
    # location skipped (None), owner miss
    db.execute = AsyncMock(side_effect=[_result(None)])
    service = ComplianceScheduleService(db)
    with pytest.raises(NotFoundError, match="User"):
        await service.create_requirement(
            tenant_id=1,
            user_id=9,
            title="Bespoke obligation",
            taxonomy_id="HS",
            frequency_months=12,
            next_due_date=date(2026, 9, 1),
            owner_id=4242,
        )
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_update_rejects_cross_tenant_owner(db):
    requirement = ComplianceRequirement(
        id=20,
        tenant_id=1,
        reference_number="CSR-2026-0020",
        title="FRA",
        taxonomy_id="HS",
        frequency_months=12,
        frequency_days=None,
        anchor=ComplianceScheduleAnchor.SCHEDULE,
        statutory=True,
        next_due_date=date(2026, 9, 1),
        is_active=True,
        external_id="ext20",
        owner_id=1,
    )
    # get_requirement, then owner miss
    db.execute = AsyncMock(side_effect=[_result(requirement), _result(None)])
    service = ComplianceScheduleService(db)
    with pytest.raises(NotFoundError, match="User"):
        await service.update_requirement(
            20,
            tenant_id=1,
            user_id=9,
            updates={"owner_id": 4242},
        )
    # The reassignment must not have been applied before the guard ran.
    assert requirement.owner_id == 1
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_owner_guard_does_not_leak_whether_the_user_exists_elsewhere(db):
    # A user who exists in another tenant and a user who does not exist at all
    # must be indistinguishable from outside, which is why the query filters on
    # tenant and the failure is a flat 404.
    db.execute = AsyncMock(side_effect=[_result(None)])
    service = ComplianceScheduleService(db)
    with pytest.raises(NotFoundError) as exc:
        await service._assert_owner_in_tenant(4242, tenant_id=1)
    assert "4242" in str(exc.value)
    assert "tenant" not in str(exc.value).lower()


@pytest.mark.asyncio
async def test_owner_guard_is_a_no_op_for_an_unowned_obligation(db):
    # Unowned is a legitimate state — the sweep falls back to the admin role —
    # so the guard must not turn "no owner" into a 404.
    db.execute = AsyncMock(side_effect=AssertionError("must not query for a null owner"))
    service = ComplianceScheduleService(db)
    await service._assert_owner_in_tenant(None, tenant_id=1)


@pytest.mark.asyncio
async def test_owner_guard_accepts_an_owner_in_the_same_tenant(db):
    db.execute = AsyncMock(side_effect=[_result(7)])
    service = ComplianceScheduleService(db)
    await service._assert_owner_in_tenant(7, tenant_id=1)
