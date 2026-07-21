"""Asset Registry API Routes.

REST endpoints for asset types, equipment assets, locations,
and template-asset-type linkages.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status

from src.api.dependencies import CurrentUser, DbSession, require_permission
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
    LocationCreate,
    LocationListResponse,
    LocationResponse,
    LocationUpdate,
    SafetyLookupActionResponse,
    SafetyLookupMergeRequest,
    SafetyLookupPendingListResponse,
    SafetyLookupPreviewRequest,
    SafetyLookupPreviewResponse,
    TemplateListResponse,
)
from src.domain.models.asset import AssetType
from src.domain.models.user import User
from src.domain.services.asset_service import AssetService
from src.domain.services.safety_lookup_approval_service import SafetyLookupApprovalService

router = APIRouter()


def _tid(user: CurrentUser) -> int:
    tid = user.tenant_id
    assert tid is not None, "Tenant context required"
    return tid


# ============== Location endpoints ==============
# Declare /locations before /{id} to avoid path conflicts


@router.get("/locations", response_model=LocationListResponse)
async def list_locations(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    kind: Optional[str] = None,
    is_active: Optional[bool] = None,
    parent_id: Optional[int] = None,
    search: Optional[str] = None,
):
    """List locations with filtering and pagination."""
    service = AssetService(db)
    result = await service.list_locations(
        tenant_id=_tid(user),
        page=page,
        page_size=page_size,
        kind=kind,
        is_active=is_active,
        parent_id=parent_id,
        search=search,
    )
    return LocationListResponse(
        items=[LocationResponse.model_validate(loc) for loc in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        pages=result.pages,
    )


@router.post(
    "/locations",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_location(
    data: LocationCreate,
    db: DbSession,
    user: CurrentUser,
    _: Annotated[User, Depends(require_permission("asset:create"))],
):
    """Create a site or workshop location."""
    service = AssetService(db)
    payload = data.model_dump(exclude_unset=True)
    force = bool(payload.pop("force", False))
    location = await service.create_location(
        data=payload,
        user_id=user.id,
        tenant_id=_tid(user),
        force=force,
    )
    return LocationResponse.model_validate(location)


@router.get("/locations/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Get a specific location."""
    service = AssetService(db)
    location = await service.get_location(location_id, _tid(user))
    return LocationResponse.model_validate(location)


@router.patch("/locations/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: int,
    updates: LocationUpdate,
    db: DbSession,
    user: CurrentUser,
    _: Annotated[User, Depends(require_permission("asset:update"))],
):
    """Update an existing location."""
    service = AssetService(db)
    location = await service.update_location(
        location_id=location_id,
        update_data=updates.model_dump(exclude_unset=True),
        tenant_id=_tid(user),
        actor_user_id=user.id,
    )
    return LocationResponse.model_validate(location)


@router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: int,
    db: DbSession,
    user: CurrentUser,
    _: Annotated[User, Depends(require_permission("asset:delete"))],
):
    """Delete a location."""
    service = AssetService(db)
    await service.delete_location(location_id=location_id, tenant_id=_tid(user))


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
    _: Annotated[User, Depends(require_permission("asset:create"))],
):
    """Create a new asset type."""
    service = AssetService(db)
    payload = data.model_dump(exclude_unset=True)
    force = bool(payload.pop("force", False))
    asset_type = await service.create_asset_type(
        data=payload,
        user_id=user.id,
        tenant_id=_tid(user),
        force=force,
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
    _: Annotated[User, Depends(require_permission("asset:update"))],
):
    """Update an existing asset type."""
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
    _: Annotated[User, Depends(require_permission("asset:delete"))],
):
    """Delete an asset type."""
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


@router.get("/my-tools")
async def my_tools(db: DbSession, user: CurrentUser):
    """Portal self-scope: tools assigned to me ∪ kit on my van."""
    from src.api.schemas.portal_compliance import PortalMyToolsResponse
    from src.domain.services.portal_compliance_service import PortalComplianceService

    payload = await PortalComplianceService(db).my_tools(user_id=user.id, tenant_id=_tid(user))
    return PortalMyToolsResponse.model_validate(payload)


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
    location_id: Optional[int] = None,
    vehicle_reg: Optional[str] = None,
    owner_user_id: Optional[int] = None,
    expiry_band: Optional[str] = Query(
        None,
        description="Expiry filter band: overdue | due_30 | due_60 | due_90",
    ),
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
        location_id=location_id,
        vehicle_reg=vehicle_reg,
        owner_user_id=owner_user_id,
        expiry_band=expiry_band,
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
    _: Annotated[User, Depends(require_permission("asset:create"))],
):
    """Create a new asset."""
    service = AssetService(db)
    asset = await service.create_asset(
        data=data.model_dump(exclude_unset=True),
        user_id=user.id,
        tenant_id=_tid(user),
    )
    return AssetResponse.model_validate(asset)


# ============== Safety lookup approval (CES provisional types/locations) ==============
# Declared before /{asset_id} so "safety-lookups" is not captured as an id.


def _parse_safety_lookup_kind(kind: str):
    from src.domain.exceptions import ValidationError
    from src.domain.services.safety_lookup_approval_service import Kind

    if kind == "asset_type":
        parsed: Kind = "asset_type"
        return parsed
    if kind == "location":
        parsed = "location"
        return parsed
    raise ValidationError("kind must be asset_type or location")


@router.get("/safety-lookups/pending", response_model=SafetyLookupPendingListResponse)
async def list_pending_safety_lookups(
    db: DbSession,
    user: CurrentUser,
    _: Annotated[User, Depends(require_permission("asset:create"))],
):
    result = await SafetyLookupApprovalService(db).list_pending(tenant_id=_tid(user))
    return SafetyLookupPendingListResponse.model_validate(result)


@router.post("/safety-lookups/preview", response_model=SafetyLookupPreviewResponse)
async def preview_safety_lookup_create(
    body: SafetyLookupPreviewRequest,
    db: DbSession,
    user: CurrentUser,
    _: Annotated[User, Depends(require_permission("asset:create"))],
):
    result = await SafetyLookupApprovalService(db).preview_create(
        _parse_safety_lookup_kind(body.kind), body.name, tenant_id=_tid(user)
    )
    return SafetyLookupPreviewResponse.model_validate(result)


@router.post(
    "/safety-lookups/{kind}/{entity_id}/approve",
    response_model=SafetyLookupActionResponse,
)
async def approve_safety_lookup(
    kind: str,
    entity_id: int,
    db: DbSession,
    user: CurrentUser,
    _: Annotated[User, Depends(require_permission("asset:create"))],
):
    result = await SafetyLookupApprovalService(db).approve(
        _parse_safety_lookup_kind(kind),
        entity_id,
        tenant_id=_tid(user),
        actor_user_id=user.id,
    )
    return SafetyLookupActionResponse.model_validate(result)


@router.post(
    "/safety-lookups/{kind}/{entity_id}/merge",
    response_model=SafetyLookupActionResponse,
)
async def merge_safety_lookup(
    kind: str,
    entity_id: int,
    body: SafetyLookupMergeRequest,
    db: DbSession,
    user: CurrentUser,
    _: Annotated[User, Depends(require_permission("asset:create"))],
):
    result = await SafetyLookupApprovalService(db).merge(
        _parse_safety_lookup_kind(kind),
        entity_id,
        target_id=body.target_id,
        tenant_id=_tid(user),
        actor_user_id=user.id,
    )
    return SafetyLookupActionResponse.model_validate(result)


@router.post(
    "/safety-lookups/{kind}/{entity_id}/reject",
    response_model=SafetyLookupActionResponse,
)
async def reject_safety_lookup(
    kind: str,
    entity_id: int,
    body: SafetyLookupMergeRequest,
    db: DbSession,
    user: CurrentUser,
    _: Annotated[User, Depends(require_permission("asset:create"))],
):
    result = await SafetyLookupApprovalService(db).reject(
        _parse_safety_lookup_kind(kind),
        entity_id,
        target_id=body.target_id,
        tenant_id=_tid(user),
        actor_user_id=user.id,
    )
    return SafetyLookupActionResponse.model_validate(result)


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
    _: Annotated[User, Depends(require_permission("asset:update"))],
):
    """Update an existing asset."""
    service = AssetService(db)
    asset = await service.update_asset(
        asset_id=asset_id,
        update_data=updates.model_dump(exclude_unset=True),
        tenant_id=_tid(user),
        actor_user_id=user.id,
    )
    return AssetResponse.model_validate(asset)
