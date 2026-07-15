"""Read-only LOLER inspection-history API route scaffold."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from src.api.dependencies import CurrentUser, DbSession
from src.domain.services.loler_inspection_service import LOLERInspectionService

router = APIRouter()


class LOLERInspectionHistoryItemResponse(BaseModel):
    id: int
    reference_number: str | None
    examination_type: str
    examination_date: datetime
    next_due_date: datetime | None
    safe_to_operate: bool
    competent_person_name: str
    status: str


class LOLERInspectionHistoryResponse(BaseModel):
    asset_id: int
    next_due_date: datetime | None
    status: str
    items: list[LOLERInspectionHistoryItemResponse]


@router.get(
    "/assets/{asset_id}/inspection-history",
    response_model=LOLERInspectionHistoryResponse,
)
async def get_asset_inspection_history(
    asset_id: int,
    db: DbSession,
    user: CurrentUser,
) -> LOLERInspectionHistoryResponse:
    """Return tenant-scoped LOLER certificate history and current due status."""

    assert user.tenant_id is not None, "Tenant context required"
    history = await LOLERInspectionService(db).get_asset_history(
        asset_id=asset_id,
        tenant_id=user.tenant_id,
    )
    return LOLERInspectionHistoryResponse(
        asset_id=history.asset_id,
        next_due_date=history.next_due_date,
        status=history.status,
        items=[
            LOLERInspectionHistoryItemResponse(
                id=item.id,
                reference_number=item.reference_number,
                examination_type=item.examination_type,
                examination_date=item.examination_date,
                next_due_date=item.next_due_date,
                safe_to_operate=item.safe_to_operate,
                competent_person_name=item.competent_person_name,
                status=item.status,
            )
            for item in history.items
        ],
    )
