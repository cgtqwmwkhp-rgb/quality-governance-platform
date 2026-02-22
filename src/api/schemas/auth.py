"""Pydantic schemas for Authentication API."""

import re

from pydantic import BaseModel, EmailStr, Field, field_validator


def _validate_strong_password(password: str) -> str:
    """Enforce password complexity: >=12 chars, upper, lower, digit, special."""
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]", password):
        raise ValueError("Password must contain at least one special character")
    return password


class LoginRequest(BaseModel):
    """Schema for login request."""

    email: EmailStr
    password: str = Field(..., min_length=8)


class RegisterRequest(BaseModel):
    """Schema for user registration with strong password enforcement."""

    email: EmailStr
    password: str = Field(..., min_length=12, max_length=100)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_strong_password(v)


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
    new_password: str = Field(..., min_length=12, max_length=100)

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        return _validate_strong_password(v)


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""

    token: str
    new_password: str = Field(..., min_length=12, max_length=100)

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        return _validate_strong_password(v)


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


class MFASetupResponse(BaseModel):
    """Response with TOTP provisioning details."""

    secret: str
    provisioning_uri: str


class MFAVerifyRequest(BaseModel):
    """Request to verify a TOTP code and enable MFA."""

    code: str = Field(..., min_length=6, max_length=6)


class MFAVerifyResponse(BaseModel):
    """Response after MFA verification."""

    message: str
    mfa_enabled: bool


class MFADisableRequest(BaseModel):
    """Request to disable MFA (requires current password)."""

    password: str = Field(..., min_length=1)


class MFADisableResponse(BaseModel):
    """Response after disabling MFA."""

    message: str
    mfa_enabled: bool
