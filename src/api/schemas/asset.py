"""Pydantic schemas for Asset Registry API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ============== Location Schemas ==============


class LocationBase(BaseModel):
    """Base schema for Location."""

    name: str = Field(..., min_length=1, max_length=200)
    kind: str = Field(..., description="Location kind: site | workshop")
    parent_id: Optional[int] = None
    is_active: bool = True


class LocationCreate(LocationBase):
    """Schema for creating a Location."""

    force: bool = False


class LocationUpdate(BaseModel):
    """Schema for updating a Location."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    kind: Optional[str] = None
    parent_id: Optional[int] = None
    is_active: Optional[bool] = None


class LocationResponse(BaseModel):
    """Response schema for Locations."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str
    kind: str
    parent_id: Optional[int] = None
    is_active: bool = True
    approval_status: str = "approved"
    source: Optional[str] = None
    tenant_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class LocationListResponse(BaseModel):
    """Schema for paginated location list response."""

    items: List[LocationResponse]
    total: int
    page: int
    page_size: int
    pages: int


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

    force: bool = False


class AssetTypeUpdate(BaseModel):
    """Schema for updating an Asset Type."""

    category: Optional[str] = None
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None


class AssetTypeResponse(BaseModel):
    """Response schema for Asset Types.

    Decoupled from AssetTypeBase to avoid inheriting Field validators
    (min_length, max_length) that cause 500 errors on API responses.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    category: str
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    is_active: bool = True
    approval_status: str = "approved"
    source: Optional[str] = None
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

    # Location (legacy free-text — kept for back-compat)
    site: Optional[str] = Field(None, max_length=200)
    department: Optional[str] = Field(None, max_length=100)

    # Structured assignment (Safety AM spine)
    location_id: Optional[int] = None
    vehicle_reg: Optional[str] = Field(None, max_length=20)
    owner_user_id: Optional[int] = None
    expiry_date: Optional[datetime] = None
    photo_evidence_id: Optional[int] = None

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
    location_id: Optional[int] = None
    vehicle_reg: Optional[str] = Field(None, max_length=20)
    owner_user_id: Optional[int] = None
    expiry_date: Optional[datetime] = None
    photo_evidence_id: Optional[int] = None
    qr_code_data: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class AssetResponse(BaseModel):
    """Response schema for Assets.

    Decoupled from AssetBase to avoid inheriting Field validators
    (min_length, max_length) that cause 500 errors on API responses.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    external_id: str
    asset_type_id: int
    asset_number: str
    name: str
    description: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    year_of_manufacture: Optional[int] = None
    safe_working_load: Optional[float] = None
    swl_unit: Optional[str] = None
    status: str = "active"
    last_service_date: Optional[datetime] = None
    next_service_due: Optional[datetime] = None
    last_loler_date: Optional[datetime] = None
    next_loler_due: Optional[datetime] = None
    site: Optional[str] = None
    department: Optional[str] = None
    location_id: Optional[int] = None
    vehicle_reg: Optional[str] = None
    owner_user_id: Optional[int] = None
    expiry_date: Optional[datetime] = None
    photo_evidence_id: Optional[int] = None
    qr_code_data: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
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


class AssetHealthSummaryResponse(BaseModel):
    """Read-only asset health KPI summary for the safety analytics hub."""

    total: int
    expiry_bands: Dict[str, int]
    by_type: Dict[str, int]
    by_status: Dict[str, int]
    generated_at: datetime


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


# ============== CSV Import Schemas (AM-IMPORT) ==============


class AssetImportRowError(BaseModel):
    """Single row-level validation error from CSV dry-run / commit."""

    row: int
    code: str
    message: str
    field: Optional[str] = None


class AssetImportPreviewRow(BaseModel):
    """Normalised preview of a valid CSV row."""

    row: int
    asset_number: str
    name: str
    asset_type_id: int
    make: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    owner_user_id: Optional[int] = None
    location_id: Optional[int] = None
    vehicle_reg: Optional[str] = None
    expiry_date: Optional[str] = None
    status: str = "active"


class AssetImportValidationReportResponse(BaseModel):
    """Dry-run validation report for CSV asset import."""

    dry_run: bool
    total_rows: int
    valid_rows: int
    error_rows: int
    ok: bool
    errors: List[AssetImportRowError] = Field(default_factory=list)
    preview: List[AssetImportPreviewRow] = Field(default_factory=list)


class AssetImportCommitResponse(BaseModel):
    """Result of a successful CSV asset import commit."""

    created_count: int
    created_asset_ids: List[int]
    report: AssetImportValidationReportResponse


# ============== CES XLSX Import Schemas ==============


class CesAssetImportRowIssue(BaseModel):
    row: int
    code: str
    message: str
    field: Optional[str] = None
    severity: str = "error"


class CesAssetImportPreviewRow(BaseModel):
    row: int
    action: str
    asset_number: str
    name: str
    serial_number: str
    owner_user_id: Optional[int] = None
    location_id: Optional[int] = None
    vehicle_reg: Optional[str] = None
    status: str
    not_made_available: bool = False


class CesLookupSimilarMatch(BaseModel):
    id: int
    name: str
    score: float


class CesLookupProposal(BaseModel):
    kind: str
    name: str
    intent: str
    reuse_id: Optional[int] = None
    reuse_name: Optional[str] = None
    similar_matches: List[CesLookupSimilarMatch] = Field(default_factory=list)
    row_count: int = 0
    needs_confirmation: bool = False


class CesLookupConfirmation(BaseModel):
    kind: str
    name: str
    action: str
    reuse_id: Optional[int] = None


class CesAssetImportValidationReportResponse(BaseModel):
    dry_run: bool
    total_rows: int
    valid_rows: int
    error_rows: int
    creates: int
    updates: int
    ok: bool
    requires_confirmation: bool = False
    errors: List[CesAssetImportRowIssue] = Field(default_factory=list)
    warnings: List[CesAssetImportRowIssue] = Field(default_factory=list)
    preview: List[CesAssetImportPreviewRow] = Field(default_factory=list)
    lookup_proposals: List[CesLookupProposal] = Field(default_factory=list)


class CesAssetImportCommitResponse(BaseModel):
    created_count: int
    updated_count: int
    created_asset_ids: List[int]
    updated_asset_ids: List[int]
    provisional_type_ids: List[int] = Field(default_factory=list)
    provisional_location_ids: List[int] = Field(default_factory=list)
    report: CesAssetImportValidationReportResponse


class SafetyLookupPendingItem(BaseModel):
    kind: str
    id: int
    name: str
    source: Optional[str] = None
    is_active: bool = False
    approval_status: str
    similar_matches: List[CesLookupSimilarMatch] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class SafetyLookupPendingListResponse(BaseModel):
    items: List[SafetyLookupPendingItem]
    total: int


class SafetyLookupActionResponse(BaseModel):
    kind: str
    id: int
    approval_status: str
    is_active: Optional[bool] = None
    target_id: Optional[int] = None
    merged: Optional[bool] = None


class SafetyLookupMergeRequest(BaseModel):
    target_id: int = Field(..., ge=1)


class SafetyLookupPreviewRequest(BaseModel):
    kind: str
    name: str = Field(..., min_length=1, max_length=200)


class SafetyLookupPreviewResponse(BaseModel):
    kind: str
    name: str
    intent: str
    reuse_id: Optional[int] = None
    reuse_name: Optional[str] = None
    similar_matches: List[CesLookupSimilarMatch] = Field(default_factory=list)
    needs_confirmation: bool = False
    blocked_exact_duplicate: bool = False
