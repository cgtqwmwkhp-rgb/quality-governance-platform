from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from src.api.routes.incidents import list_incidents
from src.api.schemas.error_codes import ErrorCode


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
        with pytest.raises(HTTPException) as exc_info:
            await list_incidents(
                db=SimpleNamespace(),
                current_user=current_user,
                request_id="req-123",
                reporter_email="other@example.com",
                page=1,
                page_size=50,
            )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == {
        "code": ErrorCode.PERMISSION_DENIED,
        "message": "You can only view your own incidents",
        "details": {},
    }
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
                page=1,
                page_size=50,
            )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == {
        "code": ErrorCode.INTERNAL_ERROR,
        "message": "Unable to list incidents at this time.",
        "details": {},
    }
