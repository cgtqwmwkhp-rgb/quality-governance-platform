"""Unified Governance Calendar API."""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Query

from src.api.dependencies import CurrentUser, DbSession
from src.domain.services.calendar_feed_service import CalendarFeedService

router = APIRouter()


@router.get("/feed")
async def get_calendar_feed(
    db: DbSession,
    current_user: CurrentUser,
    start: Optional[date] = Query(None, description="Inclusive start date (YYYY-MM-DD)"),
    end: Optional[date] = Query(None, description="Inclusive end date (YYYY-MM-DD)"),
    types: Optional[str] = Query(
        None,
        description="Comma-separated types: audit,deadline,review,training,meeting",
    ),
):
    """Aggregate governance deadlines and schedules for the Insights calendar."""
    today = datetime.now(timezone.utc).date()
    range_start = start or date(today.year, today.month, 1)
    if end is None:
        if range_start.month == 12:
            range_end = date(range_start.year + 1, 1, 1) - timedelta(days=1)
        else:
            range_end = date(range_start.year, range_start.month + 1, 1) - timedelta(days=1)
    else:
        range_end = end

    type_list = [part.strip() for part in (types or "").split(",") if part.strip()] or None
    service = CalendarFeedService(db, tenant_id=current_user.tenant_id)
    return await service.get_feed(start=range_start, end=range_end, types=type_list)
