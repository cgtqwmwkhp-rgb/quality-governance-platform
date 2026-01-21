"""KRI (Key Risk Indicator) API Schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class KRIBase(BaseModel):
    """Base schema for KRI."""
    code: str = Field(..., max_length=50, description="Unique KRI code")
    name: str = Field(..., max_length=200, description="KRI name")
    description: Optional[str] = None
    category: str = Field(..., description="Category: safety, compliance, operational, etc.")
    unit: str = Field(..., max_length=50, description="Measurement unit")
    measurement_frequency: str = Field("monthly", description="Frequency: daily, weekly, monthly, quarterly")
    data_source: str = Field(..., description="Data source for calculation")
    calculation_method: Optional[str] = None
    auto_calculate: bool = True
    lower_is_better: bool = Field(True, description="If true, lower values indicate better performance")
    green_threshold: float = Field(..., description="Acceptable threshold")
    amber_threshold: float = Field(..., description="Warning threshold")
    red_threshold: float = Field(..., description="Critical threshold")
    linked_risk_ids: Optional[List[int]] = None
    owner_id: Optional[int] = None
    department: Optional[str] = None
    is_active: bool = True


class KRICreate(KRIBase):
    """Schema for creating a KRI."""
    pass


class KRIUpdate(BaseModel):
    """Schema for updating a KRI."""
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    measurement_frequency: Optional[str] = None
    data_source: Optional[str] = None
    calculation_method: Optional[str] = None
    auto_calculate: Optional[bool] = None
    lower_is_better: Optional[bool] = None
    green_threshold: Optional[float] = None
    amber_threshold: Optional[float] = None
    red_threshold: Optional[float] = None
    linked_risk_ids: Optional[List[int]] = None
    owner_id: Optional[int] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None


class KRIResponse(KRIBase):
    """Schema for KRI response."""
    id: int
    current_value: Optional[float] = None
    current_status: Optional[str] = None
    last_updated: Optional[datetime] = None
    trend_direction: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KRIListResponse(BaseModel):
    """List response for KRIs."""
    items: List[KRIResponse]
    total: int


class KRIMeasurementResponse(BaseModel):
    """Schema for KRI measurement."""
    id: int
    kri_id: int
    measurement_date: datetime
    value: float
    status: str
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class KRIMeasurementListResponse(BaseModel):
    """List response for KRI measurements."""
    items: List[KRIMeasurementResponse]
    total: int


class KRIAlertResponse(BaseModel):
    """Schema for KRI alert."""
    id: int
    kri_id: int
    alert_type: str
    severity: str
    triggered_at: datetime
    trigger_value: float
    previous_value: Optional[float] = None
    threshold_breached: Optional[float] = None
    title: str
    message: str
    is_acknowledged: bool
    acknowledged_at: Optional[datetime] = None
    is_resolved: bool
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class KRIAlertListResponse(BaseModel):
    """List response for KRI alerts."""
    items: List[KRIAlertResponse]
    total: int


class KRIDashboardResponse(BaseModel):
    """Schema for KRI dashboard."""
    total: int
    by_status: Dict[str, int]
    by_category: Dict[str, int]
    alerts_pending: int
    kris: List[Dict[str, Any]]


class RiskScoreHistoryResponse(BaseModel):
    """Schema for risk score history entry."""
    id: int
    risk_id: int
    recorded_at: datetime
    likelihood: int
    impact: int
    risk_score: int
    risk_level: str
    trigger_type: str
    trigger_entity_type: Optional[str] = None
    trigger_entity_id: Optional[int] = None
    previous_score: Optional[int] = None
    score_change: Optional[int] = None
    change_reason: Optional[str] = None

    class Config:
        from_attributes = True


class RiskTrendResponse(BaseModel):
    """Schema for risk trend data."""
    risk_id: int
    trend_data: List[Dict[str, Any]]


# SIF Classification Schemas
class SIFAssessmentCreate(BaseModel):
    """Schema for SIF assessment."""
    is_sif: bool = Field(False, description="Is this a Serious Injury or Fatality?")
    is_psif: bool = Field(False, description="Is this a Potential SIF?")
    sif_classification: str = Field(..., description="Classification: SIF, pSIF, Non-SIF")
    sif_rationale: Optional[str] = None
    life_altering_potential: bool = False
    precursor_events: Optional[List[str]] = None
    control_failures: Optional[List[str]] = None


class SIFAssessmentResponse(BaseModel):
    """Schema for SIF assessment response."""
    incident_id: int
    is_sif: bool
    is_psif: bool
    sif_classification: str
    sif_assessment_date: datetime
    sif_assessed_by_id: Optional[int] = None
    sif_rationale: Optional[str] = None
    life_altering_potential: bool
    precursor_events: Optional[List[str]] = None
    control_failures: Optional[List[str]] = None

    class Config:
        from_attributes = True
