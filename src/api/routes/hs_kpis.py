"""H&S KPI board endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.domain.models.hs_reporting_period import HsReportingPeriod
from src.domain.models.user import User
from src.domain.services.hs_kpi_service import HsKpiService

router = APIRouter()


class HsReportingPeriodInput(BaseModel):
    reporting_year: int = Field(ge=2000, le=2100)
    period_start: date
    period_end: date
    average_fte: float = Field(gt=0)
    hours_per_fte_year: float = Field(default=2124, gt=0)


@router.get("/summary")
async def hs_kpi_summary(db: DbSession, current_user: CurrentUser):
    service = HsKpiService(db)
    await service.ensure_default_periods(current_user.tenant_id)
    await db.commit()
    return await service.summary(current_user.tenant_id)


@router.get("/periods")
async def list_hs_reporting_periods(db: DbSession, current_user: CurrentUser):
    rows = await HsKpiService(db).ensure_default_periods(current_user.tenant_id)
    await db.commit()
    return {"items": rows, "total": len(rows)}


@router.put("/periods/{reporting_year}")
async def put_hs_reporting_period(
    reporting_year: int,
    payload: HsReportingPeriodInput,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("analytics:manage"))],
):
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
    if row is None:
        row = HsReportingPeriod(tenant_id=current_user.tenant_id, **payload.model_dump())
        db.add(row)
    else:
        for field, value in payload.model_dump().items():
            setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return row
