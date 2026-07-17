"""Unit tests for CAPASource.investigation and create_capa_for_investigation."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.investigation import AssignedEntityType, InvestigationRun, InvestigationStatus
from src.domain.services.capa_service import CAPAService


def test_capa_source_has_investigation():
    assert CAPASource.INVESTIGATION.value == "investigation"


def _investigation(**overrides):
    inv = InvestigationRun(
        template_id=1,
        assigned_entity_type=AssignedEntityType.REPORTING_INCIDENT,
        assigned_entity_id=10,
        title="Slip investigation",
        description="Wet floor near loading bay",
        status=InvestigationStatus.IN_PROGRESS,
        tenant_id=1,
        created_by_id=2,
        updated_by_id=2,
        reference_number="INV-2026-0001",
    )
    inv.id = overrides.pop("id", 55)
    for key, value in overrides.items():
        setattr(inv, key, value)
    return inv


@pytest.mark.asyncio
async def test_create_capa_for_investigation_creates_linked_capa():
    investigation = _investigation()
    inv_result = MagicMock()
    inv_result.scalar_one_or_none.return_value = investigation
    prior_result = MagicMock()
    prior_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[inv_result, prior_result])
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    svc = CAPAService(db)
    with (
        patch(
            "src.domain.services.capa_service.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CAPA-2026-0099"),
        ),
        patch("src.domain.services.capa_service.record_audit_event", new=AsyncMock()),
        patch("src.domain.services.capa_service.invalidate_tenant_cache", new=AsyncMock()),
        patch("src.domain.services.capa_service.track_metric"),
    ):
        capa = await svc.create_capa_for_investigation(
            investigation.id,
            user_id=2,
            tenant_id=1,
            title="Install matting",
            priority="high",
        )

    assert isinstance(capa, CAPAAction)
    assert capa.source_type == CAPASource.INVESTIGATION
    assert capa.source_id == investigation.id
    assert capa.title == "Install matting"
    assert capa.priority == CAPAPriority.HIGH
    assert capa.source_reference == f"investigation:{investigation.id}"
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_capa_for_investigation_idempotent_without_title():
    investigation = _investigation()
    existing = CAPAAction(
        reference_number="CAPA-2026-0001",
        title="Existing",
        capa_type=CAPAType.CORRECTIVE,
        status=CAPAStatus.OPEN,
        priority=CAPAPriority.MEDIUM,
        source_type=CAPASource.INVESTIGATION,
        source_id=investigation.id,
        created_by_id=2,
        tenant_id=1,
    )
    existing.id = 99

    inv_result = MagicMock()
    inv_result.scalar_one_or_none.return_value = investigation
    prior_result = MagicMock()
    prior_result.scalar_one_or_none.return_value = existing

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[inv_result, prior_result])

    svc = CAPAService(db)
    capa = await svc.create_capa_for_investigation(
        investigation.id,
        user_id=2,
        tenant_id=1,
    )

    assert capa is existing
    db.add.assert_not_called()
    # Untitled idempotency must select one deterministic row when multiple CAPAs exist.
    prior_query = db.execute.await_args_list[1].args[0]
    compiled_query = str(prior_query.compile(compile_kwargs={"literal_binds": True}))
    assert "ORDER BY capa_actions.id ASC" in compiled_query
    assert "LIMIT 1" in compiled_query


@pytest.mark.asyncio
async def test_create_capa_for_investigation_titled_always_creates_new():
    """Explicit title skips idempotency so multiple CAPAs can attach to one investigation."""
    investigation = _investigation()
    existing = CAPAAction(
        reference_number="CAPA-2026-0001",
        title="Existing",
        capa_type=CAPAType.CORRECTIVE,
        status=CAPAStatus.OPEN,
        priority=CAPAPriority.MEDIUM,
        source_type=CAPASource.INVESTIGATION,
        source_id=investigation.id,
        created_by_id=2,
        tenant_id=1,
    )
    existing.id = 99

    inv_result = MagicMock()
    inv_result.scalar_one_or_none.return_value = investigation

    db = AsyncMock()
    # No prior lookup when title is supplied — only investigation fetch.
    db.execute = AsyncMock(side_effect=[inv_result])
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    svc = CAPAService(db)
    with (
        patch(
            "src.domain.services.capa_service.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CAPA-2026-0101"),
        ),
        patch("src.domain.services.capa_service.record_audit_event", new=AsyncMock()),
        patch("src.domain.services.capa_service.invalidate_tenant_cache", new=AsyncMock()),
        patch("src.domain.services.capa_service.track_metric"),
    ):
        capa = await svc.create_capa_for_investigation(
            investigation.id,
            user_id=2,
            tenant_id=1,
            title="Second corrective action",
        )

    assert capa is not existing
    assert capa.title == "Second corrective action"
    assert capa.source_type == CAPASource.INVESTIGATION
    assert capa.source_id == investigation.id
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_capa_for_investigation_not_found():
    inv_result = MagicMock()
    inv_result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=inv_result)

    svc = CAPAService(db)
    with pytest.raises(LookupError, match="Investigation with ID 404 not found"):
        await svc.create_capa_for_investigation(404, user_id=1, tenant_id=1)


@pytest.mark.asyncio
async def test_create_capa_for_investigation_unknown_assignee_email():
    investigation = _investigation()
    inv_result = MagicMock()
    inv_result.scalar_one_or_none.return_value = investigation
    prior_result = MagicMock()
    prior_result.scalar_one_or_none.return_value = None
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[inv_result, prior_result, user_result])

    svc = CAPAService(db)
    with pytest.raises(LookupError, match="User not found for email"):
        await svc.create_capa_for_investigation(
            investigation.id,
            user_id=2,
            tenant_id=1,
            assignee_email="missing@example.com",
        )


@pytest.mark.asyncio
async def test_create_capa_for_investigation_invalid_priority():
    investigation = _investigation()
    inv_result = MagicMock()
    inv_result.scalar_one_or_none.return_value = investigation
    prior_result = MagicMock()
    prior_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[inv_result, prior_result])

    svc = CAPAService(db)
    with pytest.raises(ValueError, match="Invalid priority"):
        await svc.create_capa_for_investigation(
            investigation.id,
            user_id=2,
            tenant_id=1,
            priority="urgent",
        )


@pytest.mark.asyncio
async def test_create_capa_for_investigation_defaults_from_investigation():
    investigation = _investigation(assigned_to_user_id=7)
    inv_result = MagicMock()
    inv_result.scalar_one_or_none.return_value = investigation
    prior_result = MagicMock()
    prior_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[inv_result, prior_result])
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    svc = CAPAService(db)
    with (
        patch(
            "src.domain.services.capa_service.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CAPA-2026-0100"),
        ),
        patch("src.domain.services.capa_service.record_audit_event", new=AsyncMock()),
        patch("src.domain.services.capa_service.invalidate_tenant_cache", new=AsyncMock()),
        patch("src.domain.services.capa_service.track_metric"),
    ):
        capa = await svc.create_capa_for_investigation(
            investigation.id,
            user_id=2,
            tenant_id=1,
        )

    assert capa.title == f"Action plan: {investigation.title}"
    assert capa.description == investigation.description
    assert capa.assigned_to_id == 7
