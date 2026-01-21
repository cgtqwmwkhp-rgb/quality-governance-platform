"""Auditor Competence Management Service.

Provides services for managing auditor qualifications,
competencies, and skill-based assignment.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.auditor_competence import (
    AuditAssignmentCriteria,
    AuditorCertification,
    AuditorCompetency,
    AuditorProfile,
    AuditorTraining,
    CertificationStatus,
    CompetenceLevel,
    CompetencyArea,
)

logger = logging.getLogger(__name__)


class AuditorCompetenceService:
    """Service for managing auditor competence."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # =============================================================================
    # PROFILE MANAGEMENT
    # =============================================================================
    
    async def create_profile(
        self,
        user_id: int,
        job_title: Optional[str] = None,
        department: Optional[str] = None,
        years_experience: float = 0,
    ) -> AuditorProfile:
        """Create an auditor profile for a user."""
        profile = AuditorProfile(
            user_id=user_id,
            job_title=job_title,
            department=department,
            years_audit_experience=years_experience,
            competence_level=CompetenceLevel.TRAINEE,
            is_active=True,
        )
        self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(profile)
        return profile
    
    async def get_profile(self, user_id: int) -> Optional[AuditorProfile]:
        """Get auditor profile by user ID."""
        result = await self.db.execute(
            select(AuditorProfile).where(AuditorProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def update_profile(
        self,
        user_id: int,
        **updates,
    ) -> Optional[AuditorProfile]:
        """Update auditor profile."""
        profile = await self.get_profile(user_id)
        if not profile:
            return None
        
        for field, value in updates.items():
            if hasattr(profile, field):
                setattr(profile, field, value)
        
        await self.db.commit()
        await self.db.refresh(profile)
        return profile
    
    async def calculate_competence_score(self, user_id: int) -> float:
        """Calculate overall competence score for an auditor."""
        profile = await self.get_profile(user_id)
        if not profile:
            return 0.0
        
        # Get all competencies with their areas
        result = await self.db.execute(
            select(AuditorCompetency).where(
                AuditorCompetency.profile_id == profile.id
            )
        )
        competencies = result.scalars().all()
        
        if not competencies:
            return 0.0
        
        # Get competency areas for weights
        area_result = await self.db.execute(select(CompetencyArea))
        areas = {a.id: a for a in area_result.scalars().all()}
        
        total_weighted_score = 0
        total_weight = 0
        
        for comp in competencies:
            area = areas.get(comp.competency_area_id)
            if not area:
                continue
            
            # Score is current level / max level (5) * 100
            score = (comp.current_level / 5) * 100
            weight = area.weight
            
            total_weighted_score += score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        final_score = total_weighted_score / total_weight
        
        # Update profile
        profile.competence_score = final_score
        await self.db.commit()
        
        return final_score
    
    # =============================================================================
    # CERTIFICATION MANAGEMENT
    # =============================================================================
    
    async def add_certification(
        self,
        user_id: int,
        certification_name: str,
        certification_body: str,
        issued_date: datetime,
        expiry_date: Optional[datetime] = None,
        certification_number: Optional[str] = None,
        standard_code: Optional[str] = None,
        certification_level: Optional[str] = None,
    ) -> AuditorCertification:
        """Add a certification to an auditor."""
        profile = await self.get_profile(user_id)
        if not profile:
            raise ValueError(f"No auditor profile found for user {user_id}")
        
        cert = AuditorCertification(
            profile_id=profile.id,
            certification_name=certification_name,
            certification_body=certification_body,
            certification_number=certification_number,
            standard_code=standard_code,
            certification_level=certification_level,
            issued_date=issued_date,
            expiry_date=expiry_date,
            status=CertificationStatus.ACTIVE,
        )
        self.db.add(cert)
        await self.db.commit()
        await self.db.refresh(cert)
        return cert
    
    async def get_certifications(self, user_id: int) -> List[AuditorCertification]:
        """Get all certifications for an auditor."""
        profile = await self.get_profile(user_id)
        if not profile:
            return []
        
        result = await self.db.execute(
            select(AuditorCertification).where(
                AuditorCertification.profile_id == profile.id
            ).order_by(AuditorCertification.expiry_date)
        )
        return list(result.scalars().all())
    
    async def get_expiring_certifications(
        self,
        days_ahead: int = 90,
    ) -> List[Dict[str, Any]]:
        """Get certifications expiring within specified days."""
        cutoff = datetime.utcnow() + timedelta(days=days_ahead)
        
        result = await self.db.execute(
            select(AuditorCertification).where(
                and_(
                    AuditorCertification.expiry_date <= cutoff,
                    AuditorCertification.status == CertificationStatus.ACTIVE,
                )
            ).order_by(AuditorCertification.expiry_date)
        )
        certs = result.scalars().all()
        
        expiring = []
        for cert in certs:
            expiring.append({
                "certification_id": cert.id,
                "certification_name": cert.certification_name,
                "profile_id": cert.profile_id,
                "expiry_date": cert.expiry_date,
                "days_until_expiry": cert.days_until_expiry,
            })
        
        return expiring
    
    async def update_expired_certifications(self) -> int:
        """Update status of expired certifications."""
        now = datetime.utcnow()
        
        result = await self.db.execute(
            select(AuditorCertification).where(
                and_(
                    AuditorCertification.expiry_date < now,
                    AuditorCertification.status == CertificationStatus.ACTIVE,
                )
            )
        )
        expired = result.scalars().all()
        
        for cert in expired:
            cert.status = CertificationStatus.EXPIRED
        
        if expired:
            await self.db.commit()
        
        return len(expired)
    
    # =============================================================================
    # TRAINING MANAGEMENT
    # =============================================================================
    
    async def add_training(
        self,
        user_id: int,
        training_name: str,
        start_date: datetime,
        training_type: str = "course",
        training_provider: Optional[str] = None,
        duration_hours: Optional[float] = None,
    ) -> AuditorTraining:
        """Add a training record for an auditor."""
        profile = await self.get_profile(user_id)
        if not profile:
            raise ValueError(f"No auditor profile found for user {user_id}")
        
        training = AuditorTraining(
            profile_id=profile.id,
            training_name=training_name,
            training_type=training_type,
            training_provider=training_provider,
            start_date=start_date,
            duration_hours=duration_hours,
        )
        self.db.add(training)
        await self.db.commit()
        await self.db.refresh(training)
        return training
    
    async def complete_training(
        self,
        training_id: int,
        completion_date: datetime,
        assessment_passed: Optional[bool] = None,
        assessment_score: Optional[float] = None,
        cpd_hours_earned: Optional[float] = None,
    ) -> AuditorTraining:
        """Mark a training as completed."""
        result = await self.db.execute(
            select(AuditorTraining).where(AuditorTraining.id == training_id)
        )
        training = result.scalar_one_or_none()
        
        if not training:
            raise ValueError(f"Training {training_id} not found")
        
        training.completed = True
        training.completion_date = completion_date
        training.assessment_passed = assessment_passed
        training.assessment_score = assessment_score
        training.cpd_hours_earned = cpd_hours_earned
        
        await self.db.commit()
        await self.db.refresh(training)
        
        # Update CPD hours on certifications if applicable
        if cpd_hours_earned:
            await self._update_cpd_hours(training.profile_id, cpd_hours_earned)
        
        return training
    
    async def _update_cpd_hours(self, profile_id: int, hours: float) -> None:
        """Update CPD hours on active certifications."""
        result = await self.db.execute(
            select(AuditorCertification).where(
                and_(
                    AuditorCertification.profile_id == profile_id,
                    AuditorCertification.status == CertificationStatus.ACTIVE,
                    AuditorCertification.cpd_hours_required.isnot(None),
                )
            )
        )
        certs = result.scalars().all()
        
        for cert in certs:
            cert.cpd_hours_completed += hours
        
        await self.db.commit()
    
    # =============================================================================
    # COMPETENCY ASSESSMENT
    # =============================================================================
    
    async def assess_competency(
        self,
        user_id: int,
        competency_area_id: int,
        current_level: int,
        assessor_id: int,
        assessment_method: str = "supervisor",
        evidence_summary: Optional[str] = None,
    ) -> AuditorCompetency:
        """Record a competency assessment."""
        profile = await self.get_profile(user_id)
        if not profile:
            raise ValueError(f"No auditor profile found for user {user_id}")
        
        # Check if competency record exists
        result = await self.db.execute(
            select(AuditorCompetency).where(
                and_(
                    AuditorCompetency.profile_id == profile.id,
                    AuditorCompetency.competency_area_id == competency_area_id,
                )
            )
        )
        competency = result.scalar_one_or_none()
        
        if competency:
            competency.current_level = current_level
            competency.last_assessed = datetime.utcnow()
            competency.assessed_by_id = assessor_id
            competency.assessment_method = assessment_method
            competency.evidence_summary = evidence_summary
        else:
            competency = AuditorCompetency(
                profile_id=profile.id,
                competency_area_id=competency_area_id,
                current_level=current_level,
                last_assessed=datetime.utcnow(),
                assessed_by_id=assessor_id,
                assessment_method=assessment_method,
                evidence_summary=evidence_summary,
            )
            self.db.add(competency)
        
        await self.db.commit()
        await self.db.refresh(competency)
        
        # Recalculate overall score
        await self.calculate_competence_score(user_id)
        
        return competency
    
    async def get_competency_gaps(self, user_id: int) -> List[Dict[str, Any]]:
        """Identify competency gaps for an auditor."""
        profile = await self.get_profile(user_id)
        if not profile:
            return []
        
        # Get required levels for current competence level
        level_key = profile.competence_level.value
        
        # Get all competency areas
        area_result = await self.db.execute(
            select(CompetencyArea).where(CompetencyArea.is_active == True)
        )
        areas = area_result.scalars().all()
        
        # Get current competencies
        comp_result = await self.db.execute(
            select(AuditorCompetency).where(
                AuditorCompetency.profile_id == profile.id
            )
        )
        competencies = {c.competency_area_id: c for c in comp_result.scalars().all()}
        
        gaps = []
        for area in areas:
            required_level = area.required_levels.get(level_key, 1)
            current = competencies.get(area.id)
            current_level = current.current_level if current else 0
            
            if current_level < required_level:
                gaps.append({
                    "competency_area_id": area.id,
                    "competency_area_code": area.code,
                    "competency_area_name": area.name,
                    "category": area.category,
                    "required_level": required_level,
                    "current_level": current_level,
                    "gap": required_level - current_level,
                })
        
        return gaps
    
    # =============================================================================
    # AUDITOR ASSIGNMENT
    # =============================================================================
    
    async def find_qualified_auditors(
        self,
        audit_type: str,
    ) -> List[Dict[str, Any]]:
        """Find auditors qualified for a specific audit type."""
        # Get assignment criteria
        criteria_result = await self.db.execute(
            select(AuditAssignmentCriteria).where(
                and_(
                    AuditAssignmentCriteria.audit_type == audit_type,
                    AuditAssignmentCriteria.is_active == True,
                )
            )
        )
        criteria = criteria_result.scalar_one_or_none()
        
        if not criteria:
            # No specific criteria - return all active auditors
            result = await self.db.execute(
                select(AuditorProfile).where(
                    and_(
                        AuditorProfile.is_active == True,
                        AuditorProfile.is_available == True,
                    )
                )
            )
            profiles = result.scalars().all()
            return [{"profile": p, "qualified": True, "gaps": []} for p in profiles]
        
        # Get all active, available auditors
        result = await self.db.execute(
            select(AuditorProfile).where(
                and_(
                    AuditorProfile.is_active == True,
                    AuditorProfile.is_available == True,
                )
            )
        )
        profiles = result.scalars().all()
        
        qualified_auditors = []
        
        for profile in profiles:
            is_qualified = True
            gaps = []
            
            # Check minimum level
            level_order = [l.value for l in CompetenceLevel]
            profile_level_idx = level_order.index(profile.competence_level.value)
            required_level_idx = level_order.index(criteria.minimum_auditor_level.value)
            
            if profile_level_idx < required_level_idx:
                is_qualified = False
                gaps.append(f"Requires {criteria.minimum_auditor_level.value} level")
            
            # Check experience
            if profile.total_audits_conducted < criteria.minimum_audits_conducted:
                is_qualified = False
                gaps.append(f"Requires {criteria.minimum_audits_conducted} audits conducted")
            
            if (profile.years_audit_experience or 0) < criteria.minimum_years_experience:
                is_qualified = False
                gaps.append(f"Requires {criteria.minimum_years_experience} years experience")
            
            # Check certifications
            if criteria.required_certifications:
                cert_result = await self.db.execute(
                    select(AuditorCertification).where(
                        and_(
                            AuditorCertification.profile_id == profile.id,
                            AuditorCertification.status == CertificationStatus.ACTIVE,
                        )
                    )
                )
                certs = cert_result.scalars().all()
                cert_names = [c.certification_name for c in certs]
                
                for req_cert in criteria.required_certifications:
                    if req_cert not in cert_names:
                        is_qualified = False
                        gaps.append(f"Missing certification: {req_cert}")
            
            qualified_auditors.append({
                "profile_id": profile.id,
                "user_id": profile.user_id,
                "competence_level": profile.competence_level.value,
                "competence_score": profile.competence_score,
                "is_qualified": is_qualified,
                "gaps": gaps,
            })
        
        # Sort by qualification status and score
        qualified_auditors.sort(
            key=lambda x: (not x["is_qualified"], -(x["competence_score"] or 0))
        )
        
        return qualified_auditors
    
    async def get_competence_dashboard(self) -> Dict[str, Any]:
        """Get auditor competence dashboard summary."""
        # Count auditors by level
        level_counts = {}
        for level in CompetenceLevel:
            result = await self.db.execute(
                select(func.count(AuditorProfile.id)).where(
                    and_(
                        AuditorProfile.competence_level == level,
                        AuditorProfile.is_active == True,
                    )
                )
            )
            level_counts[level.value] = result.scalar() or 0
        
        # Count expiring certifications
        expiring = await self.get_expiring_certifications(90)
        
        # Average competence score
        avg_result = await self.db.execute(
            select(func.avg(AuditorProfile.competence_score)).where(
                AuditorProfile.is_active == True
            )
        )
        avg_score = avg_result.scalar() or 0
        
        # Total active auditors
        total_result = await self.db.execute(
            select(func.count(AuditorProfile.id)).where(
                AuditorProfile.is_active == True
            )
        )
        total_active = total_result.scalar() or 0
        
        return {
            "total_active_auditors": total_active,
            "by_level": level_counts,
            "average_competence_score": round(avg_score, 1),
            "certifications_expiring_90_days": len(expiring),
            "expiring_certifications": expiring[:10],  # Top 10
        }
