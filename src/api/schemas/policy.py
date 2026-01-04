"""Policy Library API schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.domain.models.policy import DocumentStatus, DocumentType


class PolicyBase(BaseModel):
    """Base policy schema with common fields."""

    title: str = Field(..., min_length=1, max_length=300, description="Policy title")
    description: Optional[str] = Field(None, description="Policy description")
    document_type: DocumentType = Field(default=DocumentType.POLICY, description="Type of document")
    status: DocumentStatus = Field(default=DocumentStatus.DRAFT, description="Document status")


class PolicyCreate(PolicyBase):
    """Schema for creating a new policy."""

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        """Validate title is not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("Title cannot be empty or whitespace")
        return v.strip()


class PolicyUpdate(BaseModel):
    """Schema for updating an existing policy."""

    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    document_type: Optional[DocumentType] = None
    status: Optional[DocumentStatus] = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Validate title is not empty or whitespace if provided."""
        if v is not None and (not v or not v.strip()):
            raise ValueError("Title cannot be empty or whitespace")
        return v.strip() if v else None


class PolicyResponse(PolicyBase):
    """Schema for policy responses."""

    id: int
    reference_number: str
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[int] = None
    updated_by_id: Optional[int] = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class PolicyListResponse(BaseModel):
    """Schema for paginated policy list responses."""

    items: list[PolicyResponse]
    total: int
    page: int = 1
    page_size: int = 50
