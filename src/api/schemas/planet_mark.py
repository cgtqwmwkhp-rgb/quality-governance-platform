"""Planet Mark Carbon Management API response schemas."""

from typing import Any, Optional

from pydantic import BaseModel

# ============================================================================
# Reporting Year Schemas
# ============================================================================


class ReportingYearSummary(BaseModel):
    id: int
    year_label: str
    year_number: int
    period: str
    average_fte: float
    total_emissions: Optional[float] = None
    emissions_per_fte: Optional[float] = None
    scope_1: Optional[float] = None
    scope_2_market: Optional[float] = None
    scope_3: Optional[float] = None
    data_quality: Optional[int] = None
    certification_status: Optional[str] = None
    is_baseline: bool = False


class ReportingYearListResponse(BaseModel):
    total: int = 0
    years: list[ReportingYearSummary] = []


class ReportingYearCreatedResponse(BaseModel):
    id: int
    year_label: str
    message: str


class EmissionSourceSummary(BaseModel):
    name: str
    co2e: Optional[float] = None


class Scope1Detail(BaseModel):
    total: Optional[float] = None
    sources: list[EmissionSourceSummary] = []


class Scope2Detail(BaseModel):
    location_based: Optional[float] = None
    market_based: Optional[float] = None
    sources: list[EmissionSourceSummary] = []


class Scope3Detail(BaseModel):
    total: Optional[float] = None
    categories_measured: int = 0


class EmissionsBreakdown(BaseModel):
    scope_1: Scope1Detail = Scope1Detail()
    scope_2: Scope2Detail = Scope2Detail()
    scope_3: Scope3Detail = Scope3Detail()
    total_market_based: Optional[float] = None
    per_fte: Optional[float] = None


class DataQualityScores(BaseModel):
    scope_1: Optional[int] = None
    scope_2: Optional[int] = None
    scope_3: Optional[int] = None
    overall: Optional[int] = None


class ReductionTargets(BaseModel):
    reduction_target_percent: Optional[float] = None
    target_emissions_per_fte: Optional[float] = None


class CertificationInfo(BaseModel):
    status: Optional[str] = None
    certificate_number: Optional[str] = None
    certification_date: Optional[str] = None
    expiry_date: Optional[str] = None


class ReportingYearDetailResponse(BaseModel):
    id: int
    year_label: str
    year_number: int
    organization_name: Optional[str] = None
    period_start: str
    period_end: str
    average_fte: float
    is_baseline_year: bool = False
    emissions: EmissionsBreakdown = EmissionsBreakdown()
    data_quality: DataQualityScores = DataQualityScores()
    targets: ReductionTargets = ReductionTargets()
    certification: CertificationInfo = CertificationInfo()


# ============================================================================
# Emission Source Schemas
# ============================================================================


class EmissionFactorInfo(BaseModel):
    factor: float = 0
    unit: str = ""
    source: str = ""


class EmissionSourceCreatedResponse(BaseModel):
    id: int
    co2e_tonnes: float
    emission_factor: EmissionFactorInfo = EmissionFactorInfo()
    message: str


class EmissionSourceItem(BaseModel):
    id: int
    source_name: str
    source_category: str
    scope: str
    activity_value: float
    activity_unit: str
    co2e_tonnes: float
    percentage: float = 0
    data_quality: Optional[str] = None


class EmissionSourceListResponse(BaseModel):
    year_id: int
    total_co2e: float = 0
    sources: list[EmissionSourceItem] = []


# ============================================================================
# Scope 3 Schemas
# ============================================================================


class Scope3CategoryItem(BaseModel):
    number: int
    name: str
    description: Optional[str] = None
    is_relevant: Optional[bool] = None
    is_measured: Optional[bool] = None
    total_co2e: Optional[float] = None
    percentage: float = 0
    data_quality_score: Optional[int] = None
    calculation_method: Optional[str] = None
    exclusion_reason: Optional[str] = None


class Scope3BreakdownResponse(BaseModel):
    year_id: int
    measured_count: int = 0
    total_measured: int = 15
    total_co2e: float = 0
    categories: list[Scope3CategoryItem] = []


# ============================================================================
# Improvement Action Schemas
# ============================================================================


class ActionSummary(BaseModel):
    total: int = 0
    completed: int = 0
    in_progress: int = 0
    overdue: int = 0
    completion_rate: float = 0


class ActionItem(BaseModel):
    id: int
    action_id: Optional[str] = None
    action_title: str
    owner: Optional[str] = None
    deadline: str
    scheduled_month: Optional[str] = None
    status: str
    progress_percent: int = 0
    target_scope: Optional[str] = None
    expected_reduction_pct: Optional[float] = None
    is_overdue: bool = False


class ActionListResponse(BaseModel):
    year_id: int
    summary: ActionSummary = ActionSummary()
    actions: list[ActionItem] = []


class ActionCreatedResponse(BaseModel):
    id: int
    action_id: str
    message: str


class ActionUpdatedResponse(BaseModel):
    message: str
    id: int


# ============================================================================
# Data Quality Schemas
# ============================================================================


class ScopeQualityDetail(BaseModel):
    score: float = 0
    actual_pct: float = 0
    source_count: Optional[int] = None
    recommendations: list[str] = []


class PriorityImprovement(BaseModel):
    action: str
    impact: str


class DataQualityAssessmentResponse(BaseModel):
    year_id: int
    overall_score: int = 0
    max_score: int = 16
    scopes: dict[str, ScopeQualityDetail] = {}
    priority_improvements: list[PriorityImprovement] = []
    target_scores: dict[str, str] = {}


# ============================================================================
# Fleet Schemas
# ============================================================================


class FleetRecordCreatedResponse(BaseModel):
    id: int
    co2e_kg: float
    litres_per_100km: Optional[float] = None
    message: str


class VehicleSummary(BaseModel):
    registration: str
    type: Optional[str] = None
    fuel_type: str
    total_litres: float = 0
    total_co2e_kg: float = 0
    total_mileage: float = 0
    litres_per_100km: Optional[float] = None


class FleetSummaryResponse(BaseModel):
    year_id: int
    total_litres: float = 0
    total_co2e_tonnes: float = 0
    vehicle_count: int = 0
    vehicles: list[VehicleSummary] = []
    eco_driving_target: str = ""
    message: Optional[str] = None


# ============================================================================
# Utility Schemas
# ============================================================================


class UtilityReadingCreatedResponse(BaseModel):
    id: int
    message: str


# ============================================================================
# Certification Schemas
# ============================================================================


class EvidenceChecklistItem(BaseModel):
    type: str
    category: str
    description: str
    required: bool = False
    uploaded: bool = False
    verified: bool = False


class CertificationStatusResponse(BaseModel):
    year_id: int
    year_label: str
    status: Optional[str] = None
    certificate_number: Optional[str] = None
    certification_date: Optional[str] = None
    expiry_date: Optional[str] = None
    readiness_percent: float = 0
    evidence_checklist: list[EvidenceChecklistItem] = []
    actions_completed: int = 0
    actions_total: int = 0
    data_quality_met: bool = False
    next_steps: list[str] = []


# ============================================================================
# Dashboard Schemas
# ============================================================================


class CurrentYearOverview(BaseModel):
    id: int
    label: str
    total_emissions: Optional[float] = None
    emissions_per_fte: Optional[float] = None
    fte: float
    yoy_change_percent: Optional[float] = None
    on_track: bool = False


class ScopeValue(BaseModel):
    value: Optional[float] = None
    label: str


class DashboardEmissionsBreakdown(BaseModel):
    scope_1: ScopeValue = ScopeValue(label="Direct (Fleet, Gas)")
    scope_2: ScopeValue = ScopeValue(label="Indirect (Electricity)")
    scope_3: ScopeValue = ScopeValue(label="Value Chain")


class DashboardDataQuality(BaseModel):
    scope_1_2: int = 0
    scope_3: int = 0
    target: int = 12


class DashboardCertification(BaseModel):
    status: Optional[str] = None
    expiry_date: Optional[str] = None


class DashboardActions(BaseModel):
    total: int = 0
    completed: int = 0
    overdue: int = 0


class DashboardTargets(BaseModel):
    reduction_percent: Optional[float] = None
    target_per_fte: Optional[float] = None


class HistoricalYearItem(BaseModel):
    label: str
    total: Optional[float] = None
    per_fte: Optional[float] = None


class CarbonDashboardResponse(BaseModel):
    current_year: CurrentYearOverview
    emissions_breakdown: DashboardEmissionsBreakdown = DashboardEmissionsBreakdown()
    data_quality: DashboardDataQuality = DashboardDataQuality()
    certification: DashboardCertification = DashboardCertification()
    actions: DashboardActions = DashboardActions()
    targets: DashboardTargets = DashboardTargets()
    historical_years: list[HistoricalYearItem] = []


# ============================================================================
# ISO 14001 Cross-Mapping Schemas
# ============================================================================


class ISO14001MappingItem(BaseModel):
    pm_requirement: str
    pm_category: str
    iso14001_clause: str
    iso14001_title: str
    mapping_type: str
    notes: Optional[str] = None


class ISO14001MappingResponse(BaseModel):
    description: str
    mappings: list[ISO14001MappingItem] = []
