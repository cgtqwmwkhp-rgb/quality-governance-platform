"""Session lifecycle for Audit Builder Check & Challenge coach."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.models.audit_challenge import (
    AuditChallengeProposal,
    AuditChallengeProposalDecision,
    AuditChallengeSession,
    AuditChallengeSessionStatus,
    AuditChallengeTurn,
    AuditChallengeTurnRole,
)
from src.domain.services.audit_challenge_pipeline import (
    CHALLENGE_CHIPS,
    AuditChallengePipeline,
    apply_accepted_proposals,
    build_grounding,
    normalize_sections,
)

logger = logging.getLogger(__name__)


class AuditChallengeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.pipeline = AuditChallengePipeline()

    async def create_session(
        self,
        *,
        tenant_id: int,
        user_id: Optional[int],
        sections: list[dict[str, Any]],
        brief: Optional[dict[str, Any]] = None,
        chip_id: Optional[str] = None,
        user_message: Optional[str] = None,
        template_id: Optional[int] = None,
    ) -> AuditChallengeSession:
        snapshot = {"sections": normalize_sections({"sections": sections})}
        session = AuditChallengeSession(
            tenant_id=tenant_id,
            user_id=user_id,
            template_id=template_id,
            status=AuditChallengeSessionStatus.QUEUED,
            progress_pct=0,
            progress_message="Queued",
            chip_id=chip_id,
            user_message=user_message,
            brief_json=brief or {},
            template_snapshot_json=snapshot,
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        self.db.add(session)
        await self.db.flush()

        if user_message or chip_id:
            self.db.add(
                AuditChallengeTurn(
                    session_id=session.id,
                    tenant_id=tenant_id,
                    role=AuditChallengeTurnRole.USER,
                    content=user_message or f"Chip: {chip_id}",
                    chip_id=chip_id,
                    sort_order=0,
                )
            )
            await self.db.flush()
        return session

    async def get_session(self, session_id: int, tenant_id: int) -> Optional[AuditChallengeSession]:
        result = await self.db.execute(
            select(AuditChallengeSession).where(
                AuditChallengeSession.id == session_id,
                AuditChallengeSession.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_turns(self, session_id: int, tenant_id: int) -> list[AuditChallengeTurn]:
        result = await self.db.execute(
            select(AuditChallengeTurn)
            .where(
                AuditChallengeTurn.session_id == session_id,
                AuditChallengeTurn.tenant_id == tenant_id,
            )
            .order_by(AuditChallengeTurn.sort_order.asc(), AuditChallengeTurn.id.asc())
        )
        return list(result.scalars().all())

    async def list_proposals(self, session_id: int, tenant_id: int) -> list[AuditChallengeProposal]:
        result = await self.db.execute(
            select(AuditChallengeProposal)
            .where(
                AuditChallengeProposal.session_id == session_id,
                AuditChallengeProposal.tenant_id == tenant_id,
            )
            .order_by(AuditChallengeProposal.id.asc())
        )
        return list(result.scalars().all())

    async def serialize_session(self, session: AuditChallengeSession) -> dict[str, Any]:
        turns = await self.list_turns(session.id, session.tenant_id)
        proposals = await self.list_proposals(session.id, session.tenant_id)
        return {
            "id": session.id,
            "status": session.status.value if hasattr(session.status, "value") else str(session.status),
            "progress_pct": session.progress_pct,
            "progress_message": session.progress_message,
            "chip_id": session.chip_id,
            "user_message": session.user_message,
            "template_id": session.template_id,
            "brief": session.brief_json or {},
            "models_used": session.models_used_json,
            "grounding": session.grounding_json,
            "error_code": session.error_code,
            "error_detail": session.error_detail,
            "chips": CHALLENGE_CHIPS,
            "turns": [
                {
                    "id": t.id,
                    "role": t.role.value if hasattr(t.role, "value") else str(t.role),
                    "content": t.content,
                    "chip_id": t.chip_id,
                    "citations": t.citations_json or [],
                    "sort_order": t.sort_order,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in turns
            ],
            "proposals": [self.serialize_proposal(p) for p in proposals],
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        }

    @staticmethod
    def serialize_proposal(p: AuditChallengeProposal) -> dict[str, Any]:
        return {
            "id": p.id,
            "proposal_key": p.proposal_key,
            "target_path": p.target_path,
            "change_type": p.change_type,
            "dimension": p.dimension,
            "assessor_failure_mode": p.assessor_failure_mode,
            "before": p.before_json,
            "after": p.edited_after_json or p.after_json,
            "rationale": p.rationale,
            "citations": p.citations_json or [],
            "decision": p.decision.value if hasattr(p.decision, "value") else str(p.decision),
        }

    async def process_session(self, session_id: int, tenant_id: int) -> AuditChallengeSession:
        session = await self.get_session(session_id, tenant_id)
        if session is None:
            raise ValueError("SESSION_NOT_FOUND")
        if session.status == AuditChallengeSessionStatus.RUNNING:
            return session
        if session.status == AuditChallengeSessionStatus.SUCCEEDED:
            return session

        session.status = AuditChallengeSessionStatus.RUNNING
        session.started_at = datetime.now(timezone.utc)
        session.progress_pct = 10
        session.progress_message = "Grounding standards & research"
        await self.db.flush()
        await self.db.commit()

        snapshot = session.template_snapshot_json or {}
        sections = normalize_sections(snapshot if isinstance(snapshot, dict) else {"sections": snapshot})
        brief = session.brief_json or {}

        grounding = await build_grounding(
            db=self.db,
            sections=sections,
            brief=brief,
            tenant_id=tenant_id,
            chip_id=session.chip_id,
        )
        session.grounding_json = grounding
        session.progress_pct = 35
        session.progress_message = "Assessor critic reviewing template"
        await self.db.flush()

        result = await self.pipeline.run(
            sections=sections,
            brief=brief,
            chip_id=session.chip_id,
            user_message=session.user_message,
            grounding=grounding,
        )
        session.progress_pct = 75
        session.progress_message = "Author drafting proposals"
        await self.db.flush()

        turns = await self.list_turns(session_id, tenant_id)
        next_order = max((t.sort_order for t in turns), default=-1) + 1

        critic_turn = AuditChallengeTurn(
            session_id=session.id,
            tenant_id=tenant_id,
            role=AuditChallengeTurnRole.CRITIC,
            content=result.get("critic_text") or "Critique complete.",
            chip_id=session.chip_id,
            citations_json=[c for f in result.get("findings") or [] for c in (f.get("citations") or [])][:20],
            sort_order=next_order,
        )
        self.db.add(critic_turn)
        await self.db.flush()

        author_turn = AuditChallengeTurn(
            session_id=session.id,
            tenant_id=tenant_id,
            role=AuditChallengeTurnRole.AUTHOR,
            content=f"Drafted {len(result.get('proposals') or [])} proposed changes for your review.",
            sort_order=next_order + 1,
        )
        self.db.add(author_turn)
        await self.db.flush()

        for prop in result.get("proposals") or []:
            self.db.add(
                AuditChallengeProposal(
                    session_id=session.id,
                    turn_id=author_turn.id,
                    tenant_id=tenant_id,
                    proposal_key=str(prop.get("proposal_key") or f"p-{author_turn.id}"),
                    target_path=str(prop.get("target_path") or ""),
                    change_type=str(prop.get("change_type") or "revise_question"),
                    dimension=prop.get("dimension"),
                    assessor_failure_mode=prop.get("assessor_failure_mode"),
                    before_json=prop.get("before"),
                    after_json=prop.get("after"),
                    rationale=prop.get("rationale"),
                    citations_json=prop.get("citations") or [],
                    decision=AuditChallengeProposalDecision.PENDING,
                )
            )

        session.models_used_json = result.get("models_used")
        session.status = AuditChallengeSessionStatus.SUCCEEDED
        session.progress_pct = 100
        session.progress_message = "Ready for review"
        session.completed_at = datetime.now(timezone.utc)
        await self.db.flush()
        return session

    async def enqueue_follow_up(
        self,
        *,
        session_id: int,
        tenant_id: int,
        user_id: Optional[int],
        message: str,
        chip_id: Optional[str] = None,
    ) -> AuditChallengeSession:
        session = await self.get_session(session_id, tenant_id)
        if session is None:
            raise ValueError("SESSION_NOT_FOUND")
        if session.status == AuditChallengeSessionStatus.RUNNING:
            raise ValueError("SESSION_ALREADY_RUNNING")
        turns = await self.list_turns(session_id, tenant_id)
        next_order = max((t.sort_order for t in turns), default=-1) + 1
        self.db.add(
            AuditChallengeTurn(
                session_id=session.id,
                tenant_id=tenant_id,
                role=AuditChallengeTurnRole.USER,
                content=message,
                chip_id=chip_id or session.chip_id,
                sort_order=next_order,
            )
        )
        session.user_message = message
        if chip_id:
            session.chip_id = chip_id
        session.status = AuditChallengeSessionStatus.QUEUED
        session.progress_pct = 0
        session.progress_message = "Queued follow-up"
        session.error_code = None
        session.error_detail = None
        session.completed_at = None
        session.updated_by_id = user_id
        await self.db.flush()
        return session

    # API verbs (accept/reject/edit) -> persisted proposal decision states.
    _DECISION_VERB_TO_STATE = {
        "accept": AuditChallengeProposalDecision.ACCEPTED,
        "reject": AuditChallengeProposalDecision.REJECTED,
        "edit": AuditChallengeProposalDecision.EDITED,
        "pending": AuditChallengeProposalDecision.PENDING,
        "accepted": AuditChallengeProposalDecision.ACCEPTED,
        "rejected": AuditChallengeProposalDecision.REJECTED,
        "edited": AuditChallengeProposalDecision.EDITED,
    }

    async def decide_proposal(
        self,
        *,
        session_id: int,
        proposal_id: int,
        tenant_id: int,
        decision: str,
        edited_after: Optional[dict[str, Any]] = None,
    ) -> AuditChallengeProposal:
        result = await self.db.execute(
            select(AuditChallengeProposal).where(
                AuditChallengeProposal.id == proposal_id,
                AuditChallengeProposal.session_id == session_id,
                AuditChallengeProposal.tenant_id == tenant_id,
            )
        )
        prop = result.scalar_one_or_none()
        if prop is None:
            raise ValueError("PROPOSAL_NOT_FOUND")
        state = self._DECISION_VERB_TO_STATE.get((decision or "").strip().lower())
        if state is None:
            raise ValueError("INVALID_DECISION")
        prop.decision = state
        if prop.decision == AuditChallengeProposalDecision.EDITED:
            if not isinstance(edited_after, dict):
                raise ValueError("EDITED_AFTER_REQUIRED")
            prop.edited_after_json = edited_after
        await self.db.flush()
        return prop

    async def apply_accepted(self, *, session_id: int, tenant_id: int) -> dict[str, Any]:
        session = await self.get_session(session_id, tenant_id)
        if session is None:
            raise ValueError("SESSION_NOT_FOUND")
        proposals = await self.list_proposals(session_id, tenant_id)
        accepted = [
            {
                "target_path": p.target_path,
                "after": p.edited_after_json or p.after_json,
                "after_json": p.edited_after_json or p.after_json,
                "edited_after_json": p.edited_after_json,
            }
            for p in proposals
            if p.decision
            in {
                AuditChallengeProposalDecision.ACCEPTED,
                AuditChallengeProposalDecision.EDITED,
            }
        ]
        snapshot = session.template_snapshot_json or {}
        sections = normalize_sections(snapshot if isinstance(snapshot, dict) else {"sections": snapshot})
        merged = apply_accepted_proposals(sections, accepted)
        # Persist applied snapshot for history continuity
        session.template_snapshot_json = {"sections": merged}
        await self.db.flush()
        return {"sections": merged, "applied_count": len(accepted)}
