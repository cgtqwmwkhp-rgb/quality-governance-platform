"""Authentication API routes."""

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.user import UserResponse
from src.api.utils.errors import api_error
from src.core.security import decode_token
from src.domain.services.auth_service import AuthService
from src.domain.services.email_service import email_service
from src.infrastructure.monitoring.azure_monitor import record_auth_logout, track_metric

logger = logging.getLogger(__name__)

router = APIRouter()


def _auth_http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=api_error(code, message),
        headers={"WWW-Authenticate": "Bearer"} if status_code == status.HTTP_401_UNAUTHORIZED else None,
    )


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
    service = AuthService(db)
    try:
        user, access_token, refresh_token = await service.exchange_azure_token(request.id_token)
    except ValueError as exc:
        message = str(exc)
        if "missing email" in message.lower():
            raise _auth_http_error(status.HTTP_400_BAD_REQUEST, ErrorCode.VALIDATION_ERROR, message) from exc
        raise _auth_http_error(status.HTTP_401_UNAUTHORIZED, ErrorCode.INVALID_CREDENTIALS, message) from exc
    except PermissionError as exc:
        raise _auth_http_error(status.HTTP_403_FORBIDDEN, ErrorCode.ACCOUNT_LOCKED, str(exc)) from exc

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
    service = AuthService(db)
    try:
        _user, access_token, refresh_token = await service.authenticate(request.email, request.password)
    except PermissionError as exc:
        track_metric("auth.failures")
        raise _auth_http_error(status.HTTP_403_FORBIDDEN, ErrorCode.ACCOUNT_LOCKED, str(exc)) from exc
    except ValueError as exc:
        track_metric("auth.failures")
        raise _auth_http_error(status.HTTP_401_UNAUTHORIZED, ErrorCode.INVALID_CREDENTIALS, str(exc)) from exc

    track_metric("auth.login")

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: DbSession) -> TokenResponse:
    """Refresh access token using refresh token."""
    service = AuthService(db)
    try:
        access_token, new_refresh_token = await service.refresh_tokens(request.refresh_token)
    except ValueError as exc:
        message = str(exc)
        code = ErrorCode.TOKEN_REVOKED if "revoked" in message.lower() else ErrorCode.TOKEN_EXPIRED
        raise _auth_http_error(status.HTTP_401_UNAUTHORIZED, code, message) from exc

    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


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
    role_names = [role.name for role in current_user.roles] if current_user.roles else []

    return WhoAmIResponse(
        authenticated=True,
        user_id=current_user.id,
        email=current_user.email,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        token_type="platform_jwt",
        roles=role_names,
    )


@router.post("/logout")
async def logout(current_user: CurrentUser) -> dict:
    """Log out the current user. Records a telemetry event for audit trail."""
    record_auth_logout()
    logger.info("User %s (id=%s) logged out", current_user.email, current_user.id)
    return {"message": "Logged out successfully"}


@router.post("/change-password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """Change current user's password."""
    service = AuthService(db)
    try:
        await service.change_password(current_user, request.current_password, request.new_password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error(ErrorCode.INVALID_CREDENTIALS, str(exc)),
        ) from exc
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
    service = AuthService(db)
    await service.request_password_reset(request.email)

    # Always return success to prevent email enumeration
    return {"message": "If an account with that email exists, a password reset link has been sent."}


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
    service = AuthService(db)
    try:
        await service.confirm_password_reset(request.token, request.new_password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error(ErrorCode.TOKEN_EXPIRED, str(exc)),
        ) from exc
    return {"message": "Password has been reset successfully"}
