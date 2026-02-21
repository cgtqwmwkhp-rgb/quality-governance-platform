"""AI Intelligence API response schemas."""

from typing import Any, Optional

from pydantic import BaseModel

# ============================================================================
# Text Analysis Schemas
# ============================================================================


class TextAnalysisResponse(BaseModel):
    keywords: list[str] = []
    estimated_severity: Optional[str] = None
    entities: list[str] = []


# ============================================================================
# Anomaly Detection Schemas
# ============================================================================


class FrequencyAnomalyResponse(BaseModel):
    entity: Optional[str] = None
    entity_type: Optional[str] = None
    is_anomaly: bool = False
    current_count: int = 0
    expected_count: Optional[float] = None
    z_score: Optional[float] = None
    message: Optional[str] = None


# ============================================================================
# Root Cause Analysis Schemas
# ============================================================================


class FiveWhysResponse(BaseModel):
    incident_id: int
    answers: list[str] = []
    identified_root_cause: Optional[str] = None
    root_cause_category: Optional[str] = None
    confidence: Optional[float] = None
    recommended_actions: list[str] = []


# ============================================================================
# Audit AI Schemas
# ============================================================================


class FindingClassificationResponse(BaseModel):
    finding_text: Optional[str] = None
    severity: Optional[str] = None
    category: Optional[str] = None
    root_cause_category: Optional[str] = None
    confidence: Optional[float] = None
    suggested_corrective_action: Optional[str] = None


class ExecutiveSummaryResponse(BaseModel):
    summary: str


# ============================================================================
# Audit Trends Schemas
# ============================================================================


class AuditTrendsResponse(BaseModel):
    periods: list[dict[str, Any]] = []
    total_findings: int = 0
    trend_direction: Optional[str] = None
    by_severity: dict[str, int] = {}
    by_standard: dict[str, int] = {}


# ============================================================================
# Health Check Schema
# ============================================================================


class AIServiceStatus(BaseModel):
    text_analysis: bool = True
    anomaly_detection: bool = True
    recommendation_engine: bool = True
    root_cause_analysis: bool = True
    audit_assistant: bool = True
    claude_ai: bool = False


class AIHealthResponse(BaseModel):
    status: str = "operational"
    services: AIServiceStatus = AIServiceStatus()
