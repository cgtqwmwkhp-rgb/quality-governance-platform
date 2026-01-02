"""Pydantic schemas for API request/response validation."""

from src.api.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    PasswordChangeRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
)
from src.api.schemas.user import (
    RoleBase,
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    UserBase,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
)
from src.api.schemas.standard import (
    ControlBase,
    ControlCreate,
    ControlUpdate,
    ControlResponse,
    ClauseBase,
    ClauseCreate,
    ClauseUpdate,
    ClauseResponse,
    StandardBase,
    StandardCreate,
    StandardUpdate,
    StandardResponse,
    StandardDetailResponse,
    StandardListResponse,
)

__all__ = [
    # Auth
    "LoginRequest",
    "TokenResponse",
    "RefreshTokenRequest",
    "PasswordChangeRequest",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    # User
    "RoleBase",
    "RoleCreate",
    "RoleUpdate",
    "RoleResponse",
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserListResponse",
    # Standard
    "ControlBase",
    "ControlCreate",
    "ControlUpdate",
    "ControlResponse",
    "ClauseBase",
    "ClauseCreate",
    "ClauseUpdate",
    "ClauseResponse",
    "StandardBase",
    "StandardCreate",
    "StandardUpdate",
    "StandardResponse",
    "StandardDetailResponse",
    "StandardListResponse",
]
