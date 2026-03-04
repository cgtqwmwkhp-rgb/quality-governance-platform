"""Auditor Competence API Routes.

Provides endpoints for managing auditor profiles, certifications,
training, and competency assessments.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.services.auditor_competence import AuditorCompetenceService

router = APIRouter(prefix="/auditor-competence", tags=["Auditor Competence"])


# =============================================================================
# SCHEMAS
# =============================================================================


class CreateProfileRequest(BaseModel):
    user_id: int
    job_title: Optional[str] = None
    department: Optional[str] = None
    years_experience: float = 0


class UpdateProfileRequest(BaseModel):
    job_title: Optional[str] = None
    department: Optional[str] = None
    years_audit_experience: Optional[float] = None
    specializations: Optional[List[str]] = None
    industry_experience: Optional[List[str]] = None
    is_available: Optional[bool] = None
    availability_notes: Optional[str] = None


class AddCertificationRequest(BaseModel):
    certification_name: str
    certification_body: str
    issued_date: datetime
    expiry_date: Optional[datetime] = None
    certification_number: Optional[str] = None
    standard_code: Optional[str] = None
    certification_level: Optional[str] = None


class AddTrainingRequest(BaseModel):
    training_name: str
    start_date: datetime
    training_type: str = "course"
    training_provider: Optional[str] = None
    duration_hours: Optional[float] = None


class CompleteTrainingRequest(BaseModel):
    completion_date: datetime
    assessment_passed: Optional[bool] = None
    assessment_score: Optional[float] = None
    cpd_hours_earned: Optional[float] = None


class AssessCompetencyRequest(BaseModel):
    competency_area_id: int
    current_level: int = Field(..., ge=1, le=5)
    assessment_method: str = "supervisor"
    evidence_summary: Optional[str] = None


# =============================================================================
# PROFILE ENDPOINTS
# =============================================================================


@router.post("/profiles", status_code=status.HTTP_201_CREATED)
async def create_auditor_profile(
    request: CreateProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create an auditor profile for a user."""
    service = AuditorCompetenceService(db)
    profile = await service.create_profile(
        user_id=request.user_id,
        job_title=request.job_title,
        department=request.department,
        years_experience=request.years_experience,
    )
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "competence_level": profile.competence_level.value,
        "created_at": profile.created_at,
    }


@router.get("/profiles/{user_id}")
async def get_auditor_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get auditor profile by user ID."""
    service = AuditorCompetenceService(db)
    profile = await service.get_profile(user_id)

    if not profile:
        raise HTTPException(status_code=404, detail="Auditor profile not found")

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "job_title": profile.job_title,
        "department": profile.department,
        "competence_level": profile.competence_level.value,
        "years_audit_experience": profile.years_audit_experience,
        "total_audits_conducted": profile.total_audits_conducted,
        "total_audits_as_lead": profile.total_audits_as_lead,
        "specializations": profile.specializations,
        "competence_score": profile.competence_score,
        "is_available": profile.is_available,
        "is_active": profile.is_active,
    }


@router.patch("/profiles/{user_id}")
async def update_auditor_profile(
    user_id: int,
    request: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update auditor profile."""
    service = AuditorCompetenceService(db)

    updates = request.dict(exclude_unset=True)
    profile = await service.update_profile(user_id, **updates)

    if not profile:
        raise HTTPException(status_code=404, detail="Auditor profile not found")

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "updated": True,
    }


@router.post("/profiles/{user_id}/calculate-score")
async def calculate_competence_score(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Calculate and update competence score for an auditor."""
    service = AuditorCompetenceService(db)
    score = await service.calculate_competence_score(user_id)

    return {
        "user_id": user_id,
        "competence_score": score,
    }


# =============================================================================
# CERTIFICATION ENDPOINTS
# =============================================================================


@router.post("/profiles/{user_id}/certifications", status_code=status.HTTP_201_CREATED)
async def add_certification(
    user_id: int,
    request: AddCertificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add a certification to an auditor."""
    service = AuditorCompetenceService(db)

    try:
        cert = await service.add_certification(
            user_id=user_id,
            certification_name=request.certification_name,
            certification_body=request.certification_body,
            issued_date=request.issued_date,
            expiry_date=request.expiry_date,
            certification_number=request.certification_number,
            standard_code=request.standard_code,
            certification_level=request.certification_level,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "id": cert.id,
        "certification_name": cert.certification_name,
        "status": cert.status.value,
        "expiry_date": cert.expiry_date,
    }


@router.get("/profiles/{user_id}/certifications")
async def get_certifications(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all certifications for an auditor."""
    service = AuditorCompetenceService(db)
    certs = await service.get_certifications(user_id)

    return {
        "user_id": user_id,
        "certifications": [
            {
                "id": c.id,
                "certification_name": c.certification_name,
                "certification_body": c.certification_body,
                "standard_code": c.standard_code,
                "status": c.status.value,
                "issued_date": c.issued_date,
                "expiry_date": c.expiry_date,
                "days_until_expiry": c.days_until_expiry,
                "is_valid": c.is_valid,
            }
            for c in certs
        ],
    }


@router.get("/certifications/expiring")
async def get_expiring_certifications(
    days_ahead: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get certifications expiring within specified days."""
    service = AuditorCompetenceService(db)
    expiring = await service.get_expiring_certifications(days_ahead)

    return {
        "days_ahead": days_ahead,
        "expiring_count": len(expiring),
        "certifications": expiring,
    }


@router.post("/certifications/update-expired")
async def update_expired_certifications(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update status of expired certifications."""
    service = AuditorCompetenceService(db)
    count = await service.update_expired_certifications()

    return {
        "updated_count": count,
        "message": f"{count} certifications marked as expired",
    }


# =============================================================================
# TRAINING ENDPOINTS
# =============================================================================


@router.post("/profiles/{user_id}/training", status_code=status.HTTP_201_CREATED)
async def add_training(
    user_id: int,
    request: AddTrainingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add a training record for an auditor."""
    service = AuditorCompetenceService(db)

    try:
        training = await service.add_training(
            user_id=user_id,
            training_name=request.training_name,
            start_date=request.start_date,
            training_type=request.training_type,
            training_provider=request.training_provider,
            duration_hours=request.duration_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "id": training.id,
        "training_name": training.training_name,
        "completed": training.completed,
    }


@router.post("/training/{training_id}/complete")
async def complete_training(
    training_id: int,
    request: CompleteTrainingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mark a training as completed."""
    service = AuditorCompetenceService(db)

    try:
        training = await service.complete_training(
            training_id=training_id,
            completion_date=request.completion_date,
            assessment_passed=request.assessment_passed,
            assessment_score=request.assessment_score,
            cpd_hours_earned=request.cpd_hours_earned,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "id": training.id,
        "completed": training.completed,
        "completion_date": training.completion_date,
        "assessment_passed": training.assessment_passed,
    }


# =============================================================================
# COMPETENCY ASSESSMENT ENDPOINTS
# =============================================================================


@router.post("/profiles/{user_id}/assess")
async def assess_competency(
    user_id: int,
    request: AssessCompetencyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Record a competency assessment for an auditor."""
    service = AuditorCompetenceService(db)

    try:
        competency = await service.assess_competency(
            user_id=user_id,
            competency_area_id=request.competency_area_id,
            current_level=request.current_level,
            assessor_id=current_user.get("id"),
            assessment_method=request.assessment_method,
            evidence_summary=request.evidence_summary,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "id": competency.id,
        "competency_area_id": competency.competency_area_id,
        "current_level": competency.current_level,
        "last_assessed": competency.last_assessed,
    }


@router.get("/profiles/{user_id}/gaps")
async def get_competency_gaps(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get competency gaps for an auditor."""
    service = AuditorCompetenceService(db)
    gaps = await service.get_competency_gaps(user_id)

    return {
        "user_id": user_id,
        "gap_count": len(gaps),
        "gaps": gaps,
    }


# =============================================================================
# AUDITOR ASSIGNMENT ENDPOINTS
# =============================================================================


@router.get("/find-auditors/{audit_type}")
async def find_qualified_auditors(
    audit_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Find auditors qualified for a specific audit type."""
    service = AuditorCompetenceService(db)
    auditors = await service.find_qualified_auditors(audit_type)

    qualified = [a for a in auditors if a["is_qualified"]]
    not_qualified = [a for a in auditors if not a["is_qualified"]]

    return {
        "audit_type": audit_type,
        "total_auditors": len(auditors),
        "qualified_count": len(qualified),
        "qualified_auditors": qualified,
        "not_qualified_auditors": not_qualified,
    }


# =============================================================================
# DASHBOARD ENDPOINTS
# =============================================================================


@router.get("/dashboard")
async def get_competence_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get auditor competence dashboard summary."""
    service = AuditorCompetenceService(db)
    dashboard = await service.get_competence_dashboard()

    return dashboard
