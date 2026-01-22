"""Authentication API routes."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.auth import LoginRequest, PasswordChangeRequest, RefreshTokenRequest, TokenResponse
from src.api.schemas.user import UserResponse
from src.core.azure_auth import extract_user_info_from_azure_token, validate_azure_id_token
from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from src.domain.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Azure AD Token Exchange
# =============================================================================


class AzureTokenExchangeRequest(BaseModel):
    """Request to exchange Azure AD token for platform token."""

    id_token: str


class AzureTokenExchangeResponse(BaseModel):
    """Response containing platform tokens."""

    access_token: str
    refresh_token: str
    user: dict


@router.post("/token-exchange", response_model=AzureTokenExchangeResponse)
async def exchange_azure_token(
    request: AzureTokenExchangeRequest,
    db: DbSession,
) -> AzureTokenExchangeResponse:
    """
    Exchange an Azure AD id_token for platform access tokens.

    This enables portal users who authenticate via Microsoft to access
    protected API endpoints using platform-issued JWTs.

    Security:
        - Validates Azure AD token signature via JWKS
        - Verifies issuer, audience, and expiration
        - Creates or updates user in database
        - Issues platform JWT with user's database ID
    """
    # Validate the Azure AD token
    payload = validate_azure_id_token(request.id_token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Azure AD token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user info
    user_info = extract_user_info_from_azure_token(payload)

    if not user_info.get("email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token does not contain email claim",
        )

    email = user_info["email"].lower()
    azure_oid = user_info.get("oid")

    # Find or create user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        # Create new user from Azure AD profile
        name_parts = (user_info.get("name") or email.split("@")[0]).split(" ", 1)
        first_name = name_parts[0] if name_parts else "User"
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            hashed_password="",  # No password - Azure AD auth only
            is_active=True,
            is_superuser=False,
            azure_oid=azure_oid,
            department=user_info.get("department"),
            job_title=user_info.get("job_title"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"Created new user from Azure AD: {email}")
    else:
        # Update Azure OID if not set
        if azure_oid and not user.azure_oid:
            user.azure_oid = azure_oid
            await db.commit()

        # Update last login
        user.last_login = datetime.now(timezone.utc).isoformat()
        await db.commit()

    # Generate platform tokens
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return AzureTokenExchangeResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_superuser": user.is_superuser,
        },
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: DbSession) -> TokenResponse:
    """Authenticate user and return access and refresh tokens."""
    # Find user by email
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Update last login
    user.last_login = datetime.now(timezone.utc).isoformat()
    await db.commit()

    # Generate tokens
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: DbSession) -> TokenResponse:
    """Refresh access token using refresh token."""
    payload = decode_token(request.refresh_token)

    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Generate new tokens
    access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser) -> UserResponse:
    """Get current authenticated user information."""
    return UserResponse.model_validate(current_user)


@router.post("/change-password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """Change current user's password."""
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )

    current_user.hashed_password = get_password_hash(request.new_password)
    await db.commit()

    return {"message": "Password changed successfully"}
