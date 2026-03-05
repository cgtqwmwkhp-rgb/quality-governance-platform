"""Pydantic schemas for User API."""

from datetime import datetime
from typing import List, Optional

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

    password: str = Field(..., min_length=8, max_length=100)
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
    job_title: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    roles: List[RoleResponse] = []

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class UserListResponse(BaseModel):
    """Schema for paginated user list response."""

    items: List[UserResponse]
    total: int
    page: int
    page_size: int
    pages: int
