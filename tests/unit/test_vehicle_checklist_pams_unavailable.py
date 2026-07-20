"""VAN-CL-503: daily/monthly checklist list fail-soft when PAMS is unavailable."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.vehicle_checklists import (
    PAMS_UNAVAILABLE_MESSAGE,
    get_daily_record,
    get_monthly_record,
    list_daily,
    list_monthly,
)
from src.domain.exceptions import DomainError


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=1, tenant_id=1, is_superuser=False)


def _db_with_empty_cache() -> MagicMock:
    """Async session whose count queries report an empty PAMS cache."""
    result = MagicMock()
    result.scalar.return_value = 0
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_list_daily_raises_structured_503_when_pams_unavailable() -> None:
    db = _db_with_empty_cache()

    with patch("src.api.routes.vehicle_checklists.is_pams_available", return_value=False):
        with pytest.raises(DomainError) as exc_info:
            await list_daily(
                current_user=_user(),
                db=db,
                page=1,
                page_size=25,
                search=None,
            )

    err = exc_info.value
    assert err.http_status == 503
    assert err.code == "SERVICE_UNAVAILABLE"
    assert "PAMS unavailable" in err.message
    assert err.message == PAMS_UNAVAILABLE_MESSAGE
    assert err.details.get("service") == "pams"
    assert err.details.get("reason") == "not_configured"


@pytest.mark.asyncio
async def test_list_monthly_raises_structured_503_when_pams_unavailable() -> None:
    db = _db_with_empty_cache()

    with patch("src.api.routes.vehicle_checklists.is_pams_available", return_value=False):
        with pytest.raises(DomainError) as exc_info:
            await list_monthly(
                current_user=_user(),
                db=db,
                page=1,
                page_size=25,
                search=None,
            )

    err = exc_info.value
    assert err.http_status == 503
    assert err.code == "SERVICE_UNAVAILABLE"
    assert "PAMS unavailable" in err.message
    assert err.details.get("service") == "pams"


@pytest.mark.asyncio
async def test_list_daily_masks_unexpected_errors_as_pams_503() -> None:
    db = MagicMock()
    db.execute = AsyncMock(side_effect=RuntimeError("cache query exploded"))

    with pytest.raises(DomainError) as exc_info:
        await list_daily(
            current_user=_user(),
            db=db,
            page=1,
            page_size=25,
            search=None,
        )

    err = exc_info.value
    assert err.http_status == 503
    assert err.code == "SERVICE_UNAVAILABLE"
    assert "PAMS unavailable" in err.message
    assert err.details.get("reason") == "list_failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("detail_route", [get_daily_record, get_monthly_record])
async def test_checklist_detail_masks_cache_errors_as_pams_503(detail_route) -> None:
    db = MagicMock()
    db.execute = AsyncMock(side_effect=RuntimeError("cache query exploded"))

    with pytest.raises(DomainError) as exc_info:
        await detail_route(record_id=42, current_user=_user(), db=db)

    err = exc_info.value
    assert err.http_status == 503
    assert err.code == "SERVICE_UNAVAILABLE"
    assert err.message == PAMS_UNAVAILABLE_MESSAGE
    assert err.details.get("reason") == "detail_failed"
