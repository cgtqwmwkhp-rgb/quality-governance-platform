"""Testing endpoints for CI/CD - STAGING ONLY.

These endpoints are only available when APP_ENV=staging.
They are disabled in production for security.
"""

import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.dependencies import DbSession
from src.api.schemas.error_codes import ErrorCode
from src.core.config import settings
from src.core.security import get_password_hash
from src.domain.models.user import Role, User

logger = logging.getLogger(__name__)

router = APIRouter()


class TestUserRequest(BaseModel):
    """Request to ensure test user exists."""

    email: EmailStr
    password: str
    first_name: str = "UX"
    last_name: str = "TestRunner"
    # Default roles for ETL: includes etl_user role with restricted permissions
    # Removed admin role - ETL should use least-privilege
    roles: list[str] = ["user", "employee", "viewer", "etl_user"]
    # is_superuser is intentionally NOT exposed - ETL users are least-privilege
    is_superuser: bool = False


class TestUserResponse(BaseModel):
    """Response confirming test user status."""

    user_id: int
    email: str
    is_active: bool
    roles: list[str]
    created: bool


def is_staging_env() -> bool:
    """Check if running in staging environment."""
    app_env = os.environ.get("APP_ENV", settings.app_env).lower()
    return app_env == "staging"


# ETL Role Permission Matrix (ADR-0001/ADR-0002 compliant)
# This defines the minimum permissions required for ETL operations
ETL_ROLE_PERMISSIONS = {
    "name": "etl_user",
    "description": "ETL/Data Import user with restricted permissions",
    "permissions": [
        "complaint:create",  # Create complaints via ETL
        "complaint:read",  # Read complaints for validation
        "incident:create",  # Create incidents via ETL
        "incident:read",  # Read incidents for validation
        "rta:create",  # Create RTAs via ETL
        "rta:read",  # Read RTAs for validation
        # Note: Does NOT include:
        # - *:delete (no deletion of records)
        # - *:admin (no admin operations)
        # - user:* (no user management)
        # - role:* (no role management)
        # - investigation:* (investigations managed manually)
        # - action:* (actions managed manually)
    ],
}


async def _ensure_etl_role_exists(db: DbSession) -> Role:
    """
    Ensure the etl_user role exists with correct permissions.

    This is called during test user creation to ensure the role exists.
    The role has restricted permissions following least-privilege principle.
    """
    import json

    result = await db.execute(select(Role).where(Role.name == "etl_user"))
    etl_role = result.scalar_one_or_none()

    if etl_role is None:
        # Create the role with defined permissions
        etl_role = Role(
            name=ETL_ROLE_PERMISSIONS["name"],
            description=ETL_ROLE_PERMISSIONS["description"],
            permissions=json.dumps(ETL_ROLE_PERMISSIONS["permissions"]),
            is_system_role=True,
        )
        db.add(etl_role)
        await db.commit()
        await db.refresh(etl_role)
        logger.info(f"Created etl_user role with ID: {etl_role.id}")
    else:
        # Update permissions if role exists but permissions differ
        current_perms = json.loads(etl_role.permissions) if etl_role.permissions else []
        if set(current_perms) != set(ETL_ROLE_PERMISSIONS["permissions"]):
            etl_role.permissions = json.dumps(ETL_ROLE_PERMISSIONS["permissions"])
            await db.commit()
            logger.info("Updated etl_user role permissions")

    return etl_role


@router.post("/ensure-test-user", response_model=TestUserResponse)
async def ensure_test_user(
    request: TestUserRequest,
    db: DbSession,
    x_ci_secret: Optional[str] = Header(None, alias="X-CI-Secret"),
) -> TestUserResponse:
    """
    Ensure a test user exists for CI testing.

    STAGING ONLY - This endpoint is disabled in production.

    Security:
    - Only available when APP_ENV=staging
    - Requires X-CI-Secret header matching CI_TEST_SECRET env var
    - Never logs email or password
    - Returns minimal user info

    Usage:
        curl -X POST https://staging/api/v1/testing/ensure-test-user \\
          -H "X-CI-Secret: $CI_TEST_SECRET" \\
          -H "Content-Type: application/json" \\
          -d '{"email": "test@example.com", "password": "secure"}'
    """
    # Security check 1: Only staging
    if not is_staging_env():
        logger.warning("Attempt to access testing endpoint in non-staging environment")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorCode.PERMISSION_DENIED,
        )

    # Security check 2: Require CI secret
    ci_secret = os.environ.get("CI_TEST_SECRET", "")
    if not ci_secret:
        logger.warning("CI_TEST_SECRET not configured in staging")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorCode.INTERNAL_ERROR,
        )

    if not x_ci_secret or x_ci_secret != ci_secret:
        logger.warning("Invalid or missing X-CI-Secret header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorCode.PERMISSION_DENIED,
        )

    # Check if user exists - EAGER LOAD roles to avoid MissingGreenlet
    result = await db.execute(select(User).where(User.email == request.email).options(selectinload(User.roles)))
    user = result.scalar_one_or_none()

    created = False

    if user is None:
        # Create user with empty roles list initialized
        # SECURITY: ETL users are NOT superusers - use least-privilege via roles
        user = User(
            email=request.email,
            hashed_password=get_password_hash(request.password),
            first_name=request.first_name,
            last_name=request.last_name,
            is_active=True,
            is_superuser=request.is_superuser,  # Default: False for least-privilege
        )
        # Initialize roles as empty list before adding
        user.roles = []
        db.add(user)
        await db.commit()
        await db.refresh(user)
        created = True
        logger.info(f"Created test user with ID: {user.id} (is_superuser={request.is_superuser})")
    else:
        # Update password but do NOT change is_superuser flag
        user.hashed_password = get_password_hash(request.password)
        user.is_active = True
        # Note: is_superuser is NOT updated - existing users keep their privilege level
        await db.commit()
        logger.info(f"Updated test user with ID: {user.id}")

    # Assign roles - use clear/extend to avoid lazy load trigger
    if request.roles:
        # Ensure etl_user role exists with correct permissions
        if "etl_user" in request.roles:
            await _ensure_etl_role_exists(db)

        role_result = await db.execute(select(Role).where(Role.name.in_(request.roles)))
        roles: List[Role] = list(role_result.scalars().all())  # type: ignore[arg-type]  # TYPE-IGNORE: SQLALCHEMY-1
        # Clear existing roles and add new ones
        # roles relationship is already loaded via selectinload, so this is safe
        user.roles.clear()
        user.roles.extend(roles)
        await db.commit()
        # Refresh to ensure roles are synchronized
        await db.refresh(user, attribute_names=["roles"])

    # Get role names for response - roles are now loaded
    role_names = [r.name for r in user.roles] if user.roles else []

    return TestUserResponse(
        user_id=user.id,
        email=user.email,
        is_active=user.is_active,
        roles=role_names,
        created=created,
    )


@router.get("/health", response_model=dict)
async def testing_health() -> dict:
    """Check if testing endpoints are available."""
    return {
        "available": is_staging_env(),
        "environment": os.environ.get("APP_ENV", settings.app_env),
    }
