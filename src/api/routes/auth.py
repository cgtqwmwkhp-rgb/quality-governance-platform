"""Authentication API routes."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from src.api.schemas.user import UserResponse
from src.core.azure_auth import (
    extract_user_info_from_azure_token,
    validate_azure_id_token,
)
from src.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
    verify_password_reset_token,
)
from src.domain.models.user import User
from src.domain.services.email_service import email_service
from src.domain.services.token_service import TokenService
from src.infrastructure.monitoring.azure_monitor import track_metric

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

    track_metric("auth.login")
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

    # Revoke the old refresh token
    old_jti = payload.get("jti")
    if old_jti:
        expires_at = datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc)
        await TokenService.revoke_token(
            db=db,
            jti=old_jti,
            user_id=int(user_id),
            expires_at=expires_at,
            reason="token_refresh",
        )

    # Generate new tokens
    access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


security_scheme = HTTPBearer()


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: DbSession = None,  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-001
) -> dict:
    """Revoke the current access token so it can no longer be used."""
    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = payload.get("jti")
    if jti is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token does not contain a jti claim",
        )

    exp_timestamp = payload.get("exp")
    expires_at = (
        datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        if exp_timestamp
        else datetime.now(timezone.utc)
    )

    user_id_raw = payload.get("sub")
    user_id = int(user_id_raw) if user_id_raw else None

    await TokenService.revoke_token(
        db=db,
        jti=jti,
        user_id=user_id,
        expires_at=expires_at,
        reason="logout",
    )

    track_metric("auth.logout")
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser) -> UserResponse:
    """Get current authenticated user information."""
    return UserResponse.model_validate(current_user)


class WhoAmIResponse(BaseModel):
    """Response for whoami endpoint - debugging auth issues."""

    authenticated: bool
    user_id: int
    email: str
    is_active: bool
    is_superuser: bool
    token_type: str
    roles: list[str]


@router.get("/whoami", response_model=WhoAmIResponse)
async def whoami(current_user: CurrentUser) -> WhoAmIResponse:
    """
    Diagnostic endpoint to verify token validity and user identity.

    Use this to confirm:
    1. Token is valid and not expired
    2. User exists and is active
    3. Roles/permissions are correct

    If this returns 401, the issue is with token validation.
    If this returns 200, but /actions returns 401, check endpoint-specific auth.
    """
    # Get user roles
    role_names = (
        [role.name for role in current_user.roles] if current_user.roles else []
    )

    return WhoAmIResponse(
        authenticated=True,
        user_id=current_user.id,
        email=current_user.email,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        token_type="platform_jwt",
        roles=role_names,
    )


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


# =============================================================================
# Password Reset (Forgot Password)
# =============================================================================


@router.post("/password-reset/request")
async def request_password_reset(
    request: PasswordResetRequest,
    db: DbSession,
) -> dict:
    """
    Request a password reset email.

    Security:
        - Always returns 200 regardless of whether user exists (prevent email enumeration)
        - Token expires in 1 hour
        - Email is masked in logs
    """
    # Find user by email
    result = await db.execute(select(User).where(User.email == request.email.lower()))
    user = result.scalar_one_or_none()

    if user is not None and user.is_active:
        # Generate password reset token
        reset_token = create_password_reset_token(user.id)

        # Build reset URL (frontend will handle this route)
        # Use environment variable for frontend URL, fallback to common values
        import os

        frontend_url = os.getenv(
            "FRONTEND_URL", "https://app-qgp-prod.azurestaticapps.net"
        )
        reset_url = f"{frontend_url}/reset-password?token={reset_token}"

        # Send password reset email
        try:
            await email_service.send_password_reset_email(
                to=user.email,
                reset_url=reset_url,
                user_name=user.first_name or user.email.split("@")[0],
            )
            # Mask email for logging (show first 3 chars and domain)
            masked_email = user.email[:3] + "***@" + user.email.split("@")[1]
            logger.info(f"Password reset email sent to {masked_email}")
        except Exception as e:
            # Log error but don't reveal to user
            logger.error(f"Failed to send password reset email: {e}")

    # Always return success to prevent email enumeration
    return {
        "message": "If an account with that email exists, a password reset link has been sent."
    }


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    request: PasswordResetConfirm,
    db: DbSession,
) -> dict:
    """
    Confirm password reset with token and set new password.

    Security:
        - Validates JWT token signature and expiration
        - Token must be of type 'password_reset'
        - User must exist and be active
    """
    # Verify the reset token
    user_id = verify_password_reset_token(request.token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    # Find user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    # Update password
    user.hashed_password = get_password_hash(request.new_password)
    await db.commit()

    logger.info(f"Password reset successful for user ID {user_id}")

    return {"message": "Password has been reset successfully"}
