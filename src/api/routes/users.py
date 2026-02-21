"""User management API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.schemas.user import (
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.core.security import get_password_hash
from src.domain.models.user import Role, User

router = APIRouter()


# ============== User Endpoints ==============


@router.get("/search/", response_model=list[UserResponse])
async def search_users(
    db: DbSession,
    current_user: CurrentUser,
    q: str = Query(..., min_length=1, description="Search query for email, first name, or last name"),
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
        .limit(20)
    )

    result = await db.execute(query)
    users = result.scalars().all()

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
    query = select(User).options(selectinload(User.roles))

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

    query = query.order_by(User.last_name, User.first_name)

    return await paginate(db, query, params)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: DbSession,
    current_user: CurrentSuperuser,
) -> UserResponse:
    """Create a new user (superuser only)."""
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        job_title=user_data.job_title,
        department=user_data.department,
        phone=user_data.phone,
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
    result = await db.execute(select(User).options(selectinload(User.roles)).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
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
    result = await db.execute(select(User).options(selectinload(User.roles)).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

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
    user = await get_or_404(db, User, user_id)

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
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
    # Check if role name already exists
    result = await db.execute(select(Role).where(Role.name == role_data.name))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role name already exists",
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
    role = await get_or_404(db, Role, role_id)

    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify system roles",
        )

    apply_updates(role, role_data)

    await db.commit()
    await db.refresh(role)

    return RoleResponse.model_validate(role)
