"""Pydantic schemas for User API."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RoleBase(BaseModel):
    """Base schema for Role."""

    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    permissions: Optional[str] = None


class RoleCreate(RoleBase):
    """Schema for creating a Role."""

    pass


class RoleUpdate(BaseModel):
    """Schema for updating a Role."""

    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    permissions: Optional[str] = None


class RoleResponse(BaseModel):
    """Response schema for Role.

    Does NOT inherit from RoleBase to prevent Field validators
    (min_length, max_length) from triggering 500 errors on response serialisation.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    description: Optional[str] = None
    permissions: Optional[str] = None
    is_system_role: bool
    created_at: datetime
    updated_at: datetime


class UserBase(BaseModel):
    """Base schema for User."""

    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    job_title: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)


class UserCreate(UserBase):
    """Schema for creating a User."""

    auth_provider: Literal["microsoft_sso", "local"] = "microsoft_sso"
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    is_active: bool = True
    is_superuser: bool = False
    tenant_id: Optional[int] = None
    role_ids: Optional[List[int]] = None


class UserUpdate(BaseModel):
    """Schema for updating a User."""

    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    job_title: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    tenant_id: Optional[int] = None
    role_ids: Optional[List[int]] = None


class UserResponse(BaseModel):
    """Response schema for User.

    Does NOT inherit from UserBase to prevent Field validators
    (EmailStr, min_length, max_length) from triggering 500 errors on response serialisation.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    email: str
    first_name: str
    last_name: str
    full_name: str
    job_title: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    is_superuser: bool
    azure_oid: Optional[str] = None
    tenant_id: Optional[int] = None
    last_login: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    roles: List[RoleResponse] = []

class UserListResponse(BaseModel):
    """Schema for paginated user list response."""

    items: List[UserResponse]
    total: int
    page: int
    page_size: int
    pages: int
