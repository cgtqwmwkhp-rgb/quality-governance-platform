"""Feature Flags API routes."""

from fastapi import APIRouter, HTTPException, Query, status

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.feature_flag import (
    FeatureFlagCreate,
    FeatureFlagEvaluateRequest,
    FeatureFlagEvaluateResponse,
    FeatureFlagListResponse,
    FeatureFlagResponse,
    FeatureFlagUpdate,
)
from src.api.utils.errors import api_error
from src.domain.services.feature_flag_service import FeatureFlagService

router = APIRouter()


@router.get("/", response_model=FeatureFlagListResponse)
async def list_feature_flags(
    db: DbSession,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> FeatureFlagListResponse:
    """List all feature flags."""
    service = FeatureFlagService(db)
    flags = await service.list_flags()
    paginated = flags[skip : skip + limit]
    return FeatureFlagListResponse(
        items=[FeatureFlagResponse.model_validate(f) for f in paginated],
        total=len(flags),
    )


@router.post(
    "/",
    response_model=FeatureFlagResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_feature_flag(
    data: FeatureFlagCreate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> FeatureFlagResponse:
    """Create a new feature flag (admin only)."""
    service = FeatureFlagService(db)

    existing = await service._get_flag(data.key)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=api_error(ErrorCode.DUPLICATE_ENTITY, "Feature flag with this key already exists"),
        )

    flag = await service.create_flag(
        key=data.key,
        name=data.name,
        description=data.description or "",
        enabled=data.enabled,
        rollout_percentage=data.rollout_percentage,
        created_by=current_user.email,
    )

    if data.tenant_overrides is not None:
        flag.tenant_overrides = data.tenant_overrides  # type: ignore[assignment]  # SQLAlchemy JSON Column
    if data.metadata_ is not None:
        flag.metadata_ = data.metadata_  # type: ignore[assignment]  # SQLAlchemy JSON Column

    await db.flush()
    return FeatureFlagResponse.model_validate(flag)


@router.get("/{key}", response_model=FeatureFlagResponse)
async def get_feature_flag(
    key: str,
    db: DbSession,
    current_user: CurrentUser,
) -> FeatureFlagResponse:
    """Get a specific feature flag by key."""
    service = FeatureFlagService(db)
    flag = await service._get_flag(key)
    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Feature flag not found"),
        )
    return FeatureFlagResponse.model_validate(flag)


@router.patch("/{key}", response_model=FeatureFlagResponse)
async def update_feature_flag(
    key: str,
    data: FeatureFlagUpdate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> FeatureFlagResponse:
    """Update a feature flag (admin only)."""
    service = FeatureFlagService(db)
    update_data = data.model_dump(exclude_unset=True, by_alias=False)

    flag = await service.update_flag(key, **update_data)
    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Feature flag not found"),
        )
    return FeatureFlagResponse.model_validate(flag)


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feature_flag(
    key: str,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> None:
    """Delete a feature flag (admin only)."""
    service = FeatureFlagService(db)
    deleted = await service.delete_flag(key)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Feature flag not found"),
        )


@router.post("/{key}/evaluate", response_model=FeatureFlagEvaluateResponse)
async def evaluate_feature_flag(
    key: str,
    data: FeatureFlagEvaluateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> FeatureFlagEvaluateResponse:
    """Evaluate whether a feature flag is enabled for a specific tenant/user."""
    service = FeatureFlagService(db)
    flag = await service._get_flag(key)
    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Feature flag not found"),
        )
    enabled = await service.is_enabled(key, tenant_id=data.tenant_id, user_id=data.user_id)
    return FeatureFlagEvaluateResponse(key=key, enabled=enabled)
