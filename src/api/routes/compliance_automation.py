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

from fastapi import APIRouter, HTTPException

from src.api.dependencies import CurrentUser, DbSession
from src.domain.exceptions import NotFoundError
from src.domain.services.compliance_automation_service import ComplianceAutomationService

router = APIRouter()


# ============================================================================
# REGULATORY MONITORING
# ============================================================================


@router.get("/regulatory-updates")
async def list_regulatory_updates(
    db: DbSession,
    current_user: CurrentUser,
    source: Optional[str] = None,
    impact: Optional[str] = None,
    reviewed: Optional[bool] = None,
):
    """List regulatory updates with filters."""
    service = ComplianceAutomationService(db)
    tenant_id = current_user.tenant_id
    assert tenant_id is not None
    updates = await service.get_regulatory_updates(
        tenant_id=tenant_id,
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
    db: DbSession,
    current_user: CurrentUser,
    requires_action: bool = False,
    action_notes: Optional[str] = None,
):
    """Mark a regulatory update as reviewed."""
    service = ComplianceAutomationService(db)
    tenant_id = current_user.tenant_id
    assert tenant_id is not None
    try:
        response = await service.mark_update_reviewed(
            tenant_id=tenant_id,
            update_id=update_id,
            reviewed_by=current_user.id,
            requires_action=requires_action,
            action_notes=action_notes,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    return response


# ============================================================================
# GAP ANALYSIS
# ============================================================================


@router.post("/gap-analysis/run")
async def run_gap_analysis(
    db: DbSession,
    current_user: CurrentUser,
    regulatory_update_id: Optional[int] = None,
    standard_id: Optional[int] = None,
):
    """Run automated gap analysis."""
    service = ComplianceAutomationService(db)
    tenant_id = current_user.tenant_id
    assert tenant_id is not None
    response = await service.run_gap_analysis(
        tenant_id=tenant_id,
        regulatory_update_id=regulatory_update_id,
        standard_id=standard_id,
        actor_user_id=current_user.id,
    )
    await db.commit()
    return response


@router.get("/gap-analyses")
async def list_gap_analyses(
    db: DbSession,
    current_user: CurrentUser,
    status: Optional[str] = None,
):
    """List gap analyses."""
    service = ComplianceAutomationService(db)
    tenant_id = current_user.tenant_id
    assert tenant_id is not None
    analyses = await service.get_gap_analyses(tenant_id=tenant_id, status=status)
    return {"analyses": analyses, "total": len(analyses)}


# ============================================================================
# CERTIFICATE TRACKING
# ============================================================================


@router.get("/certificates")
async def list_certificates(
    db: DbSession,
    current_user: CurrentUser,
    certificate_type: Optional[str] = None,
    entity_type: Optional[str] = None,
    status: Optional[str] = None,
    expiring_within_days: Optional[int] = None,
):
    """List certificates with filters."""
    service = ComplianceAutomationService(db)
    tenant_id = current_user.tenant_id
    assert tenant_id is not None
    certificates = await service.get_certificates(
        tenant_id=tenant_id,
        certificate_type=certificate_type,
        entity_type=entity_type,
        status=status,
        expiring_within_days=expiring_within_days,
    )
    return {"certificates": certificates, "total": len(certificates)}


@router.get("/certificates/expiring-summary")
async def get_expiring_certificates_summary(db: DbSession, current_user: CurrentUser):
    """Get summary of expiring certificates."""
    service = ComplianceAutomationService(db)
    tenant_id = current_user.tenant_id
    assert tenant_id is not None
    return await service.get_expiring_certificates_summary(tenant_id=tenant_id)


# ============================================================================
# SCHEDULED AUDITS
# ============================================================================


@router.get("/scheduled-audits")
async def list_scheduled_audits(
    db: DbSession,
    current_user: CurrentUser,
    upcoming_days: Optional[int] = None,
    overdue: Optional[bool] = None,
):
    """List scheduled audits."""
    service = ComplianceAutomationService(db)
    tenant_id = current_user.tenant_id
    assert tenant_id is not None
    audits = await service.get_scheduled_audits(
        tenant_id=tenant_id,
        upcoming_days=upcoming_days,
        overdue=overdue,
    )
    return {"audits": audits, "total": len(audits)}


# ============================================================================
# COMPLIANCE SCORING
# ============================================================================


@router.get("/score")
async def get_compliance_score(
    db: DbSession,
    current_user: CurrentUser,
    scope_type: str = "organization",
    scope_id: Optional[str] = None,
):
    """Calculate current compliance score."""
    service = ComplianceAutomationService(db)
    tenant_id = current_user.tenant_id
    assert tenant_id is not None
    return await service.calculate_compliance_score(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
    )


@router.get("/score/trend")
async def get_compliance_trend(
    db: DbSession,
    current_user: CurrentUser,
    scope_type: str = "organization",
    months: int = 12,
):
    """Get compliance score trend over time."""
    service = ComplianceAutomationService(db)
    tenant_id = current_user.tenant_id
    assert tenant_id is not None
    trend = await service.get_compliance_trend(
        tenant_id=tenant_id,
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
    db: DbSession,
    current_user: CurrentUser,
):
    """Check if incident requires RIDDOR reporting."""
    service = ComplianceAutomationService(db)
    return service.check_riddor_required(incident_data)


@router.post("/riddor/prepare/{incident_id}")
async def prepare_riddor_submission(
    incident_id: int,
    riddor_type: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Prepare RIDDOR submission data."""
    service = ComplianceAutomationService(db)
    return service.prepare_riddor_submission(
        incident_id=incident_id,
        riddor_type=riddor_type,
    )


@router.post("/riddor/submit/{incident_id}")
async def submit_riddor(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Submit RIDDOR report to HSE."""
    service = ComplianceAutomationService(db)
    return service.submit_riddor(
        incident_id=incident_id,
        submitted_by=current_user.id,
    )
