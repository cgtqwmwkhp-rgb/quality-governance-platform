"""Testing endpoints for CI/CD - STAGING ONLY.

These endpoints are only available when APP_ENV=staging.
They are disabled in production for security.
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from src.api.dependencies import DbSession
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
    roles: list[str] = ["user", "employee", "admin", "viewer"]


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
            detail="This endpoint is only available in staging environment",
        )

    # Security check 2: Require CI secret
    ci_secret = os.environ.get("CI_TEST_SECRET", "")
    if not ci_secret:
        logger.warning("CI_TEST_SECRET not configured in staging")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Testing endpoints not configured",
        )

    if not x_ci_secret or x_ci_secret != ci_secret:
        logger.warning("Invalid or missing X-CI-Secret header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid CI secret",
        )

    # Check if user exists
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    created = False

    if user is None:
        # Create user
        user = User(
            email=request.email,
            hashed_password=get_password_hash(request.password),
            first_name=request.first_name,
            last_name=request.last_name,
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        created = True
        logger.info(f"Created test user with ID: {user.id}")
    else:
        # Update password (in case it changed)
        user.hashed_password = get_password_hash(request.password)
        user.is_active = True
        await db.commit()
        logger.info(f"Updated test user with ID: {user.id}")

    # Assign roles
    if request.roles:
        result = await db.execute(select(Role).where(Role.name.in_(request.roles)))
        roles = result.scalars().all()
        user.roles = list(roles)  # type: ignore[arg-type]  # TYPE-IGNORE: SQLALCHEMY-1
        await db.commit()

    # Get role names for response
    role_names = [r.name for r in user.roles] if user.roles else []

    return TestUserResponse(
        user_id=user.id,
        email=user.email,
        is_active=user.is_active,
        roles=role_names,
        created=created,
    )


@router.get("/health")
async def testing_health() -> dict:
    """Check if testing endpoints are available."""
    return {
        "available": is_staging_env(),
        "environment": os.environ.get("APP_ENV", settings.app_env),
    }
