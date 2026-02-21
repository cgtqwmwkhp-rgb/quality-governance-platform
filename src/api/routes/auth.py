"""Authentication API routes.

Thin controller layer — all business logic lives in AuthService.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.auth import (
    ChangePasswordResponse,
    ConfirmPasswordResetResponse,
    LoginRequest,
    LogoutResponse,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RequestPasswordResetResponse,
    TokenResponse,
)
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.user import UserResponse
from src.domain.services.auth_service import AuthService
from src.infrastructure.monitoring.azure_monitor import track_metric

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

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
    service = AuthService(db)
    try:
        user, access_token, refresh_token = await service.exchange_azure_token(request.id_token)
    except ValueError as exc:
        detail = ErrorCode.VALIDATION_ERROR
        if "Invalid Azure AD token" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorCode.AUTHENTICATION_REQUIRED,
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

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
    _span = tracer.start_span("login") if tracer else None
    service = AuthService(db)
    try:
        _user, access_token, refresh_token = await service.authenticate(
            request.email, request.password
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorCode.AUTHENTICATION_REQUIRED,
            headers={"WWW-Authenticate": "Bearer"},
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorCode.PERMISSION_DENIED,
        )

    track_metric("auth.login")
    if _span:
        _span.end()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: DbSession) -> TokenResponse:
    """Refresh access token using refresh token."""
    service = AuthService(db)
    try:
        access_token, new_refresh_token = await service.refresh_tokens(request.refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorCode.TOKEN_EXPIRED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


security_scheme = HTTPBearer()


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: DbSession = None,  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-001
) -> LogoutResponse:
    """Revoke the current access token so it can no longer be used."""
    service = AuthService(db)
    try:
        await service.logout(credentials.credentials)
    except ValueError as exc:
        if "missing jti" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorCode.VALIDATION_ERROR,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorCode.TOKEN_EXPIRED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    track_metric("auth.logout")
    return LogoutResponse(message="Successfully logged out")


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


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    request: PasswordChangeRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ChangePasswordResponse:
    """Change current user's password."""
    service = AuthService(db)
    try:
        await service.change_password(current_user, request.current_password, request.new_password)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.VALIDATION_ERROR,
        )

    return ChangePasswordResponse(message="Password changed successfully")


# =============================================================================
# Password Reset (Forgot Password)
# =============================================================================


@router.post("/password-reset/request", response_model=RequestPasswordResetResponse)
async def request_password_reset(
    request: PasswordResetRequest,
    db: DbSession,
) -> RequestPasswordResetResponse:
    """
    Request a password reset email.

    Security:
        - Always returns 200 regardless of whether user exists (prevent email enumeration)
        - Token expires in 1 hour
        - Email is masked in logs
    """
    service = AuthService(db)
    await service.request_password_reset(request.email)

    return RequestPasswordResetResponse(
        message="If an account with that email exists, a password reset link has been sent."
    )


@router.post("/password-reset/confirm", response_model=ConfirmPasswordResetResponse)
async def confirm_password_reset(
    request: PasswordResetConfirm,
    db: DbSession,
) -> ConfirmPasswordResetResponse:
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
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.TOKEN_EXPIRED,
        )

    return ConfirmPasswordResetResponse(message="Password has been reset successfully")
