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
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import quote

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.models.complaint import Complaint, ComplaintAction
from src.domain.models.compliance_schedule import ComplianceRequirement
from src.domain.models.incident import ActionStatus, Incident, IncidentAction, IncidentStatus
from src.domain.models.near_miss import NearMiss
from src.domain.models.user import User
from src.domain.services.compliance_schedule_authz import can_read_compliance_schedule
from src.domain.services.compliance_schedule_kill_switch import compliance_schedule_is_open_last_known

logger = logging.getLogger(__name__)

# Closed set — anything else stays on the simulated refusal path.
# Tool names match ASSIST_TOOLS in src.domain.services.assist.registry.
GROUNDED_INTENTS = frozenset(
    {
        "incident_count",
        "incident_closed_count",
        "incident_injury_category",
        "near_miss_count",
        "complaint_count",
        "overdue_actions",
        "compliance_overdue",
        "compliance_due_soon",
        "vehicle_check_top_failures",
        "vehicle_check_defect_summary",
    }
)

# SoR routes for quoted refs — relative in-app; export absolutises with the app origin.
_MODULE_PATH = {
    "incident": "/incidents/{id}",
    "near_miss": "/near-misses/{id}",
    "complaint": "/complaints/{id}",
    "incident_action": "/actions/{key}",
    "complaint_action": "/actions/{key}",
    "compliance_requirement": "/compliance-schedule/{id}",
    "vehicle_defect": "/vehicle-checklists",
}

# Intents that read the Compliance Schedule register. Unlike the four above, these
# are gated twice before any query runs: the module's own feature gate, and the
# caller's ``compliance_schedule:read`` permission. See ``_may_read_compliance``.
COMPLIANCE_SCHEDULE_INTENTS = frozenset(
    {
        "compliance_overdue",
        "compliance_due_soon",
    }
)

# Matches ``derive_status``'s ``due_soon_days`` default, so the copilot's "due soon"
# and the register's own due_soon badge cannot disagree. Asserted in
# tests/unit/test_copilot_grounded_compliance.py rather than left to inspection.
_DUE_SOON_HORIZON_DAYS = 30

# Reference tokens the validator recognises in free-text replies.
_REF_RE = re.compile(r"\b([A-Z]{2,}[A-Z0-9]*(?:-[A-Z0-9]+)*)\b")
_PERCENT_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*%")
# Standalone integers / decimals that look like figures (not years inside refs).
_FIGURE_RE = re.compile(r"(?<![A-Z0-9-])(\d+(?:\.\d+)?)(?![A-Z0-9%.-])")

_MAX_SAMPLE_REFS = 10

_PHRASE_SYSTEM = (
    "You phrase detailed review answers for a QHSE governance platform. "
    "Use ONLY the Facts JSON. Do not invent reference numbers, counts, "
    "percentages, or named records. Cite every figure you use. "
    "When Facts include multi-dimension breakdowns, present them as a markdown "
    "pipe table. Cite only reference_number values that appear in Facts, and "
    "when a ref has a path, write it as a markdown link [REF](path). "
    "If Facts do not answer the question, say so briefly — never guess."
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
    path: str = ""

    def sor_path(self) -> str:
        """In-app SoR route for this ref, or empty when unknown."""
        if self.path:
            return self.path
        template = _MODULE_PATH.get(self.module)
        if not template:
            return ""
        if "{key}" in template:
            key = quote(f"{self.module}:{self.id}", safe="")
            return template.format(key=key)
        return template.format(id=self.id)


@dataclass
class GroundedFacts:
    intent: str
    tenant_id: int
    label: str
    count: int
    refs: list[GroundedRef] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)
    breakdowns: list[tuple[str, list[tuple[str, int]]]] = field(default_factory=list)

    def allowed_refs(self) -> set[str]:
        return {r.reference_number.upper() for r in self.refs if r.reference_number}

    def allowed_figures(self) -> set[str]:
        """Canonical string forms of every numeric figure the reply may use."""
        figures: set[str] = {str(self.count), str(float(self.count))}

        def _add_number(value: Any) -> None:
            if isinstance(value, bool):
                return
            if isinstance(value, int):
                figures.add(str(value))
                figures.add(str(float(value)))
            elif isinstance(value, float):
                figures.add(str(value))
                if value == int(value):
                    figures.add(str(int(value)))
            elif isinstance(value, dict):
                for nested in value.values():
                    _add_number(nested)
            elif isinstance(value, (list, tuple)):
                for nested in value:
                    _add_number(nested)

        for value in self.extras.values():
            _add_number(value)
        for _title, rows in self.breakdowns:
            for _label, value in rows:
                _add_number(value)
        for ref in self.refs:
            _add_number(ref.id)
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
            "breakdowns": [
                {"title": title, "rows": [{"label": label, "count": count} for label, count in rows]}
                for title, rows in self.breakdowns
            ],
            "refs": [
                {
                    "module": r.module,
                    "id": r.id,
                    "reference_number": r.reference_number,
                    "path": r.sor_path(),
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

    # Compliance Schedule obligations. Deliberately *after* the two rules above, so a
    # question naming an action ("overdue compliance actions") keeps resolving to
    # overdue_actions exactly as it did before this intent existed. Both rules above
    # require the word "action", so nothing that reaches here mentioned one.
    if _mentions_compliance_obligations(text):
        if _asks_overdue(text):
            return "compliance_overdue"
        if _asks_due_soon(text):
            return "compliance_due_soon"

    if _mentions_vehicle_checks(text):
        if _asks_vehicle_defect_summary(text):
            return "vehicle_check_defect_summary"
        return "vehicle_check_top_failures"

    if "near" in text and "miss" in text and _asks_for_count(text):
        return "near_miss_count"
    if "complaint" in text and _asks_for_count(text):
        return "complaint_count"

    # Incident follow-ups before the generic incident count — registers already hold
    # status / injury / manual-handling signals; refusing them was the depth gap.
    if "incident" in text:
        if re.search(r"\bclosed\b", text) and (
            _asks_for_count(text) or re.search(r"\b(how many|are|of (those|them|these))\b", text)
        ):
            return "incident_closed_count"
        if _asks_injury_or_manual_handling(text):
            return "incident_injury_category"
        if _asks_for_count(text):
            return "incident_count"

    return None


def _mentions_vehicle_checks(text: str) -> bool:
    """Vehicle / van checklist register language (not asset register alone)."""
    if re.search(r"\bvehicle\s+checks?\b", text) or re.search(r"\bvan\s+checks?\b", text):
        return True
    if re.search(r"\b(vehicle|van)\b", text) and re.search(r"\b(checklist|checklists|defects?|checks?)\b", text):
        return True
    return bool(re.search(r"\bpams\b", text) and re.search(r"\b(check|defect|van)\b", text))


def _asks_vehicle_defect_summary(text: str) -> bool:
    """Open / priority defect totals rather than the failure heatmap."""
    if re.search(r"\b(p1|p2|p3)\b", text):
        return True
    if re.search(r"\bopen\b", text) and re.search(r"\bdefects?\b", text):
        return True
    return bool(_asks_for_count(text) and re.search(r"\bdefects?\b", text))


def _asks_injury_or_manual_handling(text: str) -> bool:
    """Whether the ask is about injury category / body part / manual handling."""
    if re.search(r"\bmanual[- ]handling\b", text):
        return True
    if re.search(r"\b(back injuries|back injury|injuries?|injury category|body parts?)\b", text):
        return True
    return bool(re.search(r"\b(lti|riddor|lost time)\b", text) and re.search(r"\b(how many|number|count)\b", text))


def _asks_for_count(text: str) -> bool:
    return bool(
        re.search(
            r"\b(how many|number of|count of|total|how much)\b",
            text,
        )
        or re.search(r"\b(incidents?|near[- ]?miss(?:es)?|complaints?)\s+(do we have|have we|are there)\b", text)
    )


def _mentions_compliance_obligations(text: str) -> bool:
    """Whether the question is about the Compliance Schedule register.

    Requires the register's own vocabulary. Bare "compliance" is not enough: the
    simulator already answers that with an ISO-clause refusal, and hijacking it here
    would answer a question about certification status with an obligation count.
    """
    if re.search(r"\bobligations?\b", text):
        return True
    if re.search(r"\bcompliance (requirements?|schedule|obligations?|checks?)\b", text):
        return True
    return bool(
        re.search(r"\bstatutory\b", text) and re.search(r"\b(requirements?|checks?|inspections?|dues?)\b", text)
    )


def _asks_overdue(text: str) -> bool:
    return bool(re.search(r"\b(overdue|past due|out of date|expired|missed)\b", text))


def _asks_due_soon(text: str) -> bool:
    return bool(re.search(r"\b(due soon|coming up|upcoming|due next|due in the next|falling due)\b", text))


class CopilotGroundingService:
    """Intent → tenant-scoped facts → optional model phrasing → citation check."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def try_answer(
        self,
        question: str,
        *,
        tenant_id: int,
        user_id: Optional[int] = None,
    ) -> GroundingOutcome:
        """Attempt a grounded answer for a registry tool the caller may invoke.

        ``user_id`` identifies the caller for RBAC. Every Assist tool declares a
        ``required_permission`` (or auth-only reason); missing / unentitled callers
        receive ``UNGROUNDED`` — same outward string as module-off — so the reply
        is not an oracle for module existence.
        """
        from src.domain.services.assist.permissions import tool_is_visible
        from src.domain.services.assist.registry import get_assist_tool

        intent = detect_grounded_intent(question)
        if intent is None:
            return UNGROUNDED

        tool = get_assist_tool(intent)
        if tool is None:
            return UNGROUNDED

        # Module kill-switch before any user/register lookup (compliance only).
        if intent in COMPLIANCE_SCHEDULE_INTENTS and not compliance_schedule_is_open_last_known():
            return UNGROUNDED

        user = None
        if user_id is not None:
            user = await self._load_caller(user_id, tenant_id=tenant_id)
        if not tool_is_visible(user, tool):
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
        if intent in {"incident_count", "incident_closed_count", "incident_injury_category"}:
            return await self._count_incidents(tenant_id, intent=intent)
        if intent == "near_miss_count":
            return await self._count_near_misses(tenant_id)
        if intent == "complaint_count":
            return await self._count_complaints(tenant_id)
        if intent == "overdue_actions":
            return await self._overdue_actions(tenant_id)
        if intent == "compliance_overdue":
            return await self._compliance_overdue(tenant_id)
        if intent == "compliance_due_soon":
            return await self._compliance_due_soon(tenant_id)
        if intent == "vehicle_check_top_failures":
            from src.domain.services.assist.tools.vehicles import gather_vehicle_check_top_failures

            return await gather_vehicle_check_top_failures(self.db, tenant_id=tenant_id)
        if intent == "vehicle_check_defect_summary":
            from src.domain.services.assist.tools.vehicles import gather_vehicle_check_defect_summary

            return await gather_vehicle_check_defect_summary(self.db, tenant_id=tenant_id)
        # Reachable only if GROUNDED_INTENTS gains a member without a branch here.
        # Previously the last intent was an unguarded fallthrough, so that mistake
        # would have answered the wrong question with real data instead of failing.
        raise ValueError(f"Grounded intent has no fact gatherer: {intent}")

    def format_facts_plain(self, facts: GroundedFacts) -> str:
        lines = [
            f"{facts.label}: **{facts.count}**.",
        ]
        for title, rows in facts.breakdowns:
            if not rows:
                continue
            lines.append("")
            lines.append(f"**{title}**")
            lines.append("| Dimension | Count |")
            lines.append("|---|---|")
            for label, value in rows:
                lines.append(f"| {label} | {value} |")
        # Prefer breakdown tables for multi-dim packs; only dump flat extras when
        # there is no table (keeps overdue/compliance replies unchanged).
        if facts.extras and not facts.breakdowns:
            for key, value in facts.extras.items():
                if isinstance(value, (dict, list, tuple)):
                    continue
                lines.append(f"{key.replace('_', ' ').capitalize()}: {value}.")
        if facts.refs:
            linked = []
            for ref in facts.refs:
                path = ref.sor_path()
                if path:
                    linked.append(f"[{ref.reference_number}]({path})")
                else:
                    linked.append(ref.reference_number)
            listed = ", ".join(linked)
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
        # Deeplink paths carry numeric ids; strip markdown destinations so path
        # segments are not mistaken for invented figures.
        scrubbed = re.sub(r"\]\([^)]+\)", "]", reply)

        for match in _REF_RE.finditer(scrubbed.upper()):
            token = match.group(1)
            # Only enforce tokens that look like platform refs (contain a hyphen
            # and a digit), so ordinary words are not treated as citations.
            if "-" not in token or not any(ch.isdigit() for ch in token):
                continue
            if token not in allowed_refs:
                return False

        for match in _PERCENT_RE.finditer(scrubbed):
            raw = match.group(1)
            if raw not in allowed_figures and f"{raw}%" not in allowed_figures:
                # Percentages are never produced by our count intents today —
                # any percentage in a grounded reply is invented.
                return False

        for match in _FIGURE_RE.finditer(scrubbed):
            raw = match.group(1)
            # Skip fragments that are part of a reference we already checked.
            start = match.start(1)
            window = scrubbed[max(0, start - 12) : match.end(1) + 1]
            if re.search(r"[A-Za-z]{2,}-", window):
                continue
            if raw not in allowed_figures:
                # Allow trivial enumeration (1., 2.) only when the digit equals
                # a known figure — otherwise fail closed.
                return False

        return True

    # ------------------------------------------------------------------ internals

    async def _may_read_compliance(self, *, tenant_id: int, user_id: Optional[int]) -> bool:
        """Whether this caller may be told anything about this tenant's obligations.

        Fails closed at every step. The copilot's HTTP routes are authenticated-only
        and check no module permission, so this is the only thing standing between a
        user without ``compliance_schedule:read`` and a real obligation count; it
        deliberately does not trust the route to have checked.

        The module gate is asked first because it costs nothing and a tenant whose
        module is off must not cause a user lookup, never mind a register query.
        """
        if not compliance_schedule_is_open_last_known():
            return False
        if user_id is None:
            return False
        user = await self._load_caller(user_id, tenant_id=tenant_id)
        if user is None:
            return False
        return can_read_compliance_schedule(user)

    async def _load_caller(self, user_id: int, *, tenant_id: int) -> Optional[User]:
        """The caller as a permission bearer, or None if they are not one.

        Scoped to the tenant whose data is about to be counted, so a user id that
        belongs to another organisation resolves to nobody rather than to a bearer
        whose roles would then be asked about this organisation's register. Roles are
        eager-loaded because ``User.has_permission`` walks the relationship and this
        session is async, where a lazy load raises instead of querying.
        """
        stmt = (
            select(User)
            .options(selectinload(User.roles))
            .where(
                User.id == user_id,
                User.tenant_id == tenant_id,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
        return (await self.db.execute(stmt)).scalars().first()

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
                "Write a detailed plain-language review using only these facts. "
                "Cite every figure. Use a markdown pipe table for any breakdowns. "
                "Link each reference_number as [REF](path) when path is present."
            )
            return await client.complete(
                prompt=prompt,
                system_prompt=_PHRASE_SYSTEM,
                temperature=0.1,
                max_tokens=1200,
            )
        except Exception as exc:  # noqa: BLE001 — provider outage → plain facts
            logger.info(
                "Copilot phrasing provider unavailable (%s); using plain facts",
                type(exc).__name__,
            )
            return None

    async def _count_incidents(self, tenant_id: int, *, intent: str = "incident_count") -> GroundedFacts:
        """Incident register facts with status / injury / MH (manual handling) dims.

        FR-ASSIST-DEPTH-01: follow-ups (closed counts, injury category, back / manual
        handling) resolve from the same computed pack rather than refusing for
        missing dimensions the register already holds.
        """
        base = (
            Incident.tenant_id == tenant_id,
            Incident.deleted_at.is_(None),
        )
        total = int((await self.db.execute(select(func.count()).select_from(Incident).where(*base))).scalar() or 0)
        closed = int(
            (
                await self.db.execute(
                    select(func.count()).select_from(Incident).where(*base, Incident.status == IncidentStatus.CLOSED)
                )
            ).scalar()
            or 0
        )
        open_count = max(0, total - closed)
        injury = int(
            (
                await self.db.execute(
                    select(func.count()).select_from(Incident).where(*base, Incident.is_injury.is_(True))
                )
            ).scalar()
            or 0
        )
        minor_injury = int(
            (
                await self.db.execute(
                    select(func.count()).select_from(Incident).where(*base, Incident.is_minor_injury.is_(True))
                )
            ).scalar()
            or 0
        )
        lti = int(
            (
                await self.db.execute(
                    select(func.count()).select_from(Incident).where(*base, Incident.is_lti.is_(True))
                )
            ).scalar()
            or 0
        )
        riddor = int(
            (
                await self.db.execute(
                    select(func.count()).select_from(Incident).where(*base, Incident.is_riddor_reportable.is_(True))
                )
            ).scalar()
            or 0
        )
        # Portable JSON text match (Postgres + SQLite hermetic / CI).
        body_parts_text = cast(Incident.body_parts, String)
        back_injury = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(Incident)
                    .where(*base, body_parts_text.is_not(None), body_parts_text.ilike("%back%"))
                )
            ).scalar()
            or 0
        )
        mh_filter = or_(
            Incident.title.ilike("%manual handling%"),
            Incident.title.ilike("%manual-handling%"),
            Incident.description.ilike("%manual handling%"),
            Incident.description.ilike("%manual-handling%"),
            body_parts_text.ilike("%manual%handling%"),
        )
        manual_handling = int(
            (await self.db.execute(select(func.count()).select_from(Incident).where(*base, mh_filter))).scalar() or 0
        )
        back_or_mh = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(Incident)
                    .where(
                        *base,
                        or_(
                            and_(body_parts_text.is_not(None), body_parts_text.ilike("%back%")),
                            mh_filter,
                        ),
                    )
                )
            ).scalar()
            or 0
        )

        type_rows = (
            await self.db.execute(
                select(Incident.incident_type, func.count())
                .where(*base)
                .group_by(Incident.incident_type)
                .order_by(func.count().desc())
            )
        ).all()
        type_breakdown = [(str(getattr(row[0], "value", row[0]) or "unknown"), int(row[1])) for row in type_rows]

        sample_filters = list(base)
        sample_order = Incident.id.desc()
        primary_count = total
        label = "Incident register count"
        if intent == "incident_closed_count":
            sample_filters.append(Incident.status == IncidentStatus.CLOSED)
            primary_count = closed
            label = "Closed incident count"
        elif intent == "incident_injury_category":
            sample_filters.append(
                or_(
                    Incident.is_injury.is_(True),
                    Incident.is_minor_injury.is_(True),
                    and_(body_parts_text.is_not(None), body_parts_text.ilike("%back%")),
                    mh_filter,
                )
            )
            primary_count = back_or_mh if back_or_mh else injury
            label = "Incident injury / manual-handling count"

        sample_stmt = (
            select(Incident.id, Incident.reference_number)
            .where(*sample_filters)
            .order_by(sample_order)
            .limit(_MAX_SAMPLE_REFS)
        )
        rows = (await self.db.execute(sample_stmt)).all()
        refs = [
            GroundedRef(module="incident", id=int(row.id), reference_number=str(row.reference_number))
            for row in rows
            if row.reference_number
        ]

        status_rows = [
            ("closed", closed),
            ("not_closed", open_count),
            ("total", total),
        ]
        injury_rows = [
            ("is_injury", injury),
            ("is_minor_injury", minor_injury),
            ("is_lti", lti),
            ("riddor_reportable", riddor),
            ("back_body_part", back_injury),
            ("manual_handling_text_match", manual_handling),
            ("back_or_manual_handling", back_or_mh),
        ]
        breakdowns: list[tuple[str, list[tuple[str, int]]]] = [
            ("Status breakdown", status_rows),
            ("Injury / MH category", injury_rows),
        ]
        if type_breakdown:
            breakdowns.append(("Incident type", type_breakdown))

        return GroundedFacts(
            intent=intent,
            tenant_id=tenant_id,
            label=label,
            count=primary_count,
            refs=refs,
            extras={
                "total_incidents": total,
                "closed_incidents": closed,
                "not_closed_incidents": open_count,
                "injury_incidents": injury,
                "minor_injury_incidents": minor_injury,
                "lti_incidents": lti,
                "riddor_incidents": riddor,
                "back_body_part_incidents": back_injury,
                "manual_handling_incidents": manual_handling,
                "back_or_manual_handling_incidents": back_or_mh,
            },
            breakdowns=breakdowns,
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

    @staticmethod
    def _live_requirement_filters(tenant_id: int) -> tuple:
        """The rows that are part of this tenant's live register, and only those.

        Same three predicates ``ComplianceScheduleService.get_stats`` applies, so the
        copilot's count and the register's own stats tile answer from one definition
        of "an obligation this organisation currently has".
        """
        return (
            ComplianceRequirement.tenant_id == tenant_id,
            ComplianceRequirement.deleted_at.is_(None),
            ComplianceRequirement.is_active.is_(True),
        )

    async def _compliance_requirement_facts(
        self,
        *,
        intent: str,
        tenant_id: int,
        label: str,
        due_filters: tuple,
        extras: dict[str, Any],
    ) -> GroundedFacts:
        filters = self._live_requirement_filters(tenant_id) + due_filters
        count = int(
            (await self.db.execute(select(func.count()).select_from(ComplianceRequirement).where(*filters))).scalar()
            or 0
        )
        sample_stmt = (
            select(ComplianceRequirement.id, ComplianceRequirement.reference_number)
            .where(*filters)
            .order_by(ComplianceRequirement.next_due_date.asc(), ComplianceRequirement.id.asc())
            .limit(_MAX_SAMPLE_REFS)
        )
        rows = (await self.db.execute(sample_stmt)).all()
        refs = [
            GroundedRef(
                module="compliance_requirement",
                id=int(row.id),
                reference_number=str(row.reference_number),
            )
            for row in rows
            if row.reference_number
        ]
        return GroundedFacts(
            intent=intent,
            tenant_id=tenant_id,
            label=label,
            count=count,
            refs=refs,
            extras=extras,
        )

    async def _compliance_overdue(self, tenant_id: int) -> GroundedFacts:
        today = datetime.now(timezone.utc).date()
        # Strictly earlier than today, matching derive_status: an obligation due
        # today is due, not yet overdue.
        due_filters = (ComplianceRequirement.next_due_date < today,)
        statutory = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(ComplianceRequirement)
                    .where(
                        *self._live_requirement_filters(tenant_id),
                        *due_filters,
                        ComplianceRequirement.statutory.is_(True),
                    )
                )
            ).scalar()
            or 0
        )
        return await self._compliance_requirement_facts(
            intent="compliance_overdue",
            tenant_id=tenant_id,
            label="Overdue compliance obligation count",
            due_filters=due_filters,
            extras={"statutory_overdue": statutory},
        )

    async def _compliance_due_soon(self, tenant_id: int) -> GroundedFacts:
        today = datetime.now(timezone.utc).date()
        horizon = today + timedelta(days=_DUE_SOON_HORIZON_DAYS)
        return await self._compliance_requirement_facts(
            intent="compliance_due_soon",
            tenant_id=tenant_id,
            label="Compliance obligations due soon",
            due_filters=(
                ComplianceRequirement.next_due_date >= today,
                ComplianceRequirement.next_due_date <= horizon,
            ),
            extras={"horizon_days": _DUE_SOON_HORIZON_DAYS},
        )


__all__ = [
    "CITATION_REFUSED",
    "COMPLIANCE_SCHEDULE_INTENTS",
    "GROUNDED_INTENTS",
    "CopilotGroundingService",
    "GroundedFacts",
    "GroundedRef",
    "GroundingOutcome",
    "UNGROUNDED",
    "detect_grounded_intent",
]
