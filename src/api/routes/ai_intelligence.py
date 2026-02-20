"""
AI Intelligence API Routes

Provides endpoints for:
- Predictive Analytics
- Root Cause Analysis
- Anomaly Detection
- Recommendations
- Audit AI Assistant
"""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.api.dependencies import CurrentUser, DbSession
from src.domain.services.ai_audit_service import (
    AuditQuestionGenerator,
    AuditReportGenerator,
    AuditTrendAnalyzer,
    EvidenceMatcher,
    FindingClassifier,
)
from src.domain.services.ai_predictive_service import (
    AnomalyDetector,
    IncidentPredictor,
    RecommendationEngine,
    RootCauseAnalyzer,
    TextAnalyzer,
)

router = APIRouter()


# ============ Pydantic Schemas ============


class TextAnalysisRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=5000)


class RecommendationRequest(BaseModel):
    incident_description: str = Field(..., min_length=10, max_length=5000)
    category: Optional[str] = None


class FiveWhysRequest(BaseModel):
    incident_id: int
    answers: list[str] = Field(..., min_items=1, max_items=7)


class QuestionGenerationRequest(BaseModel):
    standard: str = Field(..., description="ISO 9001, ISO 14001, ISO 45001")
    clause: str = Field(..., min_length=1, max_length=20)
    context: Optional[str] = None


class ChecklistRequest(BaseModel):
    standard: str = Field(..., description="ISO 9001, ISO 14001, ISO 45001")
    scope_clauses: Optional[list[str]] = None


class FindingClassificationRequest(BaseModel):
    finding_text: str = Field(..., min_length=10, max_length=2000)


class BatchFindingRequest(BaseModel):
    findings: list[str] = Field(..., min_items=1, max_items=50)


# ============ Predictive Analytics Endpoints ============


@router.post("/analyze/text", response_model=dict)
async def analyze_text(
    request: TextAnalysisRequest,
) -> dict[str, Any]:
    """Analyze text for keywords, severity, and entities"""
    keywords = TextAnalyzer.extract_keywords(request.text)
    severity = TextAnalyzer.estimate_severity(request.text)
    entities = TextAnalyzer.extract_entities(request.text)

    return {
        "keywords": keywords,
        "estimated_severity": severity,
        "entities": entities,
    }


@router.get("/predict/risk-factors", response_model=list)
async def predict_risk_factors(
    lookback_days: int = Query(365, ge=30, le=730),
    db: DbSession = None,
) -> list[dict[str, Any]]:
    """Identify conditions that predict higher incident likelihood"""
    predictor = IncidentPredictor(db)
    return await predictor.predict_risk_factors(lookback_days)


@router.post("/predict/similar-incidents", response_model=list)
async def find_similar_incidents(
    request: TextAnalysisRequest,
    limit: int = Query(5, ge=1, le=20),
    db: DbSession = None,
) -> list[dict[str, Any]]:
    """Find similar past incidents based on description"""
    predictor = IncidentPredictor(db)
    return await predictor.get_similar_incidents(request.text, limit)


# ============ Anomaly Detection Endpoints ============


@router.get("/anomalies/frequency", response_model=dict)
async def detect_frequency_anomalies(
    entity: str = Query(..., description="Entity name (department, location)"),
    entity_type: str = Query("department", description="Type: department or location"),
    lookback_days: int = Query(90, ge=30, le=365),
    db: DbSession = None,
) -> dict[str, Any]:
    """Detect if incident frequency is abnormal for an entity"""
    detector = AnomalyDetector(db)
    return await detector.detect_frequency_anomalies(entity, entity_type, lookback_days)


@router.get("/anomalies/patterns", response_model=list)
async def detect_pattern_anomalies(
    lookback_days: int = Query(30, ge=7, le=90),
    db: DbSession = None,
) -> list[dict[str, Any]]:
    """Detect unusual patterns across all incidents"""
    detector = AnomalyDetector(db)
    return await detector.detect_pattern_anomalies(lookback_days)


# ============ Recommendation Engine Endpoints ============


@router.post("/recommendations/corrective-actions", response_model=list)
async def get_corrective_action_recommendations(
    request: RecommendationRequest,
    db: DbSession = None,
) -> list[dict[str, Any]]:
    """Get recommended corrective actions for an incident"""
    engine = RecommendationEngine(db)
    return engine.get_corrective_action_recommendations(
        request.incident_description,
        request.category,
    )


# ============ Root Cause Analysis Endpoints ============


@router.get("/root-cause/clusters", response_model=list)
async def get_incident_clusters(
    lookback_days: int = Query(180, ge=30, le=365),
    db: DbSession = None,
) -> list[dict[str, Any]]:
    """Cluster similar incidents to identify systemic issues"""
    analyzer = RootCauseAnalyzer(db)
    return await analyzer.cluster_incidents(lookback_days)


@router.post("/root-cause/5-whys", response_model=dict)
async def analyze_5_whys(
    request: FiveWhysRequest,
    db: DbSession = None,
) -> dict[str, Any]:
    """Analyze 5 Whys and suggest root cause"""
    analyzer = RootCauseAnalyzer(db)
    return analyzer.analyze_5_whys(request.incident_id, request.answers)


# ============ Audit AI Assistant Endpoints ============


@router.post("/audit/generate-questions", response_model=list)
async def generate_audit_questions(
    request: QuestionGenerationRequest,
    db: DbSession = None,
) -> list[dict[str, Any]]:
    """Generate audit questions for a specific clause"""
    generator = AuditQuestionGenerator(db)
    return generator.generate_questions_for_clause(
        request.standard,
        request.clause,
        request.context,
    )


@router.post("/audit/generate-checklist", response_model=list)
async def generate_audit_checklist(
    request: ChecklistRequest,
    db: DbSession = None,
) -> list[dict[str, Any]]:
    """Generate complete audit checklist for a standard"""
    generator = AuditQuestionGenerator(db)
    return generator.generate_full_audit_checklist(
        request.standard,
        request.scope_clauses,
    )


@router.get("/audit/evidence/{standard}/{clause}", response_model=list)
async def find_evidence(
    standard: str,
    clause: str,
    db: DbSession = None,
) -> list[dict[str, Any]]:
    """Find evidence matching a clause requirement"""
    matcher = EvidenceMatcher(db)
    return await matcher.find_evidence_for_clause(standard, clause)


@router.get("/audit/{audit_id}/evidence-gaps", response_model=list)
async def get_evidence_gaps(
    audit_id: int,
    db: DbSession = None,
) -> list[dict[str, Any]]:
    """Identify clauses lacking sufficient evidence"""
    matcher = EvidenceMatcher(db)
    return await matcher.suggest_evidence_gaps(audit_id)


@router.post("/audit/classify-finding", response_model=dict)
async def classify_finding(
    request: FindingClassificationRequest,
    db: DbSession = None,
) -> dict[str, Any]:
    """Classify a finding by severity and root cause"""
    classifier = FindingClassifier(db)
    return classifier.classify_finding(request.finding_text)


@router.post("/audit/classify-findings-batch", response_model=list)
async def classify_findings_batch(
    request: BatchFindingRequest,
    db: DbSession = None,
) -> list[dict[str, Any]]:
    """Classify multiple findings"""
    classifier = FindingClassifier(db)
    return classifier.batch_classify(request.findings)


@router.get("/audit/{audit_id}/executive-summary", response_model=dict)
async def generate_executive_summary(
    audit_id: int,
    db: DbSession = None,
) -> dict[str, str]:
    """Generate executive summary for an audit"""
    generator = AuditReportGenerator(db)
    summary = await generator.generate_executive_summary(audit_id)
    return {"summary": summary}


@router.get("/audit/{audit_id}/findings-report", response_model=list)
async def generate_findings_report(
    audit_id: int,
    db: DbSession = None,
) -> list[dict[str, Any]]:
    """Generate detailed findings report"""
    generator = AuditReportGenerator(db)
    return await generator.generate_findings_report(audit_id)


# ============ Audit Trends Endpoints ============


@router.get("/audit/trends", response_model=dict)
async def get_audit_trends(
    months: int = Query(24, ge=6, le=60),
    db: DbSession = None,
) -> dict[str, Any]:
    """Get audit finding trends over time"""
    analyzer = AuditTrendAnalyzer(db)
    return await analyzer.get_finding_trends(months)


@router.get("/audit/recurring-findings", response_model=list)
async def get_recurring_findings(
    min_occurrences: int = Query(3, ge=2, le=10),
    db: DbSession = None,
) -> list[dict[str, Any]]:
    """Identify recurring findings across audits"""
    analyzer = AuditTrendAnalyzer(db)
    return await analyzer.get_recurring_findings(min_occurrences)


# ============ AI Health Check ============


@router.get("/health", response_model=dict)
async def ai_health_check() -> dict[str, Any]:
    """Check AI service availability"""
    import os

    return {
        "status": "operational",
        "services": {
            "text_analysis": True,
            "anomaly_detection": True,
            "recommendation_engine": True,
            "root_cause_analysis": True,
            "audit_assistant": True,
            "claude_ai": bool(os.getenv("ANTHROPIC_API_KEY")),
        },
    }
