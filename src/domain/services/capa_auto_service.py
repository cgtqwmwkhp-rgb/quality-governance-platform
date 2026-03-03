"""Automatic CAPA generation from assessment and induction outcomes.

When an assessment fails or an induction has "Not Yet Competent" items,
this service auto-creates CAPA actions linked to the source run.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.capa import (
    CAPAAction,
    CAPAPriority,
    CAPASource,
    CAPAStatus,
    CAPAType,
)
from src.domain.services.reference_number import ReferenceNumberService

logger = logging.getLogger(__name__)


class CAPAAutoService:
    """Automatically generates CAPA actions from WDP outcomes."""

    @staticmethod
    async def create_from_assessment(
        db: AsyncSession,
        assessment_run_id: str,
        engineer_id: int,
        supervisor_id: int,
        outcome: str,
        failed_questions: list,
        tenant_id: Optional[int] = None,
    ) -> list:
        """Create CAPA actions from a failed or conditional assessment.

        Args:
            failed_questions: List of dicts with keys: question_id, question_text, criticality, feedback
        """
        if outcome == "pass":
            return []

        created = []
        for fq in failed_questions:
            criticality = fq.get("criticality", "good_to_have")
            priority = CAPAPriority.CRITICAL if criticality == "essential" else CAPAPriority.HIGH

            due_days = 7 if criticality == "essential" else 30
            due_date = datetime.now(timezone.utc) + timedelta(days=due_days)

            ref = await ReferenceNumberService.generate(db, "capa", CAPAAction)
            capa = CAPAAction(
                reference_number=ref,
                title=f"Competency Gap: {fq.get('question_text', 'Unknown')[:200]}",
                description=(
                    f"Engineer (ID: {engineer_id}) was assessed as NOT COMPETENT on this skill.\n\n"
                    f"Question: {fq.get('question_text', 'N/A')}\n"
                    f"Criticality: {criticality}\n"
                    f"Supervisor Feedback: {fq.get('feedback', 'None provided')}\n\n"
                    f"Assessment Reference: {assessment_run_id}"
                ),
                capa_type=CAPAType.CORRECTIVE,
                status=CAPAStatus.OPEN,
                source_type=CAPASource.JOB_ASSESSMENT,
                source_id=None,
                source_reference=assessment_run_id,
                priority=priority,
                assigned_to_id=supervisor_id,
                created_by_id=supervisor_id,
                due_date=due_date,
                tenant_id=tenant_id,
            )
            db.add(capa)
            created.append(capa)
            logger.info(
                "CAPA created for assessment %s, question %s",
                assessment_run_id,
                fq.get("question_id"),
            )

        return created

    @staticmethod
    async def create_from_induction(
        db: AsyncSession,
        induction_run_id: str,
        engineer_id: int,
        supervisor_id: int,
        not_competent_items: list,
        tenant_id: Optional[int] = None,
    ) -> list:
        """Create CAPA actions from induction items marked Not Yet Competent.

        Args:
            not_competent_items: List of dicts with keys: question_id, question_text, supervisor_notes
        """
        if not not_competent_items:
            return []

        created = []
        for item in not_competent_items:
            ref = await ReferenceNumberService.generate(db, "capa", CAPAAction)
            capa = CAPAAction(
                reference_number=ref,
                title=f"Training Gap: {item.get('question_text', 'Unknown')[:200]}",
                description=(
                    f"Engineer (ID: {engineer_id}) marked as NOT YET COMPETENT during induction.\n\n"
                    f"Skill: {item.get('question_text', 'N/A')}\n"
                    f"Supervisor Notes: {item.get('supervisor_notes', 'None provided')}\n\n"
                    f"Induction Reference: {induction_run_id}\n"
                    f"Required: Follow-up training and reassessment."
                ),
                capa_type=CAPAType.CORRECTIVE,
                status=CAPAStatus.OPEN,
                source_type=CAPASource.INDUCTION,
                source_id=None,
                source_reference=induction_run_id,
                priority=CAPAPriority.HIGH,
                assigned_to_id=supervisor_id,
                created_by_id=supervisor_id,
                due_date=datetime.now(timezone.utc) + timedelta(days=14),
                tenant_id=tenant_id,
            )
            db.add(capa)
            created.append(capa)
            logger.info(
                "CAPA created for induction %s, item %s",
                induction_run_id,
                item.get("question_id"),
            )

        return created

    @staticmethod
    async def create_from_loler(
        db: AsyncSession,
        examination_id: int,
        defects: list,
        created_by_id: int,
        tenant_id: Optional[int] = None,
    ) -> list:
        """Create CAPA actions from LOLER defects."""
        created = []
        for defect in defects:
            cat = defect.get("category", "cat_c")
            priority_map = {
                "cat_a": CAPAPriority.CRITICAL,
                "cat_b": CAPAPriority.HIGH,
                "cat_c": CAPAPriority.MEDIUM,
            }
            due_map = {"cat_a": 0, "cat_b": 14, "cat_c": 30}

            ref = await ReferenceNumberService.generate(db, "capa", CAPAAction)
            capa = CAPAAction(
                reference_number=ref,
                title=f"LOLER Defect: {defect.get('description', 'Unknown')[:200]}",
                description=(
                    f"Defect found during LOLER thorough examination (ID: {examination_id}).\n\n"
                    f"Category: {cat.upper()}\n"
                    f"Description: {defect.get('description', 'N/A')}\n"
                    f"Location: {defect.get('location_on_equipment', 'N/A')}\n"
                    f"Remedial Action: {defect.get('remedial_action', 'N/A')}"
                ),
                capa_type=CAPAType.CORRECTIVE,
                status=CAPAStatus.OPEN,
                source_type=CAPASource.LOLER_EXAMINATION,
                source_id=examination_id,
                source_reference=str(examination_id),
                priority=priority_map.get(cat, CAPAPriority.MEDIUM),
                created_by_id=created_by_id,
                due_date=datetime.now(timezone.utc) + timedelta(days=due_map.get(cat, 30)),
                tenant_id=tenant_id,
            )
            db.add(capa)
            created.append(capa)

        return created
