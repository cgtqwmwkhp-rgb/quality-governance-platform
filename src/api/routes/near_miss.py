"""Near Miss API routes.

Thin controller layer — all business logic lives in NearMissService.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
from src.api.schemas.investigation import InvestigationRunListResponse, InvestigationRunResponse
from src.api.schemas.near_miss import NearMissCreate, NearMissListResponse, NearMissResponse, NearMissUpdate
from src.api.utils.pagination import PaginationParams
from src.domain.exceptions import NotFoundError
from src.domain.services.near_miss_service import NearMissService

router = APIRouter(tags=["Near Misses"])


@router.post("/", response_model=NearMissResponse, status_code=status.HTTP_201_CREATED)
async def create_near_miss(
    data: NearMissCreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> NearMissResponse:
    """Report a new near miss."""
    service = NearMissService(db)
    near_miss = await service.create_near_miss(
        data=data,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        request_id=request_id,
    )
    return near_miss


@router.get("/", response_model=NearMissListResponse)
async def list_near_misses(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    contract: Optional[str] = Query(None),
    reporter_email: Optional[str] = Query(None, description="Filter by reporter email"),
) -> NearMissListResponse:
    """List near misses with pagination and filtering."""
    service = NearMissService(db)
    params = PaginationParams(page=page, page_size=page_size)
    paginated = await service.list_near_misses(
        tenant_id=current_user.tenant_id,
        params=params,
        reporter_email=reporter_email,
        status_filter=status_filter,
        priority=priority,
        contract=contract,
    )

    return NearMissListResponse(
        items=[NearMissResponse.model_validate(nm) for nm in paginated.items],
        total=paginated.total,
        page=paginated.page,
        page_size=paginated.page_size,
        pages=paginated.pages,
    )


@router.get("/{near_miss_id}", response_model=NearMissResponse)
async def get_near_miss(
    near_miss_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> NearMissResponse:
    """Get a near miss by ID."""
    service = NearMissService(db)
    try:
        return await service.get_near_miss(near_miss_id, tenant_id=current_user.tenant_id)
    except LookupError:
        raise NotFoundError("Near miss not found")


@router.patch("/{near_miss_id}", response_model=NearMissResponse)
async def update_near_miss(
    near_miss_id: int,
    data: NearMissUpdate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> NearMissResponse:
    """Update a near miss."""
    service = NearMissService(db)
    try:
        return await service.update_near_miss(
            near_miss_id,
            data,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
        )
    except LookupError:
        raise NotFoundError("Near miss not found")


@router.delete("/{near_miss_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_near_miss(
    near_miss_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
    request_id: str = Depends(get_request_id),
) -> None:
    """Delete a near miss."""
    service = NearMissService(db)
    try:
        await service.delete_near_miss(
            near_miss_id,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
        )
    except LookupError:
        raise NotFoundError("Near miss not found")


@router.get("/{near_miss_id}/investigations", response_model=InvestigationRunListResponse)
async def list_near_miss_investigations(
    near_miss_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    """List investigations for a near miss."""
    service = NearMissService(db)
    params = PaginationParams(page=page, page_size=page_size)
    try:
        paginated = await service.list_investigations(
            near_miss_id,
            tenant_id=current_user.tenant_id,
            params=params,
        )
    except LookupError:
        raise NotFoundError("Near miss not found")

    return {
        "items": [InvestigationRunResponse.model_validate(inv) for inv in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "page_size": paginated.page_size,
        "pages": paginated.pages,
    }
