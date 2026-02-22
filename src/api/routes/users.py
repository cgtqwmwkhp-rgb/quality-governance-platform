"""User management API routes.

Thin controller layer — all business logic lives in UserService.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.user import (
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from src.api.utils.pagination import PaginationParams
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.services.user_service import UserService
from src.infrastructure.monitoring.azure_monitor import track_metric

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter()


# ============== User Endpoints ==============


@router.get("/search/", response_model=list[UserResponse])
async def search_users(
    db: DbSession,
    current_user: CurrentUser,
    q: str = Query(..., min_length=1, description="Search query for email, first name, or last name"),
) -> list[UserResponse]:
    """Search users by email, first name, or last name."""
    service = UserService(db)
    users = await service.search_users(q, current_user.tenant_id)
    return [UserResponse.model_validate(u) for u in users]


@router.get("/", response_model=UserListResponse)
async def list_users(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
    search: Optional[str] = None,
    department: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> UserListResponse:
    """List all users with pagination and filtering."""
    service = UserService(db)
    return await service.list_users(
        tenant_id=current_user.tenant_id,
        params=params,
        search=search,
        department=department,
        is_active=is_active,
    )


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> UserResponse:
    """Create a new user (superuser only)."""
    _span = tracer.start_span("create_user") if tracer else None
    if _span:
        _span.set_attribute("tenant_id", str(current_user.tenant_id or 0))

    service = UserService(db)
    try:
        user = await service.create_user(
            email=user_data.email,
            password=user_data.password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            job_title=user_data.job_title,
            department=user_data.department,
            phone=user_data.phone,
            tenant_id=current_user.tenant_id,
            role_ids=user_data.role_ids,
        )
    except ValueError:
        raise ValidationError(ErrorCode.DUPLICATE_ENTITY)

    track_metric("user.mutation", 1)
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> UserResponse:
    """Get a specific user by ID."""
    service = UserService(db)
    try:
        user = await service.get_user(user_id, current_user.tenant_id)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> UserResponse:
    """Update a user (superuser only)."""
    service = UserService(db)
    try:
        user = await service.update_user(user_id, current_user.tenant_id, user_data)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)

    track_metric("user.mutation", 1)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> None:
    """Soft delete a user (superuser only)."""
    service = UserService(db)
    try:
        await service.delete_user(user_id, current_user.tenant_id, current_user.id)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    except ValueError:
        raise ValidationError(ErrorCode.VALIDATION_ERROR)

    track_metric("user.mutation", 1)


# ============== Role Endpoints ==============


@router.get("/roles/", response_model=list[RoleResponse])
async def list_roles(
    db: DbSession,
    current_user: CurrentUser,
) -> list[RoleResponse]:
    """List all roles."""
    service = UserService(db)
    roles = await service.list_roles()
    return [RoleResponse.model_validate(r) for r in roles]


@router.post("/roles/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> RoleResponse:
    """Create a new role (superuser only)."""
    service = UserService(db)
    try:
        role = await service.create_role(role_data)
    except ValueError:
        raise ValidationError(ErrorCode.DUPLICATE_ENTITY)
    return RoleResponse.model_validate(role)


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> RoleResponse:
    """Update a role (superuser only)."""
    service = UserService(db)
    try:
        role = await service.update_role(role_id, role_data)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    except PermissionError:
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    return RoleResponse.model_validate(role)
