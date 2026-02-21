"""KRI (Key Risk Indicator) API Routes.

Provides CRUD operations for KRIs, measurements, alerts,
and risk score tracking.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.kri import (
    KRIAlertActionResponse,
    KRIAlertListResponse,
    KRIAlertResponse,
    KRICalculateAllResponse,
    KRICalculateResponse,
    KRICreate,
    KRIDashboardResponse,
    KRIListResponse,
    KRIMeasurementListResponse,
    KRIMeasurementResponse,
    KRIResponse,
    KRIUpdate,
    RiskScoreHistoryResponse,
    RiskTrendResponse,
    SIFAssessmentCreate,
    SIFAssessmentResponse,
)
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.incident import Incident
from src.domain.models.kri import KeyRiskIndicator, KRIAlert, KRIMeasurement, RiskScoreHistory
from src.domain.services.kri_calculation_service import KRICalculationService
from src.domain.services.risk_scoring import KRIService, RiskScoringService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

try:
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter(prefix="/kri", tags=["Key Risk Indicators"])


# =============================================================================
# KRI CRUD Operations
# =============================================================================


@router.get("", response_model=KRIListResponse)
async def list_kris(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    kri_status: Optional[str] = Query(None, alias="status", description="Filter by current status"),
):
    """List all KRIs with optional filtering."""
    query = select(KeyRiskIndicator).options(
        selectinload(KeyRiskIndicator.measurements),
        selectinload(KeyRiskIndicator.alerts),
    ).where(KeyRiskIndicator.tenant_id == current_user.tenant_id)

    filters = []
    if category:
        filters.append(KeyRiskIndicator.category == category)
    if is_active is not None:
        filters.append(KeyRiskIndicator.is_active == is_active)
    if kri_status:
        filters.append(KeyRiskIndicator.current_status == kri_status)

    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(KeyRiskIndicator.category, KeyRiskIndicator.code)

    return await paginate(db, query, params)


@router.post("", response_model=KRIResponse, status_code=status.HTTP_201_CREATED)
async def create_kri(
    kri_data: KRICreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new KRI."""
    _span = tracer.start_span("create_kri") if tracer else None
    existing = await db.execute(
        select(KeyRiskIndicator).where(
            KeyRiskIndicator.tenant_id == current_user.tenant_id,
            KeyRiskIndicator.code == kri_data.code,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.DUPLICATE_ENTITY)

    kri = KeyRiskIndicator(
        **kri_data.dict(),
        tenant_id=current_user.tenant_id,
        created_by=current_user.email,
    )
    db.add(kri)
    await db.commit()
    await db.refresh(kri)
    await invalidate_tenant_cache(current_user.tenant_id, "kri")
    track_metric("kri.mutation", 1)
    track_metric("kri.created", 1)

    if _span:
        _span.end()
    return KRIResponse.from_orm(kri)


@router.get("/dashboard", response_model=KRIDashboardResponse)
async def get_kri_dashboard(
    db: DbSession,
    current_user: CurrentUser,
):
    """Get KRI dashboard summary."""
    kri_service = KRIService(db)
    return await kri_service.get_kri_dashboard()


@router.post("/calculate-all", response_model=KRICalculateAllResponse)
async def calculate_all_kris(
    db: DbSession,
    current_user: CurrentUser,
):
    """Trigger calculation for all auto-calculate KRIs."""
    kri_service = KRIService(db)
    results = await kri_service.calculate_all_kris()

    return {
        "message": "KRI calculations completed",
        "calculated": len(results),
        "results": results,
    }


@router.get("/{kri_id}", response_model=KRIResponse)
async def get_kri(
    kri_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a specific KRI."""
    kri = await get_or_404(db, KeyRiskIndicator, kri_id, detail=ErrorCode.ENTITY_NOT_FOUND, tenant_id=current_user.tenant_id)
    return KRIResponse.from_orm(kri)


@router.patch("/{kri_id}", response_model=KRIResponse)
async def update_kri(
    kri_id: int,
    kri_data: KRIUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update a KRI."""
    kri = await get_or_404(db, KeyRiskIndicator, kri_id, detail=ErrorCode.ENTITY_NOT_FOUND, tenant_id=current_user.tenant_id)
    apply_updates(kri, kri_data, set_updated_at=False)
    kri.updated_by = current_user.email

    await db.commit()
    await db.refresh(kri)
    await invalidate_tenant_cache(current_user.tenant_id, "kri")
    track_metric("kri.mutation", 1)

    return KRIResponse.from_orm(kri)


@router.delete("/{kri_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kri(
    kri_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
):
    """Delete a KRI (superuser only)."""
    kri = await get_or_404(db, KeyRiskIndicator, kri_id, detail=ErrorCode.ENTITY_NOT_FOUND, tenant_id=current_user.tenant_id)
    await db.delete(kri)
    await db.commit()
    await invalidate_tenant_cache(current_user.tenant_id, "kri")
    track_metric("kri.mutation", 1)


@router.post("/{kri_id}/calculate", response_model=KRICalculateResponse)
async def calculate_kri(
    kri_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Trigger calculation for a specific KRI."""
    await get_or_404(db, KeyRiskIndicator, kri_id, detail=ErrorCode.ENTITY_NOT_FOUND, tenant_id=current_user.tenant_id)
    kri_service = KRIService(db)
    result = await kri_service.calculate_kri(kri_id)

    if not result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.VALIDATION_ERROR)

    return result


# =============================================================================
# KRI Measurements
# =============================================================================


@router.get("/{kri_id}/measurements", response_model=KRIMeasurementListResponse)
async def get_kri_measurements(
    kri_id: int,
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
):
    """Get measurement history for a KRI."""
    await get_or_404(db, KeyRiskIndicator, kri_id, detail=ErrorCode.ENTITY_NOT_FOUND, tenant_id=current_user.tenant_id)

    query = (
        select(KRIMeasurement)
        .where(KRIMeasurement.kri_id == kri_id)
        .order_by(KRIMeasurement.measurement_date.desc())
    )

    return await paginate(db, query, params)


# =============================================================================
# KRI Alerts
# =============================================================================


@router.get("/alerts/pending", response_model=KRIAlertListResponse)
async def get_pending_alerts(
    db: DbSession,
    current_user: CurrentUser,
):
    """Get pending (unacknowledged) KRI alerts."""
    result = await db.execute(
        select(KRIAlert)
        .where(
            and_(
                KRIAlert.tenant_id == current_user.tenant_id,
                KRIAlert.is_acknowledged == False,
                KRIAlert.is_resolved == False,
            )
        )
        .order_by(KRIAlert.triggered_at.desc())
    )
    alerts = result.scalars().all()

    return KRIAlertListResponse(
        items=[KRIAlertResponse.from_orm(a) for a in alerts],
        total=len(alerts),
    )


@router.post("/alerts/{alert_id}/acknowledge", response_model=KRIAlertActionResponse)
async def acknowledge_alert(
    alert_id: int,
    db: DbSession,
    current_user: CurrentUser,
    notes: Optional[str] = None,
):
    """Acknowledge a KRI alert."""
    alert = await get_or_404(db, KRIAlert, alert_id, detail=ErrorCode.ENTITY_NOT_FOUND, tenant_id=current_user.tenant_id)

    alert.is_acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by_id = current_user.id
    alert.acknowledgment_notes = notes

    await db.commit()

    return {"message": "Alert acknowledged", "alert_id": alert_id}


@router.post("/alerts/{alert_id}/resolve", response_model=KRIAlertActionResponse)
async def resolve_alert(
    alert_id: int,
    db: DbSession,
    current_user: CurrentUser,
    notes: Optional[str] = None,
):
    """Resolve a KRI alert."""
    alert = await get_or_404(db, KRIAlert, alert_id, detail=ErrorCode.ENTITY_NOT_FOUND, tenant_id=current_user.tenant_id)

    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by_id = current_user.id
    alert.resolution_notes = notes

    await db.commit()

    return {"message": "Alert resolved", "alert_id": alert_id}


# =============================================================================
# Risk Score History
# =============================================================================


@router.get("/risks/{risk_id}/trend", response_model=RiskTrendResponse)
async def get_risk_trend(
    risk_id: int,
    db: DbSession,
    current_user: CurrentUser,
    days: int = Query(90, ge=7, le=365),
):
    """Get risk score trend over time."""
    scoring_service = RiskScoringService(db)
    trend_data = await scoring_service.get_risk_trend(risk_id, days)

    return RiskTrendResponse(
        risk_id=risk_id,
        trend_data=trend_data,
    )


# =============================================================================
# SIF Classification
# =============================================================================


@router.post("/incidents/{incident_id}/sif-assessment", response_model=SIFAssessmentResponse)
async def assess_incident_sif(
    incident_id: int,
    assessment: SIFAssessmentCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Assess an incident for SIF/pSIF classification."""
    incident = await get_or_404(db, Incident, incident_id, detail=ErrorCode.ENTITY_NOT_FOUND, tenant_id=current_user.tenant_id)

    KRICalculationService.apply_sif_assessment(incident, assessment, current_user.id)

    if assessment.is_sif or assessment.is_psif:
        scoring_service = RiskScoringService(db)
        await scoring_service.recalculate_risk_score_for_incident(incident_id, trigger_type="sif_assessment")

    await db.commit()
    await db.refresh(incident)

    return SIFAssessmentResponse(
        incident_id=incident.id,
        is_sif=incident.is_sif,
        is_psif=incident.is_psif,
        sif_classification=incident.sif_classification,
        sif_assessment_date=incident.sif_assessment_date,
        sif_assessed_by_id=incident.sif_assessed_by_id,
        sif_rationale=incident.sif_rationale,
        life_altering_potential=incident.life_altering_potential,
        precursor_events=incident.precursor_events,
        control_failures=incident.control_failures,
    )


@router.get("/incidents/{incident_id}/sif-assessment", response_model=SIFAssessmentResponse)
async def get_incident_sif_assessment(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get SIF assessment for an incident."""
    incident = await get_or_404(db, Incident, incident_id, detail=ErrorCode.ENTITY_NOT_FOUND, tenant_id=current_user.tenant_id)

    if not incident.sif_classification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    return SIFAssessmentResponse(
        incident_id=incident.id,
        is_sif=incident.is_sif or False,
        is_psif=incident.is_psif or False,
        sif_classification=incident.sif_classification,
        sif_assessment_date=incident.sif_assessment_date,
        sif_assessed_by_id=incident.sif_assessed_by_id,
        sif_rationale=incident.sif_rationale,
        life_altering_potential=incident.life_altering_potential or False,
        precursor_events=incident.precursor_events,
        control_failures=incident.control_failures,
    )
