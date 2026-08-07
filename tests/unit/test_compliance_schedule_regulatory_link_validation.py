"""Validation of regulatory_standard_id / regulatory_clause_id on requirements."""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.services.compliance_schedule_service import ComplianceScheduleService


class _FakeResult:
    def __init__(self, row: Any = None) -> None:
        self._row = row

    def scalar_one_or_none(self) -> Any:
        return self._row


def _std(*, id: int = 1, tenant_id: Optional[int] = None, active: bool = True) -> MagicMock:
    row = MagicMock()
    row.id = id
    row.tenant_id = tenant_id
    row.is_active = active
    return row


def _clause(*, id: int = 2, standard_id: int = 1, active: bool = True) -> MagicMock:
    row = MagicMock()
    row.id = id
    row.standard_id = standard_id
    row.is_active = active
    return row


@pytest.mark.asyncio
async def test_clause_without_standard_raises_validation() -> None:
    service = ComplianceScheduleService(AsyncMock())
    with pytest.raises(ValidationError):
        await service._assert_regulatory_link_in_tenant(None, 2, tenant_id=1)


@pytest.mark.asyncio
async def test_other_tenant_standard_raises_not_found() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_FakeResult(None))
    service = ComplianceScheduleService(db)
    with pytest.raises(NotFoundError):
        await service._assert_regulatory_link_in_tenant(9, None, tenant_id=1)


@pytest.mark.asyncio
async def test_inactive_standard_raises_not_found() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_FakeResult(None))
    service = ComplianceScheduleService(db)
    with pytest.raises(NotFoundError):
        await service._assert_regulatory_link_in_tenant(1, None, tenant_id=1)


@pytest.mark.asyncio
async def test_clause_from_different_standard_raises_not_found() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_FakeResult(_std(id=1)), _FakeResult(None)])
    service = ComplianceScheduleService(db)
    with pytest.raises(NotFoundError):
        await service._assert_regulatory_link_in_tenant(1, 99, tenant_id=1)


@pytest.mark.asyncio
async def test_global_standard_succeeds() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_FakeResult(_std(id=1, tenant_id=None)), _FakeResult(_clause())])
    service = ComplianceScheduleService(db)
    await service._assert_regulatory_link_in_tenant(1, 2, tenant_id=1)


@pytest.mark.asyncio
async def test_update_validates_effective_pair_against_stored_standard() -> None:
    requirement = MagicMock()
    requirement.regulatory_standard_id = 1
    requirement.regulatory_clause_id = None
    requirement.frequency_months = 12
    requirement.frequency_days = None
    requirement.reference_number = "CSR-1"
    requirement.id = 5
    requirement.updated_by_id = None

    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    service = ComplianceScheduleService(db)

    with (
        patch.object(service, "get_requirement", AsyncMock(return_value=requirement)),
        patch.object(
            service,
            "_assert_regulatory_link_in_tenant",
            AsyncMock(side_effect=NotFoundError("Clause 99 not found", code="ENTITY_NOT_FOUND")),
        ) as assert_link,
        patch(
            "src.domain.services.compliance_schedule_service.record_audit_event",
            AsyncMock(),
        ),
    ):
        with pytest.raises(NotFoundError):
            await service.update_requirement(
                5,
                tenant_id=1,
                user_id=1,
                updates={"regulatory_clause_id": 99},
            )
        assert_link.assert_awaited_once_with(1, 99, tenant_id=1)


@pytest.mark.asyncio
async def test_explicit_none_clears_regulatory_links() -> None:
    requirement = MagicMock()
    requirement.regulatory_standard_id = 1
    requirement.regulatory_clause_id = 2
    requirement.frequency_months = 12
    requirement.frequency_days = None
    requirement.reference_number = "CSR-1"
    requirement.id = 5
    requirement.updated_by_id = None

    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    service = ComplianceScheduleService(db)

    with (
        patch.object(service, "get_requirement", AsyncMock(return_value=requirement)),
        patch.object(service, "_assert_regulatory_link_in_tenant", AsyncMock()) as assert_link,
        patch(
            "src.domain.services.compliance_schedule_service.record_audit_event",
            AsyncMock(),
        ),
    ):
        await service.update_requirement(
            5,
            tenant_id=1,
            user_id=1,
            updates={"regulatory_standard_id": None, "regulatory_clause_id": None},
        )

    assert_link.assert_awaited()
    assert requirement.regulatory_standard_id is None
    assert requirement.regulatory_clause_id is None
