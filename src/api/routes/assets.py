"""Asset Registry API Routes.

REST endpoints for asset types, equipment assets, and template-asset-type linkages.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.asset import (
    AssetCreate,
    AssetListResponse,
    AssetResponse,
    AssetTypeCreate,
    AssetTypeListResponse,
    AssetTypeResponse,
    AssetTypeUpdate,
    AssetUpdate,
    AuditTemplateSummaryResponse,
    TemplateListResponse,
)
from src.api.schemas.error_codes import ErrorCode
from src.api.utils.errors import api_error
from src.domain.models.asset import AssetType
from src.domain.services.asset_service import AssetService

router = APIRouter()


def _is_asset_manager(user: CurrentUser) -> bool:
    role_names = {r.name.lower() for r in getattr(user, "roles", []) or []}
    return bool(getattr(user, "is_superuser", False) or "admin" in role_names or "supervisor" in role_names)


def _assert_asset_write_access(user: CurrentUser) -> None:
    if _is_asset_manager(user):
        return
    raise HTTPException(
        status_code=403,
        detail=api_error(
            ErrorCode.PERMISSION_DENIED,
            "You do not have permission to modify asset registry data",
        ),
    )


def _tid(user: CurrentUser) -> int:
    tid = user.tenant_id
    assert tid is not None, "Tenant context required"
    return tid


# ============== Asset Type endpoints ==============
# Declare /asset-types routes first so they take precedence over /{id}


@router.get("/asset-types", response_model=AssetTypeListResponse)
async def list_asset_types(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    search: Optional[str] = None,
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    """List asset types with filtering and pagination."""
    service = AssetService(db)
    result = await service.list_asset_types(
        tenant_id=_tid(user),
        page=page,
        page_size=page_size,
        search=search,
        category=category,
        is_active=is_active,
    )
    return AssetTypeListResponse(
        items=[AssetTypeResponse.model_validate(t) for t in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        pages=result.pages,
    )


@router.post(
    "/asset-types",
    response_model=AssetTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_asset_type(
    data: AssetTypeCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Create a new asset type."""
    _assert_asset_write_access(user)
    service = AssetService(db)
    asset_type = await service.create_asset_type(
        data=data.model_dump(exclude_unset=True),
        user_id=user.id,
        tenant_id=_tid(user),
    )
    return AssetTypeResponse.model_validate(asset_type)


@router.get("/asset-types/{asset_type_id}", response_model=AssetTypeResponse)
async def get_asset_type(
    asset_type_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Get a specific asset type."""
    service = AssetService(db)
    asset_type = await service._get_entity(AssetType, asset_type_id, tenant_id=_tid(user))
    return AssetTypeResponse.model_validate(asset_type)


@router.patch("/asset-types/{asset_type_id}", response_model=AssetTypeResponse)
async def update_asset_type(
    asset_type_id: int,
    updates: AssetTypeUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update an existing asset type."""
    _assert_asset_write_access(user)
    service = AssetService(db)
    asset_type = await service.update_asset_type(
        asset_type_id=asset_type_id,
        update_data=updates.model_dump(exclude_unset=True),
        tenant_id=_tid(user),
        actor_user_id=user.id,
    )
    return AssetTypeResponse.model_validate(asset_type)


@router.delete("/asset-types/{asset_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset_type(
    asset_type_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Delete an asset type."""
    _assert_asset_write_access(user)
    service = AssetService(db)
    await service.delete_asset_type(
        asset_type_id=asset_type_id,
        tenant_id=_tid(user),
    )


@router.get("/asset-types/{asset_type_id}/templates", response_model=TemplateListResponse)
async def get_templates_for_asset_type(
    asset_type_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Get audit templates linked to an asset type."""
    service = AssetService(db)
    templates = await service.get_templates_for_asset_type(
        asset_type_id=asset_type_id,
        tenant_id=_tid(user),
    )
    return TemplateListResponse(
        items=[AuditTemplateSummaryResponse.model_validate(t) for t in templates],
        total=len(templates),
    )


# ============== Asset endpoints ==============


@router.get("/", response_model=AssetListResponse)
async def list_assets(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    search: Optional[str] = None,
    asset_type_id: Optional[int] = None,
    status: Optional[str] = None,
    site: Optional[str] = None,
):
    """List assets with filtering and pagination."""
    service = AssetService(db)
    result = await service.list_assets(
        tenant_id=_tid(user),
        page=page,
        page_size=page_size,
        search=search,
        asset_type_id=asset_type_id,
        status=status,
        site=site,
    )
    return AssetListResponse(
        items=[AssetResponse.model_validate(a) for a in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        pages=result.pages,
    )


@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    data: AssetCreate,
    db: DbSession,
    user: CurrentUser,
):
    """Create a new asset."""
    _assert_asset_write_access(user)
    service = AssetService(db)
    asset = await service.create_asset(
        data=data.model_dump(exclude_unset=True),
        user_id=user.id,
        tenant_id=_tid(user),
    )
    return AssetResponse.model_validate(asset)


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Get a specific asset."""
    service = AssetService(db)
    asset = await service.get_asset(
        asset_id=asset_id,
        tenant_id=_tid(user),
    )
    return AssetResponse.model_validate(asset)


@router.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: int,
    updates: AssetUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update an existing asset."""
    _assert_asset_write_access(user)
    service = AssetService(db)
    asset = await service.update_asset(
        asset_id=asset_id,
        update_data=updates.model_dump(exclude_unset=True),
        tenant_id=_tid(user),
        actor_user_id=user.id,
    )
    return AssetResponse.model_validate(asset)
