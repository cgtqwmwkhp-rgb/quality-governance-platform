"""Pydantic schemas for Authentication API."""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Schema for login request."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""

    refresh_token: str


class PasswordChangeRequest(BaseModel):
    """Schema for password change request."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""

    token: str
    new_password: str = Field(..., min_length=8, max_length=100)


class LogoutResponse(BaseModel):
    """Response after successfully revoking tokens."""

    message: str


class ChangePasswordResponse(BaseModel):
    """Response after password change."""

    message: str


class RequestPasswordResetResponse(BaseModel):
    """Response after requesting a password reset email."""

    message: str


class ConfirmPasswordResetResponse(BaseModel):
    """Response after confirming a password reset."""

    message: str
