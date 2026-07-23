"""H&S KPI board endpoints."""

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.domain.models.hs_reporting_period import HsReportingPeriod
from src.domain.models.user import User
from src.domain.services.hs_kpi_service import HsKpiService, effective_hours

router = APIRouter()


class HsReportingPeriodInput(BaseModel):
    reporting_year: int = Field(ge=2000, le=2100)
    period_start: date
    period_end: date
    average_fte: float = Field(gt=0)
    hours_per_fte_year: float = Field(default=2124, gt=0)
    # Authoritative annual hours for the H&S board (Admin-managed).
    manual_hours: Optional[float] = Field(default=None, gt=0)


@router.get("/summary")
async def hs_kpi_summary(db: DbSession, current_user: CurrentUser):
    assert current_user.tenant_id is not None
    service = HsKpiService(db)
    await service.ensure_default_periods(current_user.tenant_id)
    await db.commit()
    return await service.summary(current_user.tenant_id)


@router.get("/periods")
async def list_hs_reporting_periods(db: DbSession, current_user: CurrentUser):
    assert current_user.tenant_id is not None
    rows = await HsKpiService(db).ensure_default_periods(current_user.tenant_id)
    await db.commit()
    items = []
    for row in rows:
        hours = effective_hours(row)
        items.append(
            {
                "id": row.id,
                "reporting_year": row.reporting_year,
                "period_start": row.period_start.isoformat(),
                "period_end": row.period_end.isoformat(),
                "average_fte": row.average_fte,
                "hours_per_fte_year": row.hours_per_fte_year,
                "manual_hours": row.manual_hours,
                "hours": round(hours, 2),
                "hours_source": ("manual" if row.manual_hours is not None and row.manual_hours > 0 else "calculated"),
            }
        )
    return {"items": items, "total": len(items)}


@router.put("/periods/{reporting_year}")
async def put_hs_reporting_period(
    reporting_year: int,
    payload: HsReportingPeriodInput,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("analytics:manage"))],
):
    assert current_user.tenant_id is not None
    if payload.reporting_year != reporting_year or payload.period_end < payload.period_start:
        raise HTTPException(status_code=422, detail="Reporting year and period dates are invalid")
    row = (
        await db.execute(
            select(HsReportingPeriod).where(
                HsReportingPeriod.tenant_id == current_user.tenant_id,
                HsReportingPeriod.reporting_year == reporting_year,
            )
        )
    ).scalar_one_or_none()
    data = payload.model_dump()
    if row is None:
        row = HsReportingPeriod(tenant_id=current_user.tenant_id, **data)
        db.add(row)
    else:
        for field, value in data.items():
            setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    hours = effective_hours(row)
    return {
        "id": row.id,
        "reporting_year": row.reporting_year,
        "period_start": row.period_start.isoformat(),
        "period_end": row.period_end.isoformat(),
        "average_fte": row.average_fte,
        "hours_per_fte_year": row.hours_per_fte_year,
        "manual_hours": row.manual_hours,
        "hours": round(hours, 2),
        "hours_source": "manual" if row.manual_hours is not None and row.manual_hours > 0 else "calculated",
    }
