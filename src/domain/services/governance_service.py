"""Governance framework services for workforce development.

Handles scheduling, template approval, competency gating,
and supervisor validation for assessments and inductions.
"""

import logging
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)


class GovernanceService:
    """Enforces governance rules for the Workforce Development Platform."""

    @staticmethod
    async def validate_supervisor(
        db: AsyncSession,
        supervisor_id: int,
        engineer_id: int,
        tenant_id: Optional[int] = None,
    ) -> dict:
        """Validate that the supervisor is authorised to assess this engineer.

        Args:
            supervisor_id: User id of the supervisor
            engineer_id: Engineer id (engineers.id) - used to get engineer's user_id for self-check
            tenant_id: Optional tenant scope - engineer and supervisor must belong to tenant

        Rules:
        - Supervisor must exist and be active
        - Supervisor cannot assess themselves
        - Supervisor must have the 'supervisor' or 'admin' role
        - If tenant_id provided, engineer and supervisor must be in tenant
        """
        from src.domain.models.engineer import Engineer
        from src.domain.models.user import User

        stmt = select(Engineer).where(Engineer.id == engineer_id)
        if tenant_id is not None:
            stmt = stmt.where(
                or_(
                    Engineer.tenant_id == tenant_id,
                    Engineer.tenant_id.is_(None),
                )
            )
        result = await db.execute(stmt)
        engineer = result.scalar_one_or_none()
        if engineer is None:
            return {
                "valid": False,
                "reason": "Engineer not found or not in tenant scope",
            }
        if engineer.user_id == supervisor_id:
            return {"valid": False, "reason": "Supervisors cannot assess themselves"}

        stmt = (
            select(User)
            .where(User.id == supervisor_id)
            .options(selectinload(User.roles))
        )
        result = await db.execute(stmt)
        supervisor = result.scalar_one_or_none()
        if not supervisor or not supervisor.is_active:
            return {"valid": False, "reason": "Supervisor not found or inactive"}

        if (
            tenant_id is not None
            and supervisor.tenant_id is not None
            and supervisor.tenant_id != tenant_id
        ):
            return {"valid": False, "reason": "Supervisor not in tenant scope"}

        role_names = (
            {r.name.lower() for r in supervisor.roles} if supervisor.roles else set()
        )
        if "supervisor" not in role_names and "admin" not in role_names:
            return {
                "valid": False,
                "reason": "Supervisor must have 'supervisor' or 'admin' role",
            }

        return {"valid": True, "reason": None}

    @staticmethod
    async def check_template_approval(
        db: AsyncSession, template_id: int, tenant_id: Optional[int] = None
    ) -> dict:
        """Check if a template is approved for use in assessments/inductions.

        Only PUBLISHED templates can be used for execution.
        If tenant_id provided, template must belong to tenant.
        """
        from src.domain.models.audit import AuditTemplate

        stmt = select(AuditTemplate).where(AuditTemplate.id == template_id)
        if tenant_id is not None:
            stmt = stmt.where(
                or_(
                    AuditTemplate.tenant_id == tenant_id,
                    AuditTemplate.tenant_id.is_(None),
                )
            )
        result = await db.execute(stmt)
        template = result.scalar_one_or_none()
        if not template:
            return {"approved": False, "reason": "Template not found"}

        status = getattr(template, "template_status", None)
        if status and hasattr(status, "value"):
            status = status.value

        if status and status != "published":
            return {
                "approved": False,
                "reason": f"Template status is '{status}', must be 'published'",
            }

        return {"approved": True, "reason": None}

    @staticmethod
    async def check_competency_gate(
        db: AsyncSession,
        engineer_id: int,
        asset_type_id: int,
        tenant_id: Optional[int] = None,
    ) -> dict:
        """Check if an engineer has the required competencies to work on an asset type.

        Returns gate status and any missing/expired competencies.
        If tenant_id provided, engineer and records must belong to tenant.
        """
        from src.domain.models.engineer import (
            CompetencyRecord,
            CompetencyLifecycleState,
        )
        from src.domain.models.asset import AssetType
        from src.domain.models.engineer import Engineer

        # Verify engineer belongs to tenant
        if tenant_id is not None:
            eng_stmt = (
                select(Engineer.id)
                .where(Engineer.id == engineer_id)
                .where(
                    or_(Engineer.tenant_id == tenant_id, Engineer.tenant_id.is_(None))
                )
            )
            if (await db.scalar(eng_stmt)) is None:
                return {
                    "cleared": False,
                    "reason": "Engineer not found or not in tenant scope",
                    "records": [],
                }
            at_stmt = (
                select(AssetType.id)
                .where(AssetType.id == asset_type_id)
                .where(
                    or_(AssetType.tenant_id == tenant_id, AssetType.tenant_id.is_(None))
                )
            )
            if (await db.scalar(at_stmt)) is None:
                return {
                    "cleared": False,
                    "reason": "Asset type not found or not in tenant scope",
                    "records": [],
                }

        stmt = select(CompetencyRecord).where(
            CompetencyRecord.engineer_id == engineer_id,
            CompetencyRecord.asset_type_id == asset_type_id,
        )
        if tenant_id is not None:
            stmt = stmt.where(
                or_(
                    CompetencyRecord.tenant_id == tenant_id,
                    CompetencyRecord.tenant_id.is_(None),
                )
            )
        result = await db.execute(stmt)
        records = result.scalars().all()

        if not records:
            return {
                "cleared": False,
                "reason": "No competency records found for this asset type",
                "records": [],
            }

        active = [r for r in records if r.state == CompetencyLifecycleState.ACTIVE]
        expired = [r for r in records if r.state == CompetencyLifecycleState.EXPIRED]
        failed = [r for r in records if r.state == CompetencyLifecycleState.FAILED]

        if failed:
            return {
                "cleared": False,
                "reason": "Engineer has failed competency records for this asset type",
                "records": [{"id": r.id, "state": r.state.value} for r in failed],
            }

        if expired and not active:
            return {
                "cleared": False,
                "reason": "All competencies for this asset type have expired",
                "records": [{"id": r.id, "state": r.state.value} for r in expired],
            }

        return {
            "cleared": True,
            "reason": None,
            "active_count": len(active),
        }

    @staticmethod
    async def get_scheduling_suggestions(
        db: AsyncSession, engineer_id: int, tenant_id: Optional[int] = None
    ) -> list:
        """Get scheduling suggestions for upcoming assessments.

        Returns competency records that are due or expiring soon.
        """
        from src.domain.models.engineer import (
            CompetencyRecord,
            CompetencyLifecycleState,
        )

        stmt = select(CompetencyRecord).where(
            CompetencyRecord.engineer_id == engineer_id,
            CompetencyRecord.state.in_(
                [
                    CompetencyLifecycleState.DUE,
                    CompetencyLifecycleState.EXPIRED,
                ]
            ),
        )
        if tenant_id is not None:
            from sqlalchemy import or_

            stmt = stmt.where(
                or_(
                    CompetencyRecord.tenant_id == tenant_id,
                    CompetencyRecord.tenant_id.is_(None),
                )
            )

        result = await db.execute(stmt)
        records = result.scalars().all()

        suggestions = []
        for r in records:
            priority = (
                "high" if r.state == CompetencyLifecycleState.EXPIRED else "medium"
            )
            suggestions.append(
                {
                    "competency_record_id": r.id,
                    "engineer_id": r.engineer_id,
                    "asset_type_id": r.asset_type_id,
                    "template_id": r.template_id,
                    "state": r.state.value,
                    "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                    "priority": priority,
                    "suggested_action": (
                        "Reassessment required"
                        if r.state == CompetencyLifecycleState.EXPIRED
                        else "Schedule reassessment"
                    ),
                }
            )

        return sorted(suggestions, key=lambda x: x["priority"] == "high", reverse=True)


class NotificationService:
    """Extended notification service for workforce development events."""

    @staticmethod
    async def notify_assessment_complete(
        db: AsyncSession,
        assessment_run_id: str,
        engineer_user_id: int,
        supervisor_id: int,
        outcome: str,
    ) -> None:
        """Create notifications when an assessment is completed."""
        from src.domain.models.notification import (
            Notification,
            NotificationPriority,
            NotificationType,
        )

        messages = {
            "pass": "Your competency assessment has been marked as PASS.",
            "fail": "Your competency assessment has been marked as FAIL. CAPA actions will be generated.",
            "conditional": "Your competency assessment has been marked as CONDITIONAL. Follow-up required.",
        }

        notification = Notification(
            user_id=engineer_user_id,
            type=NotificationType.AUDIT_COMPLETED,
            priority=NotificationPriority.MEDIUM,
            title="Assessment Complete",
            message=messages.get(
                outcome, f"Assessment completed with outcome: {outcome}"
            ),
            entity_type="assessment",
            entity_id=assessment_run_id,
            extra_data={"notification_type": "assessment_complete", "outcome": outcome},
        )
        db.add(notification)

        supervisor_notification = Notification(
            user_id=supervisor_id,
            type=NotificationType.AUDIT_COMPLETED,
            priority=NotificationPriority.MEDIUM,
            title="Assessment Submitted",
            message=f"Assessment {assessment_run_id} completed with outcome: {outcome}",
            entity_type="assessment",
            entity_id=assessment_run_id,
            extra_data={"notification_type": "assessment_complete", "outcome": outcome},
        )
        db.add(supervisor_notification)

        logger.info("Notifications created for assessment %s", assessment_run_id)

    @staticmethod
    async def notify_induction_complete(
        db: AsyncSession,
        induction_run_id: str,
        engineer_id: int,
        supervisor_id: int,
        not_yet_competent_count: int,
    ) -> None:
        """Create notifications when an induction is completed."""
        from src.domain.models.notification import (
            Notification,
            NotificationPriority,
            NotificationType,
        )

        if not_yet_competent_count > 0:
            msg = f"Your induction has been completed with {not_yet_competent_count} item(s) marked as 'Not Yet Competent'. CAPA actions will be generated."
        else:
            msg = "Congratulations! Your induction has been completed successfully."

        notification = Notification(
            user_id=engineer_id,
            type=NotificationType.COMPLIANCE_ALERT,
            priority=NotificationPriority.MEDIUM,
            title="Induction Complete",
            message=msg,
            entity_type="induction",
            entity_id=induction_run_id,
            extra_data={
                "notification_type": "induction_complete",
                "not_yet_competent_count": not_yet_competent_count,
            },
        )
        db.add(notification)

        logger.info("Notification created for induction %s", induction_run_id)

    @staticmethod
    async def notify_competency_expiry(
        db: AsyncSession,
        engineer_id: int,
        asset_type_id: int,
        days_until_expiry: int,
    ) -> None:
        """Create notification for upcoming competency expiry."""
        from src.domain.models.notification import (
            Notification,
            NotificationPriority,
            NotificationType,
        )

        notification = Notification(
            user_id=engineer_id,
            type=NotificationType.CERTIFICATE_EXPIRING,
            priority=NotificationPriority.MEDIUM,
            title="Competency Expiring Soon",
            message=f"Your competency for asset type {asset_type_id} expires in {days_until_expiry} days. Please schedule a reassessment.",
            entity_type="competency",
            entity_id=str(asset_type_id),
            extra_data={"notification_type": "competency_expiry_warning"},
        )
        db.add(notification)
