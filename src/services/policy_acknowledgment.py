"""Policy Acknowledgment Service.

Manages policy acknowledgment requirements, tracking,
reminders, and compliance reporting.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.policy_acknowledgment import (
    AcknowledgmentStatus,
    AcknowledgmentType,
    DocumentReadLog,
    PolicyAcknowledgment,
    PolicyAcknowledgmentRequirement,
)

logger = logging.getLogger(__name__)


class PolicyAcknowledgmentService:
    """Service for managing policy acknowledgments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_requirement(
        self,
        policy_id: int,
        acknowledgment_type: AcknowledgmentType = AcknowledgmentType.READ_ONLY,
        required_for_all: bool = False,
        required_departments: Optional[List[str]] = None,
        required_roles: Optional[List[str]] = None,
        required_user_ids: Optional[List[int]] = None,
        due_within_days: int = 30,
        reminder_days_before: Optional[List[int]] = None,
        quiz_questions: Optional[List[Dict]] = None,
        quiz_passing_score: int = 80,
    ) -> PolicyAcknowledgmentRequirement:
        """Create an acknowledgment requirement for a policy."""
        requirement = PolicyAcknowledgmentRequirement(
            policy_id=policy_id,
            acknowledgment_type=acknowledgment_type,
            required_for_all=required_for_all,
            required_departments=required_departments,
            required_roles=required_roles,
            required_user_ids=required_user_ids,
            due_within_days=due_within_days,
            reminder_days_before=reminder_days_before or [7, 3, 1],
            quiz_questions=quiz_questions,
            quiz_passing_score=quiz_passing_score,
            is_active=True,
        )

        self.db.add(requirement)
        await self.db.commit()
        await self.db.refresh(requirement)

        return requirement

    async def assign_acknowledgments(
        self,
        requirement_id: int,
        user_ids: List[int],
        policy_version: Optional[str] = None,
    ) -> List[PolicyAcknowledgment]:
        """Assign acknowledgment tasks to users."""
        result = await self.db.execute(
            select(PolicyAcknowledgmentRequirement).where(
                PolicyAcknowledgmentRequirement.id == requirement_id
            )
        )
        requirement = result.scalar_one_or_none()

        if not requirement:
            raise ValueError(f"Requirement {requirement_id} not found")

        now = datetime.utcnow()
        due_date = now + timedelta(days=requirement.due_within_days)

        acknowledgments = []
        for user_id in user_ids:
            # Check if already assigned
            existing = await self.db.execute(
                select(PolicyAcknowledgment).where(
                    and_(
                        PolicyAcknowledgment.requirement_id == requirement_id,
                        PolicyAcknowledgment.user_id == user_id,
                        PolicyAcknowledgment.status.in_(
                            [
                                AcknowledgmentStatus.PENDING,
                                AcknowledgmentStatus.OVERDUE,
                            ]
                        ),
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue  # Already has pending assignment

            ack = PolicyAcknowledgment(
                requirement_id=requirement_id,
                policy_id=requirement.policy_id,
                user_id=user_id,
                policy_version=policy_version,
                status=AcknowledgmentStatus.PENDING,
                assigned_at=now,
                due_date=due_date,
            )
            self.db.add(ack)
            acknowledgments.append(ack)

        await self.db.commit()

        for ack in acknowledgments:
            await self.db.refresh(ack)

        return acknowledgments

    async def record_acknowledgment(
        self,
        acknowledgment_id: int,
        quiz_score: Optional[int] = None,
        acceptance_statement: Optional[str] = None,
        signature_data: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PolicyAcknowledgment:
        """Record a user's acknowledgment of a policy."""
        result = await self.db.execute(
            select(PolicyAcknowledgment).where(
                PolicyAcknowledgment.id == acknowledgment_id
            )
        )
        ack = result.scalar_one_or_none()

        if not ack:
            raise ValueError(f"Acknowledgment {acknowledgment_id} not found")

        # Get requirement for quiz validation
        req_result = await self.db.execute(
            select(PolicyAcknowledgmentRequirement).where(
                PolicyAcknowledgmentRequirement.id == ack.requirement_id
            )
        )
        requirement = req_result.scalar_one_or_none()

        # Validate quiz if required
        if requirement and requirement.acknowledgment_type == AcknowledgmentType.QUIZ:
            if quiz_score is None:
                raise ValueError("Quiz score required for quiz-type acknowledgment")

            ack.quiz_score = quiz_score
            ack.quiz_attempts += 1
            ack.quiz_passed = quiz_score >= (requirement.quiz_passing_score or 80)

            if not ack.quiz_passed:
                # Don't complete if quiz failed
                await self.db.commit()
                return ack

        # Record completion
        ack.acknowledged_at = datetime.utcnow()
        ack.status = AcknowledgmentStatus.COMPLETED
        ack.acceptance_statement = acceptance_statement
        ack.signature_data = signature_data
        ack.ip_address = ip_address
        ack.user_agent = user_agent

        await self.db.commit()
        await self.db.refresh(ack)

        return ack

    async def record_policy_opened(
        self,
        acknowledgment_id: int,
    ) -> PolicyAcknowledgment:
        """Record when a user first opens a policy for reading."""
        result = await self.db.execute(
            select(PolicyAcknowledgment).where(
                PolicyAcknowledgment.id == acknowledgment_id
            )
        )
        ack = result.scalar_one_or_none()

        if ack and not ack.first_opened_at:
            ack.first_opened_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(ack)

        return ack

    async def update_reading_time(
        self,
        acknowledgment_id: int,
        additional_seconds: int,
    ) -> PolicyAcknowledgment:
        """Update the time spent reading a policy."""
        result = await self.db.execute(
            select(PolicyAcknowledgment).where(
                PolicyAcknowledgment.id == acknowledgment_id
            )
        )
        ack = result.scalar_one_or_none()

        if ack:
            current_time = ack.time_spent_seconds or 0
            ack.time_spent_seconds = current_time + additional_seconds
            await self.db.commit()
            await self.db.refresh(ack)

        return ack

    async def get_user_pending_acknowledgments(
        self,
        user_id: int,
    ) -> List[PolicyAcknowledgment]:
        """Get all pending acknowledgments for a user."""
        result = await self.db.execute(
            select(PolicyAcknowledgment)
            .where(
                and_(
                    PolicyAcknowledgment.user_id == user_id,
                    PolicyAcknowledgment.status.in_(
                        [
                            AcknowledgmentStatus.PENDING,
                            AcknowledgmentStatus.OVERDUE,
                        ]
                    ),
                )
            )
            .order_by(PolicyAcknowledgment.due_date)
        )
        return list(result.scalars().all())

    async def get_policy_acknowledgment_status(
        self,
        policy_id: int,
    ) -> Dict[str, Any]:
        """Get acknowledgment status summary for a policy."""
        result = await self.db.execute(
            select(PolicyAcknowledgment).where(
                PolicyAcknowledgment.policy_id == policy_id
            )
        )
        acknowledgments = result.scalars().all()

        total = len(acknowledgments)
        completed = sum(
            1 for a in acknowledgments if a.status == AcknowledgmentStatus.COMPLETED
        )
        pending = sum(
            1 for a in acknowledgments if a.status == AcknowledgmentStatus.PENDING
        )
        overdue = sum(
            1 for a in acknowledgments if a.status == AcknowledgmentStatus.OVERDUE
        )

        return {
            "policy_id": policy_id,
            "total_assigned": total,
            "completed": completed,
            "pending": pending,
            "overdue": overdue,
            "completion_rate": round((completed / total * 100), 1) if total > 0 else 0,
        }

    async def check_overdue_acknowledgments(self) -> List[PolicyAcknowledgment]:
        """Check for and mark overdue acknowledgments."""
        now = datetime.utcnow()

        result = await self.db.execute(
            select(PolicyAcknowledgment).where(
                and_(
                    PolicyAcknowledgment.status == AcknowledgmentStatus.PENDING,
                    PolicyAcknowledgment.due_date < now,
                )
            )
        )
        overdue = result.scalars().all()

        for ack in overdue:
            ack.status = AcknowledgmentStatus.OVERDUE

        if overdue:
            await self.db.commit()

        return list(overdue)

    async def get_reminders_to_send(self) -> List[Dict[str, Any]]:
        """Get acknowledgments that need reminder emails."""
        now = datetime.utcnow()
        reminders_needed = []

        # Get all pending acknowledgments
        result = await self.db.execute(
            select(PolicyAcknowledgment).where(
                PolicyAcknowledgment.status == AcknowledgmentStatus.PENDING
            )
        )
        pending = result.scalars().all()

        for ack in pending:
            # Get requirement for reminder days
            req_result = await self.db.execute(
                select(PolicyAcknowledgmentRequirement).where(
                    PolicyAcknowledgmentRequirement.id == ack.requirement_id
                )
            )
            requirement = req_result.scalar_one_or_none()

            if not requirement or not requirement.reminder_days_before:
                continue

            days_until_due = (ack.due_date - now).days

            for reminder_day in requirement.reminder_days_before:
                if days_until_due <= reminder_day:
                    # Check if we've already sent a reminder at this threshold
                    if ack.reminders_sent < len(requirement.reminder_days_before):
                        reminders_needed.append(
                            {
                                "acknowledgment_id": ack.id,
                                "user_id": ack.user_id,
                                "policy_id": ack.policy_id,
                                "due_date": ack.due_date,
                                "days_until_due": days_until_due,
                            }
                        )
                        break

        return reminders_needed

    async def record_reminder_sent(self, acknowledgment_id: int) -> None:
        """Record that a reminder was sent."""
        result = await self.db.execute(
            select(PolicyAcknowledgment).where(
                PolicyAcknowledgment.id == acknowledgment_id
            )
        )
        ack = result.scalar_one_or_none()

        if ack:
            ack.reminders_sent += 1
            ack.last_reminder_at = datetime.utcnow()
            await self.db.commit()

    async def get_compliance_dashboard(self) -> Dict[str, Any]:
        """Get overall policy acknowledgment compliance dashboard."""
        # Overall stats
        total_result = await self.db.execute(
            select(func.count(PolicyAcknowledgment.id))
        )
        total = total_result.scalar() or 0

        completed_result = await self.db.execute(
            select(func.count(PolicyAcknowledgment.id)).where(
                PolicyAcknowledgment.status == AcknowledgmentStatus.COMPLETED
            )
        )
        completed = completed_result.scalar() or 0

        overdue_result = await self.db.execute(
            select(func.count(PolicyAcknowledgment.id)).where(
                PolicyAcknowledgment.status == AcknowledgmentStatus.OVERDUE
            )
        )
        overdue = overdue_result.scalar() or 0

        pending_result = await self.db.execute(
            select(func.count(PolicyAcknowledgment.id)).where(
                PolicyAcknowledgment.status == AcknowledgmentStatus.PENDING
            )
        )
        pending = pending_result.scalar() or 0

        # Completion rate
        completion_rate = round((completed / total * 100), 1) if total > 0 else 0

        # Policies requiring attention (more than 20% overdue)
        # This would require more complex aggregation

        return {
            "total_assignments": total,
            "completed": completed,
            "pending": pending,
            "overdue": overdue,
            "completion_rate": completion_rate,
            "overdue_rate": round((overdue / total * 100), 1) if total > 0 else 0,
        }


class DocumentReadLogService:
    """Service for tracking document reads."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_document_access(
        self,
        document_type: str,
        document_id: int,
        user_id: int,
        document_version: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        scroll_percentage: Optional[int] = None,
        ip_address: Optional[str] = None,
        device_type: Optional[str] = None,
    ) -> DocumentReadLog:
        """Log a document access."""
        log = DocumentReadLog(
            document_type=document_type,
            document_id=document_id,
            user_id=user_id,
            document_version=document_version,
            accessed_at=datetime.utcnow(),
            duration_seconds=duration_seconds,
            scroll_percentage=scroll_percentage,
            ip_address=ip_address,
            device_type=device_type,
        )

        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)

        return log

    async def get_document_read_history(
        self,
        document_type: str,
        document_id: int,
        limit: int = 100,
    ) -> List[DocumentReadLog]:
        """Get read history for a document."""
        result = await self.db.execute(
            select(DocumentReadLog)
            .where(
                and_(
                    DocumentReadLog.document_type == document_type,
                    DocumentReadLog.document_id == document_id,
                )
            )
            .order_by(DocumentReadLog.accessed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_read_history(
        self,
        user_id: int,
        document_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[DocumentReadLog]:
        """Get read history for a user."""
        query = select(DocumentReadLog).where(DocumentReadLog.user_id == user_id)

        if document_type:
            query = query.where(DocumentReadLog.document_type == document_type)

        query = query.order_by(DocumentReadLog.accessed_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def has_user_read_document(
        self,
        user_id: int,
        document_type: str,
        document_id: int,
        since: Optional[datetime] = None,
    ) -> bool:
        """Check if a user has read a document."""
        query = select(DocumentReadLog).where(
            and_(
                DocumentReadLog.user_id == user_id,
                DocumentReadLog.document_type == document_type,
                DocumentReadLog.document_id == document_id,
            )
        )

        if since:
            query = query.where(DocumentReadLog.accessed_at >= since)

        result = await self.db.execute(query.limit(1))
        return result.scalar_one_or_none() is not None
