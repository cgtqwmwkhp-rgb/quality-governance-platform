"""
IMS (Integrated Management System) Dashboard API Route

Thin HTTP layer that delegates to IMSDashboardService for all
database operations and business logic.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
from src.domain.services.ims_dashboard_service import IMSDashboardService
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter(prefix="/ims", tags=["IMS Dashboard"])


class IMSDashboardResponse(BaseModel):
    model_config = {"extra": "allow"}

    generated_at: str
    overall_compliance: float = 0


@router.get("/dashboard", response_model=IMSDashboardResponse)
async def get_ims_dashboard(
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> dict[str, Any]:
    """
    Get unified IMS dashboard aggregating data from all management system modules.

    Returns compliance scores, ISMS data, UVDB audit status, Planet Mark carbon data,
    compliance evidence coverage, and upcoming audit schedule.
    """
    track_metric("ims_dashboard.loaded")
    service = IMSDashboardService(db)
    return await service.get_dashboard()
