"""
Compliance Automation API Routes

Features:
- Regulatory change monitoring
- Gap analysis
- Certificate expiry tracking
- Scheduled audit management
- Compliance scoring
- RIDDOR automation
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, status

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.compliance_automation import (
    AddCertificateResponse,
    AuditScheduleCreate,
    CertificateCreate,
    CertificateExpirySummaryResponse,
    CertificateListResponse,
    ComplianceScoreResponse,
    ComplianceTrendResponse,
    GapAnalysisListResponse,
    PrepareRIDDORSubmissionResponse,
    RegulatoryUpdateResponse,
    ReviewRegulatoryUpdateResponse,
    RIDDORCheckRequest,
    RIDDORCheckResponse,
    RIDDORSubmissionListResponse,
    RunGapAnalysisResponse,
    ScheduleAuditResponse,
    ScheduledAuditListResponse,
    SubmitRIDDORResponse,
)
from src.api.schemas.error_codes import ErrorCode
from src.domain.services.compliance_automation_service import compliance_automation_service
from src.infrastructure.monitoring.azure_monitor import track_metric

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter()


# ============================================================================
# REGULATORY MONITORING
# ============================================================================


@router.get("/regulatory-updates", response_model=RegulatoryUpdateResponse)
async def list_regulatory_updates(
    db: DbSession,
    current_user: CurrentUser,
    source: Optional[str] = None,
    impact: Optional[str] = None,
    reviewed: Optional[bool] = None,
):
    """List regulatory updates with filters."""
    updates = await compliance_automation_service.get_regulatory_updates(
        db=db,
        source=source,
        impact=impact,
        reviewed=reviewed,
    )
    return {
        "updates": updates,
        "total": len(updates),
        "unreviewed": sum(1 for u in updates if not u.get("is_reviewed")),
    }


@router.post("/regulatory-updates/{update_id}/review", response_model=ReviewRegulatoryUpdateResponse)
async def review_regulatory_update(
    update_id: int,
    db: DbSession,
    current_user: CurrentUser,
    requires_action: bool = False,
    action_notes: Optional[str] = None,
):
    """Mark a regulatory update as reviewed."""
    try:
        result = await compliance_automation_service.mark_update_reviewed(
            db=db,
            update_id=update_id,
            reviewed_by=current_user.id,
            requires_action=requires_action,
            action_notes=action_notes,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)


# ============================================================================
# GAP ANALYSIS
# ============================================================================


@router.post("/gap-analysis/run", response_model=RunGapAnalysisResponse)
async def run_gap_analysis(
    db: DbSession,
    current_user: CurrentUser,
    regulatory_update_id: Optional[int] = None,
    standard_id: Optional[int] = None,
):
    """Run automated gap analysis."""
    _span = tracer.start_span("run_gap_analysis") if tracer else None
    result = await compliance_automation_service.run_gap_analysis(
        db=db,
        regulatory_update_id=regulatory_update_id,
        standard_id=standard_id,
    )
    track_metric("compliance_automation.gap_analysis_run", 1)
    if _span:
        _span.end()
    return result


@router.get("/gap-analyses", response_model=GapAnalysisListResponse)
async def list_gap_analyses(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Optional[str] = None,
):
    """List gap analyses."""
    analyses = await compliance_automation_service.get_gap_analyses(
        db=db,
        status=status_filter,
    )
    return {"analyses": analyses, "total": len(analyses)}


# ============================================================================
# CERTIFICATE TRACKING
# ============================================================================


@router.get("/certificates", response_model=CertificateListResponse)
async def list_certificates(
    db: DbSession,
    current_user: CurrentUser,
    certificate_type: Optional[str] = None,
    entity_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    expiring_within_days: Optional[int] = None,
):
    """List certificates with filters."""
    certificates = await compliance_automation_service.get_certificates(
        db=db,
        certificate_type=certificate_type,
        entity_type=entity_type,
        status=status_filter,
        expiring_within_days=expiring_within_days,
    )
    return {"certificates": certificates, "total": len(certificates)}


@router.get("/certificates/expiring-summary", response_model=CertificateExpirySummaryResponse)
async def get_expiring_certificates_summary(
    db: DbSession,
    current_user: CurrentUser,
):
    """Get summary of expiring certificates."""
    return await compliance_automation_service.get_expiring_certificates_summary(db=db)


@router.post("/certificates", response_model=AddCertificateResponse)
async def add_certificate(
    data: CertificateCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Add a new certificate."""
    return await compliance_automation_service.add_certificate(db=db, data=data.model_dump())


# ============================================================================
# SCHEDULED AUDITS
# ============================================================================


@router.get("/scheduled-audits", response_model=ScheduledAuditListResponse)
async def list_scheduled_audits(
    db: DbSession,
    current_user: CurrentUser,
    upcoming_days: Optional[int] = None,
    overdue: Optional[bool] = None,
):
    """List scheduled audits."""
    audits = await compliance_automation_service.get_scheduled_audits(
        db=db,
        upcoming_days=upcoming_days,
        overdue=overdue,
    )
    return {"audits": audits, "total": len(audits)}


@router.post("/scheduled-audits", response_model=ScheduleAuditResponse)
async def schedule_audit(
    data: AuditScheduleCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Schedule a new audit."""
    return await compliance_automation_service.schedule_audit(
        db=db,
        data=data.model_dump(),
        created_by=current_user.id,
    )


# ============================================================================
# COMPLIANCE SCORING
# ============================================================================


@router.get("/score", response_model=ComplianceScoreResponse)
async def get_compliance_score(
    db: DbSession,
    current_user: CurrentUser,
    scope_type: str = "organization",
    scope_id: Optional[str] = None,
):
    """Calculate current compliance score."""
    return await compliance_automation_service.calculate_compliance_score(
        db=db,
        scope_type=scope_type,
        scope_id=scope_id,
    )


@router.get("/score/trend", response_model=ComplianceTrendResponse)
async def get_compliance_trend(
    db: DbSession,
    current_user: CurrentUser,
    scope_type: str = "organization",
    months: int = 12,
):
    """Get compliance score trend over time."""
    trend = await compliance_automation_service.get_compliance_trend(
        db=db,
        scope_type=scope_type,
        months=months,
    )
    return {"trend": trend, "period_months": months}


# ============================================================================
# RIDDOR AUTOMATION
# ============================================================================


@router.get("/riddor/submissions", response_model=RIDDORSubmissionListResponse)
async def list_riddor_submissions(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Optional[str] = None,
):
    """List RIDDOR submissions."""
    submissions = await compliance_automation_service.get_riddor_submissions(
        db=db,
        status=status_filter,
    )
    return {"submissions": submissions, "total": len(submissions)}


@router.post("/riddor/check", response_model=RIDDORCheckResponse)
async def check_riddor_required(
    incident_data: RIDDORCheckRequest,
    current_user: CurrentUser,
):
    """Check if incident requires RIDDOR reporting."""
    return await compliance_automation_service.check_riddor_required(incident_data.model_dump())


@router.post("/riddor/prepare/{incident_id}", response_model=PrepareRIDDORSubmissionResponse)
async def prepare_riddor_submission(
    incident_id: int,
    riddor_type: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Prepare RIDDOR submission data."""
    return await compliance_automation_service.prepare_riddor_submission(
        db=db,
        incident_id=incident_id,
        riddor_type=riddor_type,
    )


@router.post("/riddor/submit/{incident_id}", response_model=SubmitRIDDORResponse)
async def submit_riddor(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Submit RIDDOR report to HSE."""
    try:
        return await compliance_automation_service.submit_riddor(
            db=db,
            incident_id=incident_id,
            submitted_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)
