"""User management API routes."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import selectinload

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
from src.api.utils.errors import api_error
from src.core.security import get_password_hash
from src.domain.services.feature_flag_service import FeatureFlagService
from src.domain.models.user import Role, User

router = APIRouter()
USER_MANAGEMENT_FLAG_KEY = "admin_user_management"


async def _active_superuser_count(db: DbSession) -> int:
    count = await db.scalar(select(func.count()).select_from(User).where(User.is_superuser == True, User.is_active == True))  # noqa: E712
    return int(count or 0)


async def _ensure_user_management_enabled(db: DbSession) -> None:
    service = FeatureFlagService(db)
    try:
        flag = await service._get_flag(USER_MANAGEMENT_FLAG_KEY)
    except (OperationalError, ProgrammingError):
        return
    if flag is not None and not flag.enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.CONFIGURATION_ERROR, "User management is currently unavailable"),
        )


# ============== User Endpoints ==============


@router.get("/search/", response_model=list[UserResponse])
async def search_users(
    db: DbSession,
    current_user: CurrentUser,
    q: str = Query(
        ...,
        min_length=1,
        description="Search query for email, first name, or last name",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[UserResponse]:
    """Search users by email, first name, or last name."""
    search_filter = f"%{q}%"
    query = (
        select(User)
        .options(selectinload(User.roles))
        .where(
            (User.email.ilike(search_filter))
            | (User.first_name.ilike(search_filter))
            | (User.last_name.ilike(search_filter))
        )
        .where(User.is_active == True)  # noqa: E712
        .order_by(User.email)
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    users = result.scalars().all()

    return [UserResponse.model_validate(u) for u in users]


@router.get("/", response_model=UserListResponse)
async def list_users(
    db: DbSession,
    current_user: CurrentSuperuser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    department: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> UserListResponse:
    """List all users with pagination and filtering."""
    await _ensure_user_management_enabled(db)
    # Build query
    query = select(User).options(selectinload(User.roles))

    # Apply filters
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (User.email.ilike(search_filter))
            | (User.first_name.ilike(search_filter))
            | (User.last_name.ilike(search_filter))
        )
    if department:
        query = query.where(User.department == department)
    if is_active is not None:
        query = query.where(User.is_active == is_active)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(User.last_name, User.first_name)

    result = await db.execute(query)
    users = result.scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=((total or 0) + page_size - 1) // page_size,
    )


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> UserResponse:
    """Create a new user (superuser only)."""
    await _ensure_user_management_enabled(db)
    # Check if email already exists
    normalized_email = user_data.email.lower()
    result = await db.execute(select(User).where(func.lower(User.email) == normalized_email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error(ErrorCode.DUPLICATE_ENTITY, "Email already registered"),
        )

    if user_data.auth_provider == "local" and not user_data.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error(ErrorCode.VALIDATION_ERROR, "Password is required for local accounts"),
        )

    # Create user
    user = User(
        email=normalized_email,
        hashed_password=get_password_hash(user_data.password) if user_data.password else "",
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        job_title=user_data.job_title,
        department=user_data.department,
        phone=user_data.phone,
        is_active=user_data.is_active,
        is_superuser=user_data.is_superuser,
        tenant_id=user_data.tenant_id,
    )

    # Assign roles if provided
    if user_data.role_ids:
        result = await db.execute(select(Role).where(Role.id.in_(user_data.role_ids)))
        roles = result.scalars().all()
        user.roles = list(roles)  # type: ignore[arg-type]  # TYPE-IGNORE: SQLALCHEMY-001

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> UserResponse:
    """Get a specific user by ID."""
    await _ensure_user_management_enabled(db)
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=api_error(ErrorCode.PERMISSION_DENIED, "Not enough permissions to view this user"),
        )

    result = await db.execute(select(User).options(selectinload(User.roles)).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "User not found"),
        )

    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> UserResponse:
    """Update a user (superuser only)."""
    await _ensure_user_management_enabled(db)
    result = await db.execute(select(User).options(selectinload(User.roles)).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "User not found"),
        )

    previous_is_superuser = user.is_superuser
    previous_is_active = user.is_active

    # Update fields
    update_data = user_data.model_dump(exclude_unset=True)

    # Handle role assignment separately
    role_ids = update_data.pop("role_ids", None)
    if role_ids is not None:
        result = await db.execute(select(Role).where(Role.id.in_(role_ids)))
        roles = result.scalars().all()
        user.roles = list(roles)  # type: ignore[arg-type]  # TYPE-IGNORE: SQLALCHEMY-001

    # Update other fields
    for field, value in update_data.items():
        setattr(user, field, value)

    if user.id == current_user.id and user.is_superuser is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error(ErrorCode.INVALID_STATE_TRANSITION, "Cannot remove your own superuser access"),
        )

    if user.id == current_user.id and user.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error(ErrorCode.INVALID_STATE_TRANSITION, "Cannot deactivate your own account"),
        )

    if (
        previous_is_superuser
        and previous_is_active
        and (not user.is_superuser or not user.is_active)
        and await _active_superuser_count(db) <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error(ErrorCode.INVALID_STATE_TRANSITION, "At least one active superuser must remain"),
        )

    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> None:
    """Soft delete a user (superuser only)."""
    await _ensure_user_management_enabled(db)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "User not found"),
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error(ErrorCode.VALIDATION_ERROR, "Cannot delete your own account"),
        )

    if user.is_superuser and await _active_superuser_count(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error(ErrorCode.INVALID_STATE_TRANSITION, "At least one active superuser must remain"),
        )

    user.is_active = False
    await db.commit()


# ============== Role Endpoints ==============


@router.get("/roles/", response_model=list[RoleResponse])
async def list_roles(
    db: DbSession,
    current_user: CurrentUser,
) -> list[RoleResponse]:
    """List all roles."""
    await _ensure_user_management_enabled(db)
    result = await db.execute(select(Role).order_by(Role.name))
    roles = result.scalars().all()
    return [RoleResponse.model_validate(r) for r in roles]


@router.post("/roles/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> RoleResponse:
    """Create a new role (superuser only)."""
    await _ensure_user_management_enabled(db)
    # Check if role name already exists
    result = await db.execute(select(Role).where(Role.name == role_data.name))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error(ErrorCode.DUPLICATE_ENTITY, "Role name already exists"),
        )

    role = Role(**role_data.model_dump())
    db.add(role)
    await db.commit()
    await db.refresh(role)

    return RoleResponse.model_validate(role)


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> RoleResponse:
    """Update a role (superuser only)."""
    await _ensure_user_management_enabled(db)
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Role not found"),
        )

    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error(ErrorCode.INVALID_STATE_TRANSITION, "Cannot modify system roles"),
        )

    update_data = role_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(role, field, value)

    await db.commit()
    await db.refresh(role)

    return RoleResponse.model_validate(role)
