"""Automatic CAPA generation from assessment, induction and compliance outcomes.

When an assessment fails, an induction has "Not Yet Competent" items, or a
compliance obligation is closed with a failed check, this service auto-creates
CAPA actions linked to the source run or record.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.compliance_schedule import ComplianceRecord, ComplianceRequirement
from src.domain.services.reference_number import ReferenceNumberService

logger = logging.getLogger(__name__)

# ``source_id`` holds the occurrence (the record), because that is what makes one
# failure distinct from the next and is therefore what deduplication has to key
# on. The obligation the failure belongs to is the thing a reader wants to open,
# so it travels in ``source_reference`` as a storage key rather than a display
# string — the same shape as ``investigation:6``, which the Actions surfaces
# already recognise as internal and refuse to print (isInternalSourceReference).
COMPLIANCE_REQUIREMENT_SOURCE_PREFIX = "compliance_requirement"


def compliance_requirement_source_reference(requirement_id: int) -> str:
    """Storage key pointing a compliance CAPA back at its obligation."""
    return f"{COMPLIANCE_REQUIREMENT_SOURCE_PREFIX}:{int(requirement_id)}"


def _naive_utc(value: datetime) -> datetime:
    """Normalise to UTC, then drop the offset.

    ``capa_actions.due_date`` is ``DateTime`` with no ``timezone=True``, so on
    PostgreSQL it is TIMESTAMP WITHOUT TIME ZONE and asyncpg refuses an aware
    datetime for it outright. SQLite accepts either, so a unit run against a
    mocked or SQLite session cannot show the difference — only an integration run
    on PostgreSQL does.

    Converting before stripping matters: dropping the offset off a non-UTC aware
    value would silently store a different instant.
    """
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class CAPAAutoService:
    """Automatically generates CAPA actions from WDP outcomes."""

    @staticmethod
    async def _existing_action(
        db: AsyncSession,
        *,
        source_type: CAPASource,
        source_reference: str,
        source_id: int,
        tenant_id: Optional[int],
    ) -> CAPAAction | None:
        stmt = select(CAPAAction).where(
            CAPAAction.source_type == source_type,
            CAPAAction.source_reference == source_reference,
            CAPAAction.source_id == source_id,
        )
        if tenant_id is None:
            stmt = stmt.where(CAPAAction.tenant_id.is_(None))
        else:
            stmt = stmt.where(CAPAAction.tenant_id == tenant_id)
        return (await db.execute(stmt)).scalar_one_or_none()

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
            question_id = int(fq.get("question_id") or 0)
            if question_id <= 0:
                continue
            existing = await CAPAAutoService._existing_action(
                db,
                source_type=CAPASource.JOB_ASSESSMENT,
                source_reference=assessment_run_id,
                source_id=question_id,
                tenant_id=tenant_id,
            )
            if existing is not None:
                created.append(existing)
                continue
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
                source_id=question_id,
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
            question_id = int(item.get("question_id") or 0)
            if question_id <= 0:
                continue
            existing = await CAPAAutoService._existing_action(
                db,
                source_type=CAPASource.INDUCTION,
                source_reference=induction_run_id,
                source_id=question_id,
                tenant_id=tenant_id,
            )
            if existing is not None:
                created.append(existing)
                continue
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
                source_id=question_id,
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
    async def create_from_compliance_record(
        db: AsyncSession,
        *,
        record: ComplianceRecord,
        requirement: ComplianceRequirement,
        created_by_id: int,
        now: Optional[datetime] = None,
    ) -> CAPAAction:
        """Raise the corrective action owed by a failed compliance check.

        Takes the two rows rather than loose ids so tenancy is derived here from
        the record itself and cross-checked against the obligation, instead of
        being asserted by whichever caller happens to be writing. ``capa_actions``
        is under ``tenant_isolation`` with FORCE, so a wrong tenant id would not
        silently cross customers — it would fail the policy's WITH CHECK and
        abort the completion. Refusing it in this frame says why.

        Idempotent per occurrence: a second call for the same record returns the
        CAPA already raised rather than a duplicate, matching the assessment and
        induction paths.

        Due dates run from wall-clock now, not from ``completed_at``. Historical
        occurrences are entered against past due dates during onboarding, and
        anchoring the CAPA to those would open it already overdue — an artefact
        of when the data was typed rather than a real breach. They are stored
        naive; see :func:`_naive_utc` for why the column leaves no choice.
        """
        tenant_id = record.tenant_id
        if tenant_id is None:
            raise ValueError("compliance record has no tenant; refusing to raise an untenanted CAPA")
        if requirement.tenant_id != tenant_id:
            raise ValueError(
                f"compliance record {record.id} (tenant {tenant_id}) does not belong to "
                f"requirement {requirement.id} (tenant {requirement.tenant_id})"
            )
        if record.requirement_id != requirement.id:
            raise ValueError(
                f"compliance record {record.id} belongs to requirement "
                f"{record.requirement_id}, not {requirement.id}"
            )
        if record.id is None:
            raise ValueError("compliance record must be flushed before a CAPA can reference it")

        source_reference = compliance_requirement_source_reference(requirement.id)
        existing = await CAPAAutoService._existing_action(
            db,
            source_type=CAPASource.COMPLIANCE_RECORD,
            source_reference=source_reference,
            source_id=record.id,
            tenant_id=tenant_id,
        )
        if existing is not None:
            return existing

        statutory = bool(requirement.statutory)
        priority = CAPAPriority.CRITICAL if statutory else CAPAPriority.HIGH
        due_days = 7 if statutory else 30
        clock = now or datetime.now(timezone.utc)

        ref = await ReferenceNumberService.generate(db, "capa", CAPAAction)
        capa = CAPAAction(
            reference_number=ref,
            title=f"Compliance Check Failed: {requirement.title[:200]}",
            description=(
                f"Occurrence of {requirement.reference_number} was closed with a FAILED check.\n\n"
                f"Obligation: {requirement.title}\n"
                f"Occurrence due: {record.due_date.isoformat()}\n"
                f"Statutory: {'yes' if statutory else 'no'}\n"
                f"Notes: {record.notes or 'None provided'}\n\n"
                f"Compliance Record: {record.reference_number}"
            ),
            capa_type=CAPAType.CORRECTIVE,
            status=CAPAStatus.OPEN,
            source_type=CAPASource.COMPLIANCE_RECORD,
            source_id=record.id,
            source_reference=source_reference,
            priority=priority,
            # The obligation owner is already refused unless they belong to this
            # tenant (ComplianceScheduleService._assert_owner_in_tenant), so it is
            # safe to carry through; unowned obligations leave the CAPA
            # unassigned rather than parking it on whoever filed the record.
            assigned_to_id=requirement.owner_id,
            created_by_id=created_by_id,
            due_date=_naive_utc(clock + timedelta(days=due_days)),
            tenant_id=tenant_id,
        )
        db.add(capa)
        logger.info(
            "CAPA created for failed compliance check: record=%s requirement=%s tenant=%s",
            record.reference_number,
            requirement.reference_number,
            tenant_id,
        )
        return capa

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
