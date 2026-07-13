"""Closed-loop Actions for Regulatory Watch impacts (GKB WL2).

Creates real CAPA Actions from regulatory_watch_impacts with owner + due date,
and resolves the impact (optionally closing the linked action).
Kept as a dedicated module so audit-pack / compliance evidence paths stay untouched.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.compliance_automation import RegulatoryUpdate
from src.domain.models.document import Document
from src.domain.models.governed_knowledge import AiDecisionLog, RegulatoryImpactStatus, RegulatoryWatchImpact
from src.domain.models.user import User
from src.domain.services.reference_number import ReferenceNumberService

logger = logging.getLogger(__name__)

DEFAULT_DUE_DAYS = 14
HIGH_CONFIDENCE_DUE_DAYS = 7
HIGH_CONFIDENCE_THRESHOLD = 0.85


def _due_and_priority(confidence: Optional[float]) -> tuple[datetime, CAPAPriority]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if confidence is not None and confidence >= HIGH_CONFIDENCE_THRESHOLD:
        return now + timedelta(days=HIGH_CONFIDENCE_DUE_DAYS), CAPAPriority.HIGH
    return now + timedelta(days=DEFAULT_DUE_DAYS), CAPAPriority.MEDIUM


def _parse_due_date(due_date: Optional[str | datetime]) -> Optional[datetime]:
    if due_date is None:
        return None
    if isinstance(due_date, datetime):
        return due_date.replace(tzinfo=None) if due_date.tzinfo else due_date
    raw = due_date.strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError:
        # YYYY-MM-DD
        return datetime.strptime(raw[:10], "%Y-%m-%d")


class RegulatoryWatchActionsService:
    """Create / resolve Actions linked to regulatory watch impacts."""

    async def create_action_for_impact(
        self,
        db: AsyncSession,
        *,
        impact: RegulatoryWatchImpact,
        created_by_id: int,
        tenant_id: int,
        owner_id: Optional[int] = None,
        owner_email: Optional[str] = None,
        due_date: Optional[str | datetime] = None,
        priority: Optional[str] = None,
        auto_applied: bool = False,
        commit: bool = True,
    ) -> CAPAAction:
        """Create a CAPA Action for an impact (idempotent if already linked)."""
        if impact.tenant_id != tenant_id:
            raise LookupError("Regulatory impact not found for tenant")

        if impact.status == RegulatoryImpactStatus.DISMISSED:
            raise ValueError("Cannot create action for a dismissed impact")
        if impact.status == RegulatoryImpactStatus.RESOLVED:
            raise ValueError("Cannot create action for a resolved impact")

        if impact.action_id:
            existing = await db.get(CAPAAction, impact.action_id)
            if existing is not None and existing.tenant_id == tenant_id:
                return existing

        # Idempotent: CAPA already sourced from this impact
        prior = await db.execute(
            select(CAPAAction).where(
                CAPAAction.tenant_id == tenant_id,
                CAPAAction.source_type == CAPASource.REGULATORY_WATCH,
                CAPAAction.source_id == impact.id,
            )
        )
        existing_capa = prior.scalar_one_or_none()
        if existing_capa is not None:
            impact.action_id = existing_capa.id
            impact.status = RegulatoryImpactStatus.TASK_CREATED
            if impact.due_date is None and existing_capa.due_date is not None:
                impact.due_date = existing_capa.due_date
            if impact.owner_id is None:
                impact.owner_id = existing_capa.assigned_to_id
            if commit:
                await db.commit()
                await db.refresh(existing_capa)
            return existing_capa

        resolved_owner = owner_id
        if resolved_owner is None and owner_email:
            user_result = await db.execute(select(User).where(User.email == owner_email))
            user = user_result.scalar_one_or_none()
            if user is None:
                raise LookupError(f"User not found for email: {owner_email}")
            resolved_owner = user.id
        if resolved_owner is None:
            resolved_owner = created_by_id

        default_due, default_priority = _due_and_priority(impact.confidence)
        parsed_due = _parse_due_date(due_date) or default_due
        capa_priority = default_priority
        if priority:
            try:
                capa_priority = CAPAPriority(priority.lower())
            except ValueError as exc:
                raise ValueError(f"Invalid priority: {priority}") from exc

        update_title, doc_title = await self._context_titles(db, impact)
        title = f"Regulatory watch: review {doc_title or 'document'}"[:255]
        description = self._build_description(impact, update_title=update_title, doc_title=doc_title)

        ref = await ReferenceNumberService.generate(db, "capa", CAPAAction)
        capa = CAPAAction(
            reference_number=ref,
            title=title,
            description=description,
            capa_type=CAPAType.PREVENTIVE,
            status=CAPAStatus.OPEN,
            priority=capa_priority,
            source_type=CAPASource.REGULATORY_WATCH,
            source_id=impact.id,
            source_reference=f"regulatory_watch_impact:{impact.id}",
            assigned_to_id=resolved_owner,
            created_by_id=created_by_id,
            due_date=parsed_due,
            tenant_id=tenant_id,
            proposed_action=(
                "Review impacted controlled document against the regulatory update; "
                "revise, rematch evidence, and re-acknowledge as required."
            ),
        )
        db.add(capa)
        await db.flush()

        impact.action_id = capa.id
        impact.owner_id = resolved_owner
        impact.due_date = parsed_due
        impact.status = RegulatoryImpactStatus.TASK_CREATED

        db.add(
            AiDecisionLog(
                tenant_id=tenant_id,
                action="regulatory_watch_action_created",
                entity_type="regulatory_watch_impact",
                entity_id=str(impact.id),
                confidence=impact.confidence,
                auto_applied=auto_applied,
                payload={
                    "capa_id": capa.id,
                    "reference_number": ref,
                    "owner_id": resolved_owner,
                    "due_date": parsed_due.isoformat() if parsed_due else None,
                    "priority": capa_priority.value,
                },
            )
        )

        if commit:
            await db.commit()
            await db.refresh(capa)
        logger.info(
            "Created CAPA %s for regulatory watch impact %s (auto=%s)",
            ref,
            impact.id,
            auto_applied,
        )
        return capa

    async def resolve_impact(
        self,
        db: AsyncSession,
        *,
        impact: RegulatoryWatchImpact,
        resolved_by_id: int,
        tenant_id: int,
        notes: Optional[str] = None,
        dismiss: bool = False,
        close_action: bool = True,
    ) -> RegulatoryWatchImpact:
        """Resolve or dismiss an impact; optionally close the linked Action."""
        if impact.tenant_id != tenant_id:
            raise LookupError("Regulatory impact not found for tenant")

        if impact.status in (RegulatoryImpactStatus.RESOLVED, RegulatoryImpactStatus.DISMISSED):
            return impact

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        resolution_notes = (notes or "").strip() or None

        if dismiss:
            impact.status = RegulatoryImpactStatus.DISMISSED
        else:
            impact.status = RegulatoryImpactStatus.RESOLVED
            if close_action and impact.action_id:
                capa = await db.get(CAPAAction, impact.action_id)
                if capa is not None and capa.tenant_id == tenant_id and capa.status != CAPAStatus.CLOSED:
                    capa.status = CAPAStatus.CLOSED
                    capa.completed_at = now  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE SQLAlchemy Column
                    capa.verified_at = now  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE SQLAlchemy Column
                    capa.verified_by_id = resolved_by_id  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE SQLAlchemy Column
                    if resolution_notes:
                        capa.verification_result = resolution_notes  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE SQLAlchemy Column
                        capa.proposed_action = capa.proposed_action or resolution_notes  # type: ignore[assignment]

        impact.resolved_at = now  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE SQLAlchemy Column
        impact.resolved_by_id = resolved_by_id  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE SQLAlchemy Column
        impact.resolution_notes = resolution_notes  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE SQLAlchemy Column

        db.add(
            AiDecisionLog(
                tenant_id=tenant_id,
                action="regulatory_watch_impact_dismissed" if dismiss else "regulatory_watch_impact_resolved",
                entity_type="regulatory_watch_impact",
                entity_id=str(impact.id),
                confidence=impact.confidence,
                auto_applied=False,
                payload={
                    "dismiss": dismiss,
                    "action_id": impact.action_id,
                    "notes": resolution_notes,
                    "resolved_by_id": resolved_by_id,
                },
            )
        )
        await db.commit()
        await db.refresh(impact)
        return impact

    async def _context_titles(
        self, db: AsyncSession, impact: RegulatoryWatchImpact
    ) -> tuple[Optional[str], Optional[str]]:
        update_title: Optional[str] = None
        doc_title: Optional[str] = None
        try:
            update_id = int(impact.update_id)
        except (TypeError, ValueError):
            update_id = None
        if update_id is not None:
            update = await db.get(RegulatoryUpdate, update_id)
            if update is not None:
                update_title = update.title
        if impact.document_id:
            doc = await db.get(Document, impact.document_id)
            if doc is not None:
                doc_title = doc.title
        return update_title, doc_title

    def _build_description(
        self,
        impact: RegulatoryWatchImpact,
        *,
        update_title: Optional[str],
        doc_title: Optional[str],
    ) -> str:
        parts = [
            "Regulatory watch impact requires document review and closed-loop action.",
            f"Impact ID: {impact.id}",
            f"Update ID: {impact.update_id}",
        ]
        if update_title:
            parts.append(f"Update: {update_title}")
        if impact.document_id:
            parts.append(f"Document ID: {impact.document_id}")
        if doc_title:
            parts.append(f"Document: {doc_title}")
        if impact.confidence is not None:
            parts.append(f"Match confidence: {impact.confidence:.2f}")
        if impact.rationale:
            parts.append(f"Rationale: {impact.rationale}")
        return "\n".join(parts)[:5000]

    def serialize_action(self, capa: CAPAAction) -> dict[str, Any]:
        return {
            "id": capa.id,
            "reference_number": capa.reference_number,
            "title": capa.title,
            "status": capa.status.value if hasattr(capa.status, "value") else str(capa.status),
            "priority": capa.priority.value if hasattr(capa.priority, "value") else str(capa.priority),
            "owner_id": capa.assigned_to_id,
            "due_date": capa.due_date.isoformat() if capa.due_date else None,
            "source_type": "regulatory_watch",
            "source_id": capa.source_id,
            "action_key": f"capa:{capa.id}",
        }


regulatory_watch_actions_service = RegulatoryWatchActionsService()
