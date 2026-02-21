"""KRI (Key Risk Indicator) API Routes.

Provides CRUD operations for KRIs, measurements, alerts,
and risk score tracking.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.api.schemas.kri import (
    KRIAlertListResponse,
    KRIAlertResponse,
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
from src.domain.models.incident import Incident
from src.domain.models.kri import KeyRiskIndicator, KRIAlert, KRIMeasurement, RiskScoreHistory
from src.domain.services.risk_scoring import KRIService, RiskScoringService

router = APIRouter(prefix="/kri", tags=["Key Risk Indicators"])


# =============================================================================
# KRI CRUD Operations
# =============================================================================


@router.get("", response_model=KRIListResponse)
async def list_kris(
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    status: Optional[str] = Query(None, description="Filter by current status"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all KRIs with optional filtering."""
    query = select(KeyRiskIndicator)

    filters = []
    if category:
        filters.append(KeyRiskIndicator.category == category)
    if is_active is not None:
        filters.append(KeyRiskIndicator.is_active == is_active)
    if status:
        filters.append(KeyRiskIndicator.current_status == status)

    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(KeyRiskIndicator.category, KeyRiskIndicator.code)

    result = await db.execute(query)
    kris = result.scalars().all()

    return KRIListResponse(
        items=[KRIResponse.from_orm(k) for k in kris],
        total=len(kris),
    )


@router.post("", response_model=KRIResponse, status_code=status.HTTP_201_CREATED)
async def create_kri(
    kri_data: KRICreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new KRI."""
    # Check for duplicate code
    existing = await db.execute(select(KeyRiskIndicator).where(KeyRiskIndicator.code == kri_data.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="KRI code already exists")

    kri = KeyRiskIndicator(
        **kri_data.dict(),
        created_by=current_user.get("email"),
    )
    db.add(kri)
    await db.commit()
    await db.refresh(kri)

    return KRIResponse.from_orm(kri)


@router.get("/dashboard", response_model=KRIDashboardResponse)
async def get_kri_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get KRI dashboard summary."""
    kri_service = KRIService(db)
    return await kri_service.get_kri_dashboard()


@router.post("/calculate-all")
async def calculate_all_kris(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
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
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a specific KRI."""
    result = await db.execute(select(KeyRiskIndicator).where(KeyRiskIndicator.id == kri_id))
    kri = result.scalar_one_or_none()

    if not kri:
        raise HTTPException(status_code=404, detail="KRI not found")

    return KRIResponse.from_orm(kri)


@router.patch("/{kri_id}", response_model=KRIResponse)
async def update_kri(
    kri_id: int,
    kri_data: KRIUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a KRI."""
    result = await db.execute(select(KeyRiskIndicator).where(KeyRiskIndicator.id == kri_id))
    kri = result.scalar_one_or_none()

    if not kri:
        raise HTTPException(status_code=404, detail="KRI not found")

    update_data = kri_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(kri, field, value)

    kri.updated_by = current_user.get("email")

    await db.commit()
    await db.refresh(kri)

    return KRIResponse.from_orm(kri)


@router.delete("/{kri_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kri(
    kri_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a KRI."""
    result = await db.execute(select(KeyRiskIndicator).where(KeyRiskIndicator.id == kri_id))
    kri = result.scalar_one_or_none()

    if not kri:
        raise HTTPException(status_code=404, detail="KRI not found")

    await db.delete(kri)
    await db.commit()


@router.post("/{kri_id}/calculate")
async def calculate_kri(
    kri_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Trigger calculation for a specific KRI."""
    kri_service = KRIService(db)
    result = await kri_service.calculate_kri(kri_id)

    if not result:
        raise HTTPException(status_code=400, detail="Could not calculate KRI")

    return result


# =============================================================================
# KRI Measurements
# =============================================================================


@router.get("/{kri_id}/measurements", response_model=KRIMeasurementListResponse)
async def get_kri_measurements(
    kri_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get measurement history for a KRI."""
    result = await db.execute(
        select(KRIMeasurement)
        .where(KRIMeasurement.kri_id == kri_id)
        .order_by(KRIMeasurement.measurement_date.desc())
        .limit(limit)
    )
    measurements = result.scalars().all()

    return KRIMeasurementListResponse(
        items=[KRIMeasurementResponse.from_orm(m) for m in measurements],
        total=len(measurements),
    )


# =============================================================================
# KRI Alerts
# =============================================================================


@router.get("/alerts/pending", response_model=KRIAlertListResponse)
async def get_pending_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get pending (unacknowledged) KRI alerts."""
    result = await db.execute(
        select(KRIAlert)
        .where(
            and_(
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


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Acknowledge a KRI alert."""
    result = await db.execute(select(KRIAlert).where(KRIAlert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.is_acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by_id = current_user.get("id")
    alert.acknowledgment_notes = notes

    await db.commit()

    return {"message": "Alert acknowledged", "alert_id": alert_id}


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Resolve a KRI alert."""
    result = await db.execute(select(KRIAlert).where(KRIAlert.id == alert_id))
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by_id = current_user.get("id")
    alert.resolution_notes = notes

    await db.commit()

    return {"message": "Alert resolved", "alert_id": alert_id}


# =============================================================================
# Risk Score History
# =============================================================================


@router.get("/risks/{risk_id}/trend", response_model=RiskTrendResponse)
async def get_risk_trend(
    risk_id: int,
    days: int = Query(90, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
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
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Assess an incident for SIF/pSIF classification."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Update SIF fields
    incident.is_sif = assessment.is_sif
    incident.is_psif = assessment.is_psif
    incident.sif_classification = assessment.sif_classification
    incident.sif_assessment_date = datetime.utcnow()
    incident.sif_assessed_by_id = current_user.get("id")
    incident.sif_rationale = assessment.sif_rationale
    incident.life_altering_potential = assessment.life_altering_potential
    incident.precursor_events = assessment.precursor_events
    incident.control_failures = assessment.control_failures

    # If SIF or pSIF, trigger risk score update
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
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get SIF assessment for an incident."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if not incident.sif_classification:
        raise HTTPException(status_code=404, detail="No SIF assessment found for this incident")

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
