"""User management domain service.

Extracts business logic from user routes into a testable service class.
Raises domain exceptions instead of HTTPException.
"""

from typing import Optional, Sequence

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.core.security import get_password_hash
from src.domain.models.user import Role, User
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache


class UserService:
    """Handles user CRUD, search, and role management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_users(
        self, query_str: str, tenant_id: int | None
    ) -> list[User]:
        """Search users by email, first name, or last name within a tenant."""
        search_filter = f"%{query_str}%"
        query = (
            select(User)
            .options(selectinload(User.roles))
            .where(User.tenant_id == tenant_id)
            .where(
                (User.email.ilike(search_filter))
                | (User.first_name.ilike(search_filter))
                | (User.last_name.ilike(search_filter))
            )
            .where(User.is_active == True)  # noqa: E712
            .order_by(User.email)
            .limit(20)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_users(
        self,
        tenant_id: int | None,
        params: PaginationParams,
        search: Optional[str] = None,
        department: Optional[str] = None,
        is_active: Optional[bool] = None,
    ):
        """List users with pagination and filters."""
        query = (
            select(User)
            .options(selectinload(User.roles))
            .where(User.tenant_id == tenant_id)
        )

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

        return await paginate(self.db, query, params)

    async def create_user(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        job_title: Optional[str] = None,
        department: Optional[str] = None,
        phone: Optional[str] = None,
        tenant_id: int | None,
        role_ids: list[int] | None = None,
    ) -> User:
        """Create a new user.

        Raises:
            ValueError: If the email already exists within the tenant.
        """
        result = await self.db.execute(
            select(User).where(User.email == email, User.tenant_id == tenant_id)
        )
        if result.scalar_one_or_none():
            raise ValueError("A user with this email already exists")

        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            job_title=job_title,
            department=department,
            phone=phone,
            tenant_id=tenant_id,
        )

        if role_ids:
            result = await self.db.execute(select(Role).where(Role.id.in_(role_ids)))
            roles = result.scalars().all()
            user.roles = list(roles)  # type: ignore[arg-type]  # TYPE-IGNORE: SQLALCHEMY-001

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        await invalidate_tenant_cache(tenant_id, "users")

        return user

    async def get_user(self, user_id: int, tenant_id: int | None) -> User:
        """Fetch a single user by ID.

        Raises:
            LookupError: If the user is not found.
        """
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.id == user_id, User.tenant_id == tenant_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise LookupError(f"User with ID {user_id} not found")
        return user

    async def update_user(
        self,
        user_id: int,
        tenant_id: int | None,
        update_schema: BaseModel,
    ) -> User:
        """Update a user's fields.

        Raises:
            LookupError: If the user is not found.
        """
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.id == user_id, User.tenant_id == tenant_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise LookupError(f"User with ID {user_id} not found")

        update_data = update_schema.model_dump(exclude_unset=True)
        role_ids = update_data.get("role_ids")
        if role_ids is not None:
            result = await self.db.execute(select(Role).where(Role.id.in_(role_ids)))
            roles = result.scalars().all()
            user.roles = list(roles)  # type: ignore[arg-type]  # TYPE-IGNORE: SQLALCHEMY-001

        apply_updates(user, update_schema, exclude={"role_ids"})

        await self.db.commit()
        await self.db.refresh(user)
        await invalidate_tenant_cache(tenant_id, "users")

        return user

    async def delete_user(
        self, user_id: int, tenant_id: int | None, current_user_id: int
    ) -> None:
        """Soft-delete a user by deactivating them.

        Raises:
            LookupError: If the user is not found.
            ValueError: If the user tries to delete themselves.
        """
        user = await self.get_user(user_id, tenant_id)

        if user.id == current_user_id:
            raise ValueError("Cannot delete your own account")

        user.is_active = False
        await self.db.commit()
        await invalidate_tenant_cache(tenant_id, "users")

    # ======================== Role operations ========================

    async def list_roles(self) -> Sequence[Role]:
        """List all roles."""
        result = await self.db.execute(select(Role).order_by(Role.name))
        return result.scalars().all()

    async def create_role(self, role_data: BaseModel) -> Role:
        """Create a new role.

        Raises:
            ValueError: If the role name already exists.
        """
        data = role_data.model_dump()
        result = await self.db.execute(select(Role).where(Role.name == data["name"]))
        if result.scalar_one_or_none():
            raise ValueError("A role with this name already exists")

        role = Role(**data)
        self.db.add(role)
        await self.db.commit()
        await self.db.refresh(role)
        return role

    async def update_role(self, role_id: int, role_data: BaseModel) -> Role:
        """Update a role.

        Raises:
            LookupError: If the role is not found.
            PermissionError: If the role is a system role.
        """
        result = await self.db.execute(select(Role).where(Role.id == role_id))
        role = result.scalar_one_or_none()
        if not role:
            raise LookupError(f"Role with ID {role_id} not found")

        if role.is_system_role:
            raise PermissionError("System roles cannot be modified")

        apply_updates(role, role_data)
        await self.db.commit()
        await self.db.refresh(role)
        return role
