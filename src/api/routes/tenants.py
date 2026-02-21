"""
Multi-Tenancy API Routes

Provides endpoints for:
- Tenant management
- User-tenant associations
- Branding configuration
- Tenant switching
"""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.dependencies.tenant import verify_tenant_access
from src.api.utils.pagination import PaginationParams, paginate
from src.domain.services.tenant_service import TenantService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter()


# ============================================================================
# Schemas
# ============================================================================


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    admin_email: EmailStr
    domain: Optional[str] = None
    subscription_tier: str = "standard"


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    subscription_tier: Optional[str] = None
    is_active: Optional[bool] = None


class TenantBranding(BaseModel):
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    theme_mode: Optional[str] = Field(None, pattern=r"^(light|dark|system)$")
    custom_css: Optional[str] = None


class TenantUserAdd(BaseModel):
    user_id: int
    role: str = "user"


class TenantInvite(BaseModel):
    email: EmailStr
    role: str = "user"


class TenantResponse(BaseModel):
    id: int
    name: str
    slug: str
    domain: Optional[str]
    is_active: bool
    subscription_tier: str
    logo_url: Optional[str]
    primary_color: str
    theme_mode: str
    max_users: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Tenant CRUD
# ============================================================================


@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    data: TenantCreate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> Any:
    """Create a new tenant."""
    service = TenantService(db)

    try:
        tenant = await service.create_tenant(
            name=data.name,
            slug=data.slug,
            admin_email=data.admin_email,
            admin_user_id=current_user.id,
            subscription_tier=data.subscription_tier,
            domain=data.domain,
        )
        await invalidate_tenant_cache(current_user.tenant_id, "tenants")
        track_metric("tenant.mutation", 1)
        return tenant
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=list[TenantResponse])
async def list_tenants(
    db: DbSession,
    current_user: CurrentSuperuser,
    params: PaginationParams = Depends(),
) -> Any:
    """List all tenants (admin only)."""
    from src.domain.models.tenant import Tenant

    return await paginate(
        db, select(Tenant).options(selectinload(Tenant.users)), params
    )


@router.get("/current", response_model=TenantResponse)
async def get_current_tenant(
    db: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Get the current tenant context."""
    service = TenantService(db)
    tenant = await service.get_tenant(1)

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    return tenant


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Get tenant by ID."""
    await verify_tenant_access(tenant_id, current_user)
    service = TenantService(db)
    tenant = await service.get_tenant(tenant_id)

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    return tenant


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: int,
    data: TenantUpdate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> Any:
    """Update tenant settings."""
    await verify_tenant_access(tenant_id, current_user)
    service = TenantService(db)

    try:
        updates = data.model_dump(exclude_unset=True)
        tenant = await service.update_tenant(tenant_id, **updates)
        await invalidate_tenant_cache(current_user.tenant_id, "tenants")
        track_metric("tenant.mutation", 1)
        return tenant
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# Branding
# ============================================================================


@router.put("/{tenant_id}/branding", response_model=TenantResponse)
async def update_branding(
    tenant_id: int,
    data: TenantBranding,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> Any:
    """Update tenant branding."""
    await verify_tenant_access(tenant_id, current_user)
    service = TenantService(db)

    try:
        tenant = await service.update_branding(
            tenant_id, **data.model_dump(exclude_unset=True)
        )
        await invalidate_tenant_cache(current_user.tenant_id, "tenants")
        track_metric("tenant.mutation", 1)
        return tenant
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# User Management
# ============================================================================


@router.get("/{tenant_id}/users", response_model=dict)
async def list_tenant_users(
    tenant_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Any:
    """List all users in a tenant."""
    await verify_tenant_access(tenant_id, current_user)
    service = TenantService(db)
    users = await service.get_tenant_users(tenant_id)

    return {
        "items": [
            {
                "id": u.id,
                "user_id": u.user_id,
                "role": u.role,
                "is_active": u.is_active,
                "joined_at": u.joined_at,
            }
            for u in users
        ]
    }


@router.post("/{tenant_id}/users", response_model=dict)
async def add_user_to_tenant(
    tenant_id: int,
    data: TenantUserAdd,
    db: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Add a user to a tenant."""
    await verify_tenant_access(tenant_id, current_user)
    service = TenantService(db)

    if not await service.can_add_user(tenant_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User limit reached"
        )

    try:
        tenant_user = await service.add_user_to_tenant(
            tenant_id=tenant_id,
            user_id=data.user_id,
            role=data.role,
        )
        await invalidate_tenant_cache(current_user.tenant_id, "tenants")
        track_metric("tenant.mutation", 1)
        return {"id": tenant_user.id, "role": tenant_user.role}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{tenant_id}/users/{user_id}", response_model=dict)
async def remove_user_from_tenant(
    tenant_id: int,
    user_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Remove a user from a tenant."""
    await verify_tenant_access(tenant_id, current_user)
    service = TenantService(db)

    try:
        await service.remove_user_from_tenant(tenant_id, user_id)
        await invalidate_tenant_cache(current_user.tenant_id, "tenants")
        track_metric("tenant.mutation", 1)
        return {"status": "removed"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# Invitations
# ============================================================================


@router.post("/{tenant_id}/invitations", response_model=dict)
async def create_invitation(
    tenant_id: int,
    data: TenantInvite,
    db: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Create an invitation to join a tenant."""
    await verify_tenant_access(tenant_id, current_user)
    service = TenantService(db)

    invitation = await service.create_invitation(
        tenant_id=tenant_id,
        email=data.email,
        invited_by_id=current_user.id,
        role=data.role,
    )

    return {
        "id": invitation.id,
        "email": invitation.email,
        "token": invitation.token,
        "expires_at": invitation.expires_at,
    }


@router.post("/invitations/{token}/accept", response_model=dict)
async def accept_invitation(
    token: str,
    db: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Accept a tenant invitation."""
    service = TenantService(db)

    try:
        tenant_user = await service.accept_invitation(token, user_id=current_user.id)
        return {"status": "accepted", "tenant_id": tenant_user.tenant_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# Features
# ============================================================================


@router.get("/{tenant_id}/features", response_model=dict)
async def get_features(
    tenant_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Get enabled features for a tenant."""
    await verify_tenant_access(tenant_id, current_user)
    service = TenantService(db)
    tenant = await service.get_tenant(tenant_id)

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    return tenant.features_enabled


@router.put("/{tenant_id}/features/{feature}", response_model=dict)
async def toggle_feature(
    tenant_id: int,
    feature: str,
    db: DbSession,
    current_user: CurrentSuperuser,
    enabled: bool = True,
) -> Any:
    """Enable or disable a feature for a tenant."""
    await verify_tenant_access(tenant_id, current_user)
    service = TenantService(db)

    if enabled:
        await service.enable_feature(tenant_id, feature)
    else:
        await service.disable_feature(tenant_id, feature)

    return {"feature": feature, "enabled": enabled}


# ============================================================================
# Limits
# ============================================================================


@router.get("/{tenant_id}/limits", response_model=dict)
async def get_limits(
    tenant_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Any:
    """Get usage limits for a tenant."""
    await verify_tenant_access(tenant_id, current_user)
    service = TenantService(db)
    tenant = await service.get_tenant(tenant_id)

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    current_users, max_users = await service.check_user_limit(tenant_id)

    return {
        "users": {"current": current_users, "max": max_users},
        "storage_gb": {"current": 0, "max": tenant.max_storage_gb},
    }
