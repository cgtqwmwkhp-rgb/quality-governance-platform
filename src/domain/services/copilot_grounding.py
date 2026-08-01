"""Copilot grounded inference — closed intents, tenant-scoped facts, citation validation.

PR3b. The model (when a provider is credentialed) may only *phrase* an answer over
server-computed facts. Every reference number and every numeric figure in the reply
must appear in those facts; otherwise the reply is discarded and the caller falls
back to the existing honesty refusal. With no provider, facts are returned as plain
text — still without inventing.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.complaint import Complaint, ComplaintAction
from src.domain.models.incident import ActionStatus, Incident, IncidentAction
from src.domain.models.near_miss import NearMiss

logger = logging.getLogger(__name__)

# Closed set — anything else stays on the simulated refusal path.
GROUNDED_INTENTS = frozenset(
    {
        "incident_count",
        "near_miss_count",
        "complaint_count",
        "overdue_actions",
    }
)

# Reference tokens the validator recognises in free-text replies.
_REF_RE = re.compile(r"\b([A-Z]{2,}[A-Z0-9]*(?:-[A-Z0-9]+)*)\b")
_PERCENT_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*%")
# Standalone integers / decimals that look like figures (not years inside refs).
_FIGURE_RE = re.compile(r"(?<![A-Z0-9-])(\d+(?:\.\d+)?)(?![A-Z0-9%.-])")

_MAX_SAMPLE_REFS = 10

_PHRASE_SYSTEM = (
    "You phrase answers for a QHSE governance platform. "
    "Use ONLY the Facts JSON. Do not invent reference numbers, counts, "
    "percentages, or named records. Cite only reference_number values that "
    "appear in Facts. If Facts do not answer the question, say so briefly."
)


@dataclass(frozen=True)
class GroundingOutcome:
    """Result of a grounding attempt.

    ``kind``:
      - ``ungrounded`` — question outside the closed set; use the simulator.
      - ``answered`` — ``content`` is safe to serve; ``model_used`` names the path.
      - ``refused`` — intent matched but citation validation failed; use honesty refusal.
    """

    kind: str
    content: Optional[str] = None
    model_used: Optional[str] = None


UNGROUNDED = GroundingOutcome(kind="ungrounded")
CITATION_REFUSED = GroundingOutcome(kind="refused")


@dataclass(frozen=True)
class GroundedRef:
    module: str
    id: int
    reference_number: str


@dataclass
class GroundedFacts:
    intent: str
    tenant_id: int
    label: str
    count: int
    refs: list[GroundedRef] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    def allowed_refs(self) -> set[str]:
        return {r.reference_number.upper() for r in self.refs if r.reference_number}

    def allowed_figures(self) -> set[str]:
        """Canonical string forms of every numeric figure the reply may use."""
        figures: set[str] = {str(self.count), str(float(self.count))}
        for value in self.extras.values():
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                figures.add(str(value))
                figures.add(str(float(value)))
            elif isinstance(value, float):
                figures.add(str(value))
                if value == int(value):
                    figures.add(str(int(value)))
        figures.add(str(len(self.refs)))
        figures.add(str(float(len(self.refs))))
        return figures

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "tenant_id": self.tenant_id,
            "label": self.label,
            "count": self.count,
            "extras": self.extras,
            "refs": [
                {
                    "module": r.module,
                    "id": r.id,
                    "reference_number": r.reference_number,
                }
                for r in self.refs
            ],
        }


def detect_grounded_intent(message: str) -> Optional[str]:
    """Map a user message onto the closed intent set, or None."""
    text = (message or "").strip().lower()
    if not text:
        return None

    # Overdue actions before generic "actions" noise.
    if "overdue" in text and "action" in text:
        return "overdue_actions"
    if re.search(r"\bactions?\b", text) and re.search(r"\b(past due|late)\b", text):
        return "overdue_actions"

    if "near" in text and "miss" in text and _asks_for_count(text):
        return "near_miss_count"
    if "complaint" in text and _asks_for_count(text):
        return "complaint_count"
    if "incident" in text and _asks_for_count(text):
        return "incident_count"

    return None


def _asks_for_count(text: str) -> bool:
    return bool(
        re.search(
            r"\b(how many|number of|count of|total|how much)\b",
            text,
        )
        or re.search(r"\b(incidents?|near[- ]?miss(?:es)?|complaints?)\s+(do we have|have we|are there)\b", text)
    )


class CopilotGroundingService:
    """Intent → tenant-scoped facts → optional model phrasing → citation check."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def try_answer(self, question: str, *, tenant_id: int) -> GroundingOutcome:
        """Attempt a grounded answer for a closed-set intent."""
        intent = detect_grounded_intent(question)
        if intent is None:
            return UNGROUNDED

        facts = await self.gather_facts(intent, tenant_id=tenant_id)
        if self._provider_available():
            phrased = await self._phrase_over_facts(question, facts)
            if phrased is not None:
                if self.validate_citations(phrased, facts):
                    return GroundingOutcome(kind="answered", content=phrased, model_used="grounded-llm")
                logger.warning(
                    "Copilot grounded reply failed citation validation; dropping",
                    extra={"intent": intent, "tenant_id": tenant_id},
                )
                return CITATION_REFUSED

        plain = self.format_facts_plain(facts)
        if not self.validate_citations(plain, facts):
            logger.error("Deterministic fact formatter failed its own citation check")
            return CITATION_REFUSED
        return GroundingOutcome(kind="answered", content=plain, model_used="grounded-facts")

    async def gather_facts(self, intent: str, *, tenant_id: int) -> GroundedFacts:
        if intent not in GROUNDED_INTENTS:
            raise ValueError(f"Unknown grounded intent: {intent}")
        if intent == "incident_count":
            return await self._count_incidents(tenant_id)
        if intent == "near_miss_count":
            return await self._count_near_misses(tenant_id)
        if intent == "complaint_count":
            return await self._count_complaints(tenant_id)
        return await self._overdue_actions(tenant_id)

    def format_facts_plain(self, facts: GroundedFacts) -> str:
        lines = [
            f"{facts.label}: {facts.count}.",
        ]
        if facts.extras:
            for key, value in facts.extras.items():
                lines.append(f"{key.replace('_', ' ').capitalize()}: {value}.")
        if facts.refs:
            listed = ", ".join(r.reference_number for r in facts.refs)
            suffix = "" if facts.count <= len(facts.refs) else f" (showing {len(facts.refs)} of {facts.count})"
            lines.append(f"References{suffix}: {listed}.")
        else:
            lines.append("No matching records in this organisation.")
        lines.append("Figures are from your live registers for this organisation only.")
        return "\n".join(lines)

    def validate_citations(self, reply: str, facts: GroundedFacts) -> bool:
        """Fail closed: every ref and figure in the reply must appear in facts.

        Modelled on :meth:`SafetyInsightsAnalystService.validate_citations` —
        invented references are dropped from consideration; here the unit of
        rejection is the whole free-text reply.
        """
        if not reply or not reply.strip():
            return False

        allowed_refs = facts.allowed_refs()
        allowed_figures = facts.allowed_figures()

        for match in _REF_RE.finditer(reply.upper()):
            token = match.group(1)
            # Only enforce tokens that look like platform refs (contain a hyphen
            # and a digit), so ordinary words are not treated as citations.
            if "-" not in token or not any(ch.isdigit() for ch in token):
                continue
            if token not in allowed_refs:
                return False

        for match in _PERCENT_RE.finditer(reply):
            raw = match.group(1)
            if raw not in allowed_figures and f"{raw}%" not in allowed_figures:
                # Percentages are never produced by our count intents today —
                # any percentage in a grounded reply is invented.
                return False

        for match in _FIGURE_RE.finditer(reply):
            raw = match.group(1)
            # Skip fragments that are part of a reference we already checked.
            start = match.start(1)
            window = reply[max(0, start - 12) : match.end(1) + 1]
            if re.search(r"[A-Za-z]{2,}-", window):
                continue
            if raw not in allowed_figures:
                # Allow trivial enumeration (1., 2.) only when the digit equals
                # a known figure — otherwise fail closed.
                return False

        return True

    # ------------------------------------------------------------------ internals

    @staticmethod
    def _provider_available() -> bool:
        from src.domain.services.ai_models import AIConfig

        config = AIConfig.from_env()
        return bool(config.anthropic_api_key or config.openai_api_key)

    async def _phrase_over_facts(self, question: str, facts: GroundedFacts) -> Optional[str]:
        try:
            from src.domain.services.ai_models import get_ai_client

            client = get_ai_client()
            prompt = (
                f"Question:\n{question}\n\n"
                f"Facts (JSON):\n{json.dumps(facts.to_prompt_dict(), indent=2)}\n\n"
                "Write a short plain-language answer using only these facts."
            )
            return await client.complete(
                prompt=prompt,
                system_prompt=_PHRASE_SYSTEM,
                temperature=0.1,
                max_tokens=600,
            )
        except Exception as exc:  # noqa: BLE001 — provider outage → plain facts
            logger.info(
                "Copilot phrasing provider unavailable (%s); using plain facts",
                type(exc).__name__,
            )
            return None

    async def _count_incidents(self, tenant_id: int) -> GroundedFacts:
        count_stmt = (
            select(func.count())
            .select_from(Incident)
            .where(
                Incident.tenant_id == tenant_id,
                Incident.deleted_at.is_(None),
            )
        )
        count = int((await self.db.execute(count_stmt)).scalar() or 0)
        sample_stmt = (
            select(Incident.id, Incident.reference_number)
            .where(
                Incident.tenant_id == tenant_id,
                Incident.deleted_at.is_(None),
            )
            .order_by(Incident.id.desc())
            .limit(_MAX_SAMPLE_REFS)
        )
        rows = (await self.db.execute(sample_stmt)).all()
        refs = [
            GroundedRef(module="incident", id=int(row.id), reference_number=str(row.reference_number))
            for row in rows
            if row.reference_number
        ]
        return GroundedFacts(
            intent="incident_count",
            tenant_id=tenant_id,
            label="Open register incident count",
            count=count,
            refs=refs,
        )

    async def _count_near_misses(self, tenant_id: int) -> GroundedFacts:
        count_stmt = select(func.count()).select_from(NearMiss).where(NearMiss.tenant_id == tenant_id)
        count = int((await self.db.execute(count_stmt)).scalar() or 0)
        sample_stmt = (
            select(NearMiss.id, NearMiss.reference_number)
            .where(NearMiss.tenant_id == tenant_id)
            .order_by(NearMiss.id.desc())
            .limit(_MAX_SAMPLE_REFS)
        )
        rows = (await self.db.execute(sample_stmt)).all()
        refs = [
            GroundedRef(module="near_miss", id=int(row.id), reference_number=str(row.reference_number))
            for row in rows
            if row.reference_number
        ]
        return GroundedFacts(
            intent="near_miss_count",
            tenant_id=tenant_id,
            label="Near-miss count",
            count=count,
            refs=refs,
        )

    async def _count_complaints(self, tenant_id: int) -> GroundedFacts:
        count_stmt = (
            select(func.count())
            .select_from(Complaint)
            .where(
                Complaint.tenant_id == tenant_id,
                Complaint.deleted_at.is_(None),
            )
        )
        count = int((await self.db.execute(count_stmt)).scalar() or 0)
        sample_stmt = (
            select(Complaint.id, Complaint.reference_number)
            .where(
                Complaint.tenant_id == tenant_id,
                Complaint.deleted_at.is_(None),
            )
            .order_by(Complaint.id.desc())
            .limit(_MAX_SAMPLE_REFS)
        )
        rows = (await self.db.execute(sample_stmt)).all()
        refs = [
            GroundedRef(module="complaint", id=int(row.id), reference_number=str(row.reference_number))
            for row in rows
            if row.reference_number
        ]
        return GroundedFacts(
            intent="complaint_count",
            tenant_id=tenant_id,
            label="Complaint count",
            count=count,
            refs=refs,
        )

    async def _overdue_actions(self, tenant_id: int) -> GroundedFacts:
        now = datetime.now(timezone.utc)
        closed = (
            ActionStatus.COMPLETED,
            ActionStatus.VERIFIED,
            ActionStatus.CANCELLED,
        )

        inc_overdue = or_(
            IncidentAction.status == ActionStatus.OVERDUE,
            and_(
                IncidentAction.due_date.is_not(None),
                IncidentAction.due_date < now,
                IncidentAction.status.not_in(closed),
            ),
        )
        inc_filters = (
            IncidentAction.tenant_id == tenant_id,
            Incident.tenant_id == tenant_id,
            IncidentAction.deleted_at.is_(None),
            Incident.deleted_at.is_(None),
            inc_overdue,
        )
        count = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(IncidentAction)
                    .join(Incident, IncidentAction.incident_id == Incident.id)
                    .where(*inc_filters)
                )
            ).scalar()
            or 0
        )
        actions = list(
            (
                await self.db.execute(
                    select(IncidentAction)
                    .join(Incident, IncidentAction.incident_id == Incident.id)
                    .where(*inc_filters)
                    .order_by(IncidentAction.due_date.asc().nullslast())
                    .limit(_MAX_SAMPLE_REFS)
                )
            )
            .scalars()
            .all()
        )
        refs = [
            GroundedRef(
                module="incident_action",
                id=int(action.id),
                reference_number=str(action.reference_number),
            )
            for action in actions
            if action.reference_number
        ]

        cmp_overdue = or_(
            ComplaintAction.status == ActionStatus.OVERDUE,
            and_(
                ComplaintAction.due_date.is_not(None),
                ComplaintAction.due_date < now,
                ComplaintAction.status.not_in(closed),
            ),
        )
        cmp_filters = (
            ComplaintAction.tenant_id == tenant_id,
            Complaint.tenant_id == tenant_id,
            ComplaintAction.deleted_at.is_(None),
            Complaint.deleted_at.is_(None),
            cmp_overdue,
        )
        c_count = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(ComplaintAction)
                    .join(Complaint, ComplaintAction.complaint_id == Complaint.id)
                    .where(*cmp_filters)
                )
            ).scalar()
            or 0
        )
        remaining = max(0, _MAX_SAMPLE_REFS - len(refs))
        if remaining:
            c_actions = list(
                (
                    await self.db.execute(
                        select(ComplaintAction)
                        .join(Complaint, ComplaintAction.complaint_id == Complaint.id)
                        .where(*cmp_filters)
                        .order_by(ComplaintAction.due_date.asc().nullslast())
                        .limit(remaining)
                    )
                )
                .scalars()
                .all()
            )
            for action in c_actions:
                if action.reference_number:
                    refs.append(
                        GroundedRef(
                            module="complaint_action",
                            id=int(action.id),
                            reference_number=str(action.reference_number),
                        )
                    )

        total = count + c_count
        return GroundedFacts(
            intent="overdue_actions",
            tenant_id=tenant_id,
            label="Overdue action count",
            count=total,
            refs=refs,
            extras={
                "incident_action_overdue": count,
                "complaint_action_overdue": c_count,
            },
        )


__all__ = [
    "CITATION_REFUSED",
    "GROUNDED_INTENTS",
    "CopilotGroundingService",
    "GroundedFacts",
    "GroundedRef",
    "GroundingOutcome",
    "UNGROUNDED",
    "detect_grounded_intent",
]
