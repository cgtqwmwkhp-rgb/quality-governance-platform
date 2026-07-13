"""Assessor competence_gap → Workforce closed-loop service.

Creates idempotent competence_gap_actions from Assessor / evidence signals,
links engineers + requirements, creates CAPA (CAPASource.competence_gap),
and resolves when competency evidence exists.

TrainingTicket resolve is optional until path11/workforce-p0-spine lands —
prefer requirement_id + CompetencyRecord.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.competence_gap import (
    CompetenceGapAction,
    CompetenceGapSignalType,
    CompetenceGapSourceType,
    CompetenceGapStatus,
)
from src.domain.models.compliance_evidence import ComplianceEvidenceLink
from src.domain.models.engineer import CompetencyLifecycleState, CompetencyRecord, CompetencyRequirement, Engineer
from src.domain.models.governed_knowledge import AiDecisionLog
from src.domain.models.user import User
from src.domain.services.audit_service import record_audit_event
from src.domain.services.reference_number import ReferenceNumberService

logger = logging.getLogger(__name__)

DEFAULT_DUE_DAYS = 14
HIGH_CONFIDENCE_DUE_DAYS = 7
HIGH_CONFIDENCE_THRESHOLD = 0.85

# Assessor Exceptions signals that must open a workforce gap (no silent drop).
WORKFORCE_GAP_SIGNALS = frozenset({"competence_gap", "nonconformity", "gap"})


def normalize_signal_type(raw: Optional[str]) -> Optional[CompetenceGapSignalType]:
    """Map Assessor / evidence signal strings into the DB CHECK set."""
    value = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if value in {"competence_gap", "gap"}:
        return CompetenceGapSignalType.COMPETENCE_GAP
    if value in {"nonconformity", "nc", "major_nc", "minor_nc"}:
        return CompetenceGapSignalType.NONCONFORMITY
    return None


def should_open_competence_gap(signal_type: Optional[str]) -> bool:
    value = (signal_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    return value in WORKFORCE_GAP_SIGNALS


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
        return datetime.strptime(raw[:10], "%Y-%m-%d")


def _status_value(status: CompetenceGapStatus | str) -> str:
    return status.value if hasattr(status, "value") else str(status)


class CompetenceGapService:
    """Closed-loop competence gap actions."""

    async def from_signal(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        created_by_id: int,
        source_type: str,
        source_id: int,
        signal_type: Optional[str] = None,
        rationale: Optional[str] = None,
        confidence: Optional[float] = None,
        commit: bool = True,
    ) -> CompetenceGapAction:
        """Create a gap row from an Assessor / evidence signal (idempotent)."""
        normalized_source = (source_type or "").strip().lower()
        try:
            CompetenceGapSourceType(normalized_source)
        except ValueError as exc:
            raise ValueError(f"Invalid source_type: {source_type}") from exc

        if not source_id:
            raise ValueError("source_id is required")

        existing = await db.execute(
            select(CompetenceGapAction).where(
                CompetenceGapAction.tenant_id == tenant_id,
                CompetenceGapAction.source_type == normalized_source,
                CompetenceGapAction.source_id == source_id,
            )
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            return row

        signal = normalize_signal_type(signal_type)
        if signal is None:
            raise ValueError("signal_type must be competence_gap or nonconformity " f"(got {signal_type!r})")

        gap = CompetenceGapAction(
            tenant_id=tenant_id,
            source_type=normalized_source,
            source_id=source_id,
            signal_type=signal,
            status=CompetenceGapStatus.OPEN,
            rationale=(rationale or "").strip() or None,
            confidence=confidence,
            created_by_id=created_by_id,
        )
        db.add(gap)
        await db.flush()

        await self._log(
            db,
            tenant_id=tenant_id,
            action="competence_gap.detected",
            gap=gap,
            actor_id=created_by_id,
            payload={
                "signal_type": signal.value,
                "source_type": normalized_source,
                "source_id": source_id,
                "confidence": confidence,
            },
        )

        if commit:
            await db.commit()
            await db.refresh(gap)
        logger.info(
            "competence_gap_actions id=%s created from %s:%s",
            gap.id,
            normalized_source,
            source_id,
        )
        return gap

    async def from_evidence_link(
        self,
        db: AsyncSession,
        *,
        link: ComplianceEvidenceLink,
        created_by_id: int,
        tenant_id: int,
        commit: bool = True,
    ) -> Optional[CompetenceGapAction]:
        """Hook for Assessor Exceptions confirm — no silent drop on gap/NC."""
        if link.tenant_id != tenant_id:
            raise LookupError("Evidence link not found for tenant")
        if not should_open_competence_gap(link.signal_type):
            return None

        return await self.from_signal(
            db,
            tenant_id=tenant_id,
            created_by_id=created_by_id,
            source_type=CompetenceGapSourceType.COMPLIANCE_EVIDENCE_LINK.value,
            source_id=link.id,
            signal_type=link.signal_type,
            rationale=link.rationale or link.notes,
            confidence=link.confidence,
            commit=commit,
        )

    async def list_gaps(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[CompetenceGapAction]:
        query = select(CompetenceGapAction).where(CompetenceGapAction.tenant_id == tenant_id)
        if status:
            query = query.where(CompetenceGapAction.status == status.strip().lower())
        query = query.order_by(CompetenceGapAction.created_at.desc()).limit(min(limit, 200))
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_gap(
        self,
        db: AsyncSession,
        *,
        gap_id: int,
        tenant_id: int,
    ) -> CompetenceGapAction:
        gap = await db.get(CompetenceGapAction, gap_id)
        if gap is None or gap.tenant_id != tenant_id:
            raise LookupError("Competence gap not found for tenant")
        return gap

    async def link_engineer(
        self,
        db: AsyncSession,
        *,
        gap: CompetenceGapAction,
        tenant_id: int,
        actor_id: int,
        engineer_id: int,
        requirement_id: Optional[int] = None,
        ticket_scheme: Optional[str] = None,
    ) -> CompetenceGapAction:
        if gap.tenant_id != tenant_id:
            raise LookupError("Competence gap not found for tenant")
        if _status_value(gap.status) in {
            CompetenceGapStatus.RESOLVED.value,
            CompetenceGapStatus.DISMISSED.value,
        }:
            raise ValueError("Cannot link a resolved or dismissed competence gap")

        engineer = await db.get(Engineer, engineer_id)
        if engineer is None or engineer.tenant_id != tenant_id:
            raise LookupError("Engineer not found for tenant")

        if requirement_id is not None:
            req = await db.get(CompetencyRequirement, requirement_id)
            if req is None or req.tenant_id != tenant_id:
                raise LookupError("Competency requirement not found for tenant")
            gap.requirement_id = requirement_id

        if ticket_scheme is not None:
            gap.ticket_scheme = ticket_scheme.strip() or None

        gap.engineer_id = engineer_id
        if _status_value(gap.status) == CompetenceGapStatus.OPEN.value:
            gap.status = CompetenceGapStatus.LINKED

        await self._log(
            db,
            tenant_id=tenant_id,
            action="competence_gap.linked",
            gap=gap,
            actor_id=actor_id,
            payload={
                "engineer_id": engineer_id,
                "requirement_id": gap.requirement_id,
                "ticket_scheme": gap.ticket_scheme,
            },
        )
        await db.commit()
        await db.refresh(gap)
        return gap

    async def create_capa(
        self,
        db: AsyncSession,
        *,
        gap: CompetenceGapAction,
        tenant_id: int,
        created_by_id: int,
        owner_id: Optional[int] = None,
        owner_email: Optional[str] = None,
        due_date: Optional[str | datetime] = None,
        priority: Optional[str] = None,
    ) -> CAPAAction:
        if gap.tenant_id != tenant_id:
            raise LookupError("Competence gap not found for tenant")
        if _status_value(gap.status) in {
            CompetenceGapStatus.RESOLVED.value,
            CompetenceGapStatus.DISMISSED.value,
        }:
            raise ValueError("Cannot create CAPA for a resolved or dismissed competence gap")

        if gap.capa_action_id:
            existing = await db.get(CAPAAction, gap.capa_action_id)
            if existing is not None and existing.tenant_id == tenant_id:
                return existing

        prior = await db.execute(
            select(CAPAAction).where(
                CAPAAction.tenant_id == tenant_id,
                CAPAAction.source_type == CAPASource.COMPETENCE_GAP,
                CAPAAction.source_id == gap.id,
            )
        )
        existing_capa = prior.scalar_one_or_none()
        if existing_capa is not None:
            gap.capa_action_id = existing_capa.id
            gap.status = CompetenceGapStatus.CAPA_CREATED
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

        default_due, default_priority = _due_and_priority(gap.confidence)
        parsed_due = _parse_due_date(due_date) or default_due
        capa_priority = default_priority
        if priority:
            try:
                capa_priority = CAPAPriority(priority.lower())
            except ValueError as exc:
                raise ValueError(f"Invalid priority: {priority}") from exc

        signal = gap.signal_type.value if hasattr(gap.signal_type, "value") else str(gap.signal_type)
        title = f"Competence gap: remediate {signal}"[:255]
        description = self._build_capa_description(gap)

        ref = await ReferenceNumberService.generate(db, "capa", CAPAAction)
        capa = CAPAAction(
            reference_number=ref,
            title=title,
            description=description,
            capa_type=CAPAType.CORRECTIVE,
            status=CAPAStatus.OPEN,
            priority=capa_priority,
            source_type=CAPASource.COMPETENCE_GAP,
            source_id=gap.id,
            source_reference=f"competence_gap:{gap.id}",
            assigned_to_id=resolved_owner,
            created_by_id=created_by_id,
            due_date=parsed_due,
            tenant_id=tenant_id,
            proposed_action=(
                "Link engineer to requirement or verified ticket; close only when " "competency evidence is active."
            ),
        )
        db.add(capa)
        await db.flush()

        gap.capa_action_id = capa.id
        gap.status = CompetenceGapStatus.CAPA_CREATED

        await self._log(
            db,
            tenant_id=tenant_id,
            action="competence_gap.capa_created",
            gap=gap,
            actor_id=created_by_id,
            payload={
                "capa_id": capa.id,
                "reference_number": ref,
                "owner_id": resolved_owner,
                "due_date": parsed_due.isoformat() if parsed_due else None,
            },
        )
        await db.commit()
        await db.refresh(capa)
        return capa

    async def resolve(
        self,
        db: AsyncSession,
        *,
        gap: CompetenceGapAction,
        tenant_id: int,
        resolved_by_id: int,
        notes: Optional[str] = None,
        dismiss: bool = False,
        close_capa: bool = True,
    ) -> CompetenceGapAction:
        if gap.tenant_id != tenant_id:
            raise LookupError("Competence gap not found for tenant")

        current = _status_value(gap.status)
        if current in {CompetenceGapStatus.RESOLVED.value, CompetenceGapStatus.DISMISSED.value}:
            return gap

        now = datetime.now(timezone.utc)
        resolution_notes = (notes or "").strip() or None

        if dismiss:
            gap.status = CompetenceGapStatus.DISMISSED
        else:
            await self._assert_resolve_evidence(db, gap=gap, tenant_id=tenant_id)
            gap.status = CompetenceGapStatus.RESOLVED
            if close_capa and gap.capa_action_id:
                capa = await db.get(CAPAAction, gap.capa_action_id)
                if capa is not None and capa.tenant_id == tenant_id and capa.status != CAPAStatus.CLOSED:
                    capa.status = CAPAStatus.CLOSED
                    capa.completed_at = now.replace(tzinfo=None)
                    capa.verified_at = now.replace(tzinfo=None)
                    capa.verified_by_id = resolved_by_id
                    if resolution_notes:
                        capa.verification_result = resolution_notes

        gap.resolved_at = now
        gap.resolved_by_id = resolved_by_id
        if resolution_notes:
            gap.rationale = (
                f"{gap.rationale}\n\nResolution: {resolution_notes}".strip() if gap.rationale else resolution_notes
            )

        await self._log(
            db,
            tenant_id=tenant_id,
            action="competence_gap.dismissed" if dismiss else "competence_gap.resolved",
            gap=gap,
            actor_id=resolved_by_id,
            payload={
                "dismiss": dismiss,
                "capa_action_id": gap.capa_action_id,
                "engineer_id": gap.engineer_id,
                "requirement_id": gap.requirement_id,
                "notes": resolution_notes,
            },
        )
        await db.commit()
        await db.refresh(gap)
        return gap

    async def golden_thread(
        self,
        db: AsyncSession,
        *,
        gap: CompetenceGapAction,
        tenant_id: int,
    ) -> dict[str, Any]:
        """Ordered auditor pack for a single competence gap — no invented SMTP."""
        if gap.tenant_id != tenant_id:
            raise LookupError("Competence gap not found for tenant")

        events: list[dict[str, Any]] = []

        events.append(
            {
                "event": "competence_gap.detected",
                "at": gap.created_at.isoformat() if gap.created_at else None,
                "actor_id": gap.created_by_id,
                "payload": {
                    "source_type": gap.source_type,
                    "source_id": gap.source_id,
                    "signal_type": (
                        gap.signal_type.value if hasattr(gap.signal_type, "value") else str(gap.signal_type)
                    ),
                    "confidence": gap.confidence,
                    "rationale": gap.rationale,
                },
            }
        )

        if gap.engineer_id:
            events.append(
                {
                    "event": "competence_gap.linked",
                    "at": gap.updated_at.isoformat() if gap.updated_at else None,
                    "actor_id": gap.created_by_id,
                    "payload": {
                        "engineer_id": gap.engineer_id,
                        "requirement_id": gap.requirement_id,
                        "ticket_scheme": gap.ticket_scheme,
                    },
                }
            )

        if gap.capa_action_id:
            capa = await db.get(CAPAAction, gap.capa_action_id)
            events.append(
                {
                    "event": "competence_gap.capa_created",
                    "at": capa.created_at.isoformat() if capa is not None and capa.created_at else None,
                    "actor_id": capa.created_by_id if capa is not None else None,
                    "payload": {
                        "capa_id": gap.capa_action_id,
                        "reference_number": capa.reference_number if capa else None,
                        "owner_id": capa.assigned_to_id if capa else None,
                        "due_date": capa.due_date.isoformat() if capa and capa.due_date else None,
                        "status": (capa.status.value if capa and hasattr(capa.status, "value") else None),
                    },
                }
            )

        if gap.resolved_at:
            events.append(
                {
                    "event": (
                        "competence_gap.dismissed"
                        if _status_value(gap.status) == CompetenceGapStatus.DISMISSED.value
                        else "competence_gap.resolved"
                    ),
                    "at": gap.resolved_at.isoformat(),
                    "actor_id": gap.resolved_by_id,
                    "payload": {
                        "status": _status_value(gap.status),
                        "engineer_id": gap.engineer_id,
                        "requirement_id": gap.requirement_id,
                    },
                }
            )

        # Persist AiDecisionLog rows for this entity (append-only stream).
        log_result = await db.execute(
            select(AiDecisionLog)
            .where(
                AiDecisionLog.tenant_id == tenant_id,
                AiDecisionLog.entity_type == "competence_gap_action",
                AiDecisionLog.entity_id == str(gap.id),
            )
            .order_by(AiDecisionLog.created_at.asc())
        )
        decision_logs = [
            {
                "event": row.action,
                "at": row.created_at.isoformat() if row.created_at else None,
                "actor_id": None,
                "payload": row.payload or {},
                "confidence": row.confidence,
                "auto_applied": row.auto_applied,
            }
            for row in log_result.scalars().all()
        ]

        return {
            "gap": self.serialize(gap),
            "events": events,
            "decision_log": decision_logs,
        }

    async def _assert_resolve_evidence(
        self,
        db: AsyncSession,
        *,
        gap: CompetenceGapAction,
        tenant_id: int,
    ) -> None:
        if not gap.engineer_id:
            raise ValueError("Cannot resolve: engineer must be linked first")

        if gap.requirement_id:
            req = await db.get(CompetencyRequirement, gap.requirement_id)
            if req is None or req.tenant_id != tenant_id:
                raise ValueError("Cannot resolve: competency requirement missing")
            result = await db.execute(
                select(CompetencyRecord).where(
                    CompetencyRecord.tenant_id == tenant_id,
                    CompetencyRecord.engineer_id == gap.engineer_id,
                    CompetencyRecord.asset_type_id == req.asset_type_id,
                    CompetencyRecord.state == CompetencyLifecycleState.ACTIVE,
                )
            )
            record = result.scalars().first()
            if record is None:
                raise ValueError(
                    "Cannot resolve: engineer has no active CompetencyRecord " f"for requirement {gap.requirement_id}"
                )
            return

        if gap.ticket_scheme:
            # TrainingTicket owned by P0 spine — soft probe, never invent table.
            try:
                from src.domain.models.engineer import TicketVerifyState, TrainingTicket  # type: ignore
            except ImportError as exc:
                raise ValueError(
                    "Cannot resolve via ticket_scheme until TrainingTicket "
                    "(path11/workforce-p0-spine) is available; link a requirement_id instead"
                ) from exc

            now = datetime.now(timezone.utc)
            ticket_q = select(TrainingTicket).where(
                TrainingTicket.tenant_id == tenant_id,
                TrainingTicket.engineer_id == gap.engineer_id,
                TrainingTicket.scheme == gap.ticket_scheme,
                TrainingTicket.verify_state == TicketVerifyState.VERIFIED,
            )
            ticket_result = await db.execute(ticket_q)
            ticket = ticket_result.scalars().first()
            if ticket is None:
                raise ValueError(f"Cannot resolve: no verified TrainingTicket for scheme {gap.ticket_scheme}")
            if ticket.expires_at is not None and ticket.expires_at <= now:
                raise ValueError(f"Cannot resolve: TrainingTicket for scheme {gap.ticket_scheme} is expired")
            return

        raise ValueError("Cannot resolve: link a requirement_id (preferred) or ticket_scheme before resolve")

    async def _log(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        action: str,
        gap: CompetenceGapAction,
        actor_id: int,
        payload: dict[str, Any],
    ) -> None:
        db.add(
            AiDecisionLog(
                tenant_id=tenant_id,
                action=action,
                entity_type="competence_gap_action",
                entity_id=str(gap.id),
                confidence=gap.confidence,
                auto_applied=False,
                payload={**payload, "actor_id": actor_id},
            )
        )
        await record_audit_event(
            db,
            event_type=action,
            entity_type="competence_gap_action",
            entity_id=str(gap.id),
            action=action,
            description=f"Competence gap {action}",
            payload=payload,
            actor_user_id=actor_id,
        )

    def _build_capa_description(self, gap: CompetenceGapAction) -> str:
        signal = gap.signal_type.value if hasattr(gap.signal_type, "value") else str(gap.signal_type)
        parts = [
            "Assessor / evidence competence signal requires closed-loop workforce action.",
            f"Gap ID: {gap.id}",
            f"Source: {gap.source_type}:{gap.source_id}",
            f"Signal: {signal}",
        ]
        if gap.confidence is not None:
            parts.append(f"Confidence: {gap.confidence:.2f}")
        if gap.rationale:
            parts.append(f"Rationale: {gap.rationale}")
        if gap.engineer_id:
            parts.append(f"Engineer ID: {gap.engineer_id}")
        if gap.requirement_id:
            parts.append(f"Requirement ID: {gap.requirement_id}")
        if gap.ticket_scheme:
            parts.append(f"Ticket scheme: {gap.ticket_scheme}")
        return "\n".join(parts)[:5000]

    def serialize(self, gap: CompetenceGapAction) -> dict[str, Any]:
        return {
            "id": gap.id,
            "tenant_id": gap.tenant_id,
            "source_type": gap.source_type,
            "source_id": gap.source_id,
            "signal_type": (gap.signal_type.value if hasattr(gap.signal_type, "value") else str(gap.signal_type)),
            "engineer_id": gap.engineer_id,
            "requirement_id": gap.requirement_id,
            "ticket_scheme": gap.ticket_scheme,
            "capa_action_id": gap.capa_action_id,
            "status": _status_value(gap.status),
            "rationale": gap.rationale,
            "confidence": gap.confidence,
            "created_by_id": gap.created_by_id,
            "resolved_at": gap.resolved_at.isoformat() if gap.resolved_at else None,
            "resolved_by_id": gap.resolved_by_id,
            "created_at": gap.created_at.isoformat() if gap.created_at else None,
            "updated_at": gap.updated_at.isoformat() if gap.updated_at else None,
            "action_key": f"capa:{gap.capa_action_id}" if gap.capa_action_id else None,
        }

    def serialize_capa(self, capa: CAPAAction) -> dict[str, Any]:
        return {
            "id": capa.id,
            "reference_number": capa.reference_number,
            "title": capa.title,
            "status": capa.status.value if hasattr(capa.status, "value") else str(capa.status),
            "priority": capa.priority.value if hasattr(capa.priority, "value") else str(capa.priority),
            "owner_id": capa.assigned_to_id,
            "due_date": capa.due_date.isoformat() if capa.due_date else None,
            "source_type": "competence_gap",
            "source_id": capa.source_id,
            "action_key": f"capa:{capa.id}",
        }


competence_gap_service = CompetenceGapService()
