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

from datetime import datetime
from typing import Optional

from fastapi import APIRouter

from src.api.dependencies import CurrentUser
from src.domain.services.compliance_automation_service import compliance_automation_service

router = APIRouter()


# ============================================================================
# REGULATORY MONITORING
# ============================================================================


@router.get("/regulatory-updates")
async def list_regulatory_updates(
    current_user: CurrentUser,
    source: Optional[str] = None,
    impact: Optional[str] = None,
    reviewed: Optional[bool] = None,
):
    """List regulatory updates with filters."""
    updates = compliance_automation_service.get_regulatory_updates(
        source=source,
        impact=impact,
        reviewed=reviewed,
    )
    return {
        "updates": updates,
        "total": len(updates),
        "unreviewed": sum(1 for u in updates if not u["is_reviewed"]),
    }


@router.post("/regulatory-updates/{update_id}/review")
async def review_regulatory_update(
    update_id: int,
    current_user: CurrentUser,
    requires_action: bool = False,
    action_notes: Optional[str] = None,
):
    """Mark a regulatory update as reviewed."""
    return compliance_automation_service.mark_update_reviewed(
        update_id=update_id,
        reviewed_by=current_user.id,
        requires_action=requires_action,
        action_notes=action_notes,
    )


# ============================================================================
# GAP ANALYSIS
# ============================================================================


@router.post("/gap-analysis/run")
async def run_gap_analysis(
    current_user: CurrentUser,
    regulatory_update_id: Optional[int] = None,
    standard_id: Optional[int] = None,
):
    """Run automated gap analysis."""
    return compliance_automation_service.run_gap_analysis(
        regulatory_update_id=regulatory_update_id,
        standard_id=standard_id,
    )


@router.get("/gap-analyses")
async def list_gap_analyses(
    current_user: CurrentUser,
    status: Optional[str] = None,
):
    """List gap analyses."""
    analyses = compliance_automation_service.get_gap_analyses(status=status)
    return {"analyses": analyses, "total": len(analyses)}


# ============================================================================
# CERTIFICATE TRACKING
# ============================================================================


@router.get("/certificates")
async def list_certificates(
    current_user: CurrentUser,
    certificate_type: Optional[str] = None,
    entity_type: Optional[str] = None,
    status: Optional[str] = None,
    expiring_within_days: Optional[int] = None,
):
    """List certificates with filters."""
    certificates = compliance_automation_service.get_certificates(
        certificate_type=certificate_type,
        entity_type=entity_type,
        status=status,
        expiring_within_days=expiring_within_days,
    )
    return {"certificates": certificates, "total": len(certificates)}


@router.get("/certificates/expiring-summary")
async def get_expiring_certificates_summary(current_user: CurrentUser):
    """Get summary of expiring certificates."""
    return compliance_automation_service.get_expiring_certificates_summary()


# ============================================================================
# SCHEDULED AUDITS
# ============================================================================


@router.get("/scheduled-audits")
async def list_scheduled_audits(
    current_user: CurrentUser,
    upcoming_days: Optional[int] = None,
    overdue: Optional[bool] = None,
):
    """List scheduled audits."""
    audits = compliance_automation_service.get_scheduled_audits(
        upcoming_days=upcoming_days,
        overdue=overdue,
    )
    return {"audits": audits, "total": len(audits)}


# ============================================================================
# COMPLIANCE SCORING
# ============================================================================


@router.get("/score")
async def get_compliance_score(
    current_user: CurrentUser,
    scope_type: str = "organization",
    scope_id: Optional[str] = None,
):
    """Calculate current compliance score."""
    return compliance_automation_service.calculate_compliance_score(
        scope_type=scope_type,
        scope_id=scope_id,
    )


@router.get("/score/trend")
async def get_compliance_trend(
    current_user: CurrentUser,
    scope_type: str = "organization",
    months: int = 12,
):
    """Get compliance score trend over time."""
    trend = compliance_automation_service.get_compliance_trend(
        scope_type=scope_type,
        months=months,
    )
    return {"trend": trend, "period_months": months}


# ============================================================================
# RIDDOR AUTOMATION
# ============================================================================


@router.post("/riddor/check")
async def check_riddor_required(
    incident_data: dict,
    current_user: CurrentUser,
):
    """Check if incident requires RIDDOR reporting."""
    return compliance_automation_service.check_riddor_required(incident_data)


@router.post("/riddor/prepare/{incident_id}")
async def prepare_riddor_submission(
    incident_id: int,
    riddor_type: str,
    current_user: CurrentUser,
):
    """Prepare RIDDOR submission data."""
    return compliance_automation_service.prepare_riddor_submission(
        incident_id=incident_id,
        riddor_type=riddor_type,
    )


@router.post("/riddor/submit/{incident_id}")
async def submit_riddor(
    incident_id: int,
    current_user: CurrentUser,
):
    """Submit RIDDOR report to HSE."""
    return compliance_automation_service.submit_riddor(
        incident_id=incident_id,
        submitted_by=current_user.id,
    )
