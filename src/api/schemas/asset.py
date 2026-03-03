"""Pydantic schemas for Asset Registry API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ============== Asset Type Schemas ==============


class AssetTypeBase(BaseModel):
    """Base schema for Asset Type."""

    category: str = Field(..., description="Asset category (lifting, power, transport, etc.)")
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    icon: Optional[str] = Field(None, max_length=50)
    is_active: bool = True


class AssetTypeCreate(AssetTypeBase):
    """Schema for creating an Asset Type."""

    pass


class AssetTypeUpdate(BaseModel):
    """Schema for updating an Asset Type."""

    category: Optional[str] = None
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None


class AssetTypeResponse(AssetTypeBase):
    """Schema for Asset Type response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class AssetTypeListResponse(BaseModel):
    """Schema for paginated asset type list response."""

    items: List[AssetTypeResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ============== Asset Schemas ==============


class AssetBase(BaseModel):
    """Base schema for Asset."""

    asset_type_id: int
    asset_number: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    make: Optional[str] = Field(None, max_length=100)
    model: Optional[str] = Field(None, max_length=100)
    serial_number: Optional[str] = Field(None, max_length=100)
    year_of_manufacture: Optional[int] = None

    # Lifting-specific
    safe_working_load: Optional[float] = None
    swl_unit: Optional[str] = Field(None, max_length=20)

    # Status
    status: str = "active"

    # Service dates
    last_service_date: Optional[datetime] = None
    next_service_due: Optional[datetime] = None
    last_loler_date: Optional[datetime] = None
    next_loler_due: Optional[datetime] = None

    # Location
    site: Optional[str] = Field(None, max_length=200)
    department: Optional[str] = Field(None, max_length=100)

    # QR code
    qr_code_data: Optional[str] = Field(None, max_length=500)

    # Metadata (stored as metadata_json in model)
    metadata_json: Optional[Dict[str, Any]] = None


class AssetCreate(AssetBase):
    """Schema for creating an Asset."""

    pass


class AssetUpdate(BaseModel):
    """Schema for updating an Asset."""

    asset_type_id: Optional[int] = None
    asset_number: Optional[str] = Field(None, min_length=1, max_length=100)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    year_of_manufacture: Optional[int] = None
    safe_working_load: Optional[float] = None
    swl_unit: Optional[str] = None
    status: Optional[str] = None
    last_service_date: Optional[datetime] = None
    next_service_due: Optional[datetime] = None
    last_loler_date: Optional[datetime] = None
    next_loler_due: Optional[datetime] = None
    site: Optional[str] = None
    department: Optional[str] = None
    qr_code_data: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class AssetResponse(AssetBase):
    """Schema for Asset response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    tenant_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class AssetListResponse(BaseModel):
    """Schema for paginated asset list response."""

    items: List[AssetResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ============== Template Link Schemas ==============


class AuditTemplateSummaryResponse(BaseModel):
    """Minimal audit template for asset-type templates listing."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    external_id: str
    category: Optional[str] = None
    is_active: bool
    is_published: bool


class TemplateListResponse(BaseModel):
    """Schema for templates linked to an asset type."""

    items: List[AuditTemplateSummaryResponse]
    total: int
