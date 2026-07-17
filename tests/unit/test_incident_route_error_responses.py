from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from src.api.routes.incidents import list_incidents
from src.api.schemas.error_codes import ErrorCode
from src.domain.exceptions import AuthorizationError
from src.domain.models.incident import IncidentSeverity, IncidentStatus, IncidentType


@pytest.mark.asyncio
async def test_list_incidents_denies_foreign_reporter_email_with_structured_error() -> None:
    service = SimpleNamespace(
        check_reporter_email_access=AsyncMock(return_value=False),
        list_incidents=AsyncMock(),
    )
    current_user = SimpleNamespace(
        id=7,
        tenant_id=11,
        email="owner@example.com",
        is_superuser=False,
        has_permission=lambda permission: False,
    )

    with patch("src.api.routes.incidents.IncidentService", return_value=service):
        with pytest.raises(AuthorizationError) as exc_info:
            await list_incidents(
                db=SimpleNamespace(),
                current_user=current_user,
                request_id="req-123",
                reporter_email="other@example.com",
                owner=None,
                page=1,
                page_size=50,
            )

    assert exc_info.value.message == "You can only view your own incidents"
    assert exc_info.value.code == "PERMISSION_DENIED"
    service.list_incidents.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_incidents_masks_pending_migration_errors() -> None:
    service = SimpleNamespace(
        check_reporter_email_access=AsyncMock(return_value=True),
        list_incidents=AsyncMock(side_effect=RuntimeError('column "reporter_email" does not exist')),
    )
    current_user = SimpleNamespace(
        id=7,
        tenant_id=11,
        email="owner@example.com",
        is_superuser=False,
        has_permission=lambda permission: False,
    )

    with patch("src.api.routes.incidents.IncidentService", return_value=service):
        with pytest.raises(HTTPException) as exc_info:
            await list_incidents(
                db=SimpleNamespace(),
                current_user=current_user,
                request_id="req-456",
                reporter_email=None,
                owner=None,
                page=1,
                page_size=50,
            )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == {
        "code": ErrorCode.DATABASE_ERROR,
        "message": "Database migration pending. Please wait for migrations to complete.",
        "details": {},
    }


@pytest.mark.asyncio
async def test_list_incidents_masks_unexpected_internal_errors() -> None:
    service = SimpleNamespace(
        check_reporter_email_access=AsyncMock(return_value=True),
        list_incidents=AsyncMock(side_effect=RuntimeError("boom")),
    )
    current_user = SimpleNamespace(
        id=7,
        tenant_id=11,
        email="owner@example.com",
        is_superuser=False,
        has_permission=lambda permission: False,
    )

    with patch("src.api.routes.incidents.IncidentService", return_value=service):
        with pytest.raises(HTTPException) as exc_info:
            await list_incidents(
                db=SimpleNamespace(),
                current_user=current_user,
                request_id="req-789",
                reporter_email=None,
                owner=None,
                page=1,
                page_size=50,
            )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == {
        "code": ErrorCode.INTERNAL_ERROR,
        "message": "Unable to list incidents at this time.",
        "details": {},
    }


@pytest.mark.asyncio
async def test_list_incidents_skips_unserializable_rows() -> None:
    """One bad ORM row must not 500 the whole incidents index."""
    now = datetime.now(timezone.utc)
    good = SimpleNamespace(
        id=1,
        reference_number="INC-OK",
        title="Good row",
        description="ok",
        incident_type=IncidentType.OTHER,
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.REPORTED,
        incident_date=now,
        reported_date=now,
        created_at=now,
        updated_at=None,
        location=None,
        department=None,
        reporter_id=None,
        reporter_email=None,
        reporter_name=None,
        people_involved=None,
        witnesses=None,
        immediate_actions=None,
        first_aid_given=False,
        emergency_services_called=False,
        investigator_id=None,
        is_riddor_reportable=None,
        riddor_classification=None,
        is_sif=None,
        life_altering_potential=None,
        reporter_submission=None,
        closed_at=None,
        owner_id=None,
        asset_id=None,
        linked_risk_ids=None,
    )
    bad = SimpleNamespace(
        id=2,
        reference_number="INC-BAD",
        title="Bad row",
        description="missing required enums",
        incident_type=None,
        severity=None,
        status=None,
        incident_date=None,
        reported_date=None,
        created_at=None,
        updated_at=None,
    )
    page = SimpleNamespace(items=[good, bad], total=2, page=1, page_size=50, pages=1)
    service = SimpleNamespace(
        check_reporter_email_access=AsyncMock(return_value=True),
        list_incidents=AsyncMock(return_value=page),
    )
    current_user = SimpleNamespace(
        id=7,
        tenant_id=11,
        email="owner@example.com",
        is_superuser=False,
        has_permission=lambda permission: False,
    )

    with patch("src.api.routes.incidents.IncidentService", return_value=service):
        result = await list_incidents(
            db=SimpleNamespace(),
            current_user=current_user,
            request_id="req-skip",
            reporter_email=None,
            owner=None,
            page=1,
            page_size=50,
        )

    assert len(result.items) == 1
    assert result.items[0].reference_number == "INC-OK"
    assert result.total == 2

