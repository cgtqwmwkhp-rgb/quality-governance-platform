"""Root Cause Analysis Tools Models.

Provides structured models for:
- 5-Whys Analysis
- Fishbone (Ishikawa) Diagrams
- Fault Tree Analysis
- Barrier Analysis
"""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, Base, TimestampMixin


class RCAToolType(str, enum.Enum):
    """Types of RCA tools available."""

    FIVE_WHYS = "five_whys"
    FISHBONE = "fishbone"
    FAULT_TREE = "fault_tree"
    BARRIER_ANALYSIS = "barrier_analysis"


class FishboneCategory(str, enum.Enum):
    """ICAM contributing-factor categories (INV-C12 / DEC-1).

    Re-specified from the manufacturing 6M set (manpower / method / machine /
    material / measurement / mother nature) to the four ICAM categories an
    incident investigator actually classifies against. The 6M names were never
    populated: no route, service or UI in this repository wrote a
    ``fishbone_diagrams`` row, so re-specifying is a contract change on an
    unused surface rather than a migration of stored meaning.

    Nothing is dropped from any row that does exist. ``causes`` is a JSON map
    keyed by these values, so a pre-existing diagram keyed by a 6M name is
    still readable — :meth:`FishboneDiagram.get_all_causes` iterates whatever
    keys are stored. Only *adding* under a 6M name stops working, and that is
    the intended refusal: there is no fifth taxonomy.
    """

    ORGANISATIONAL = "organisational_factors"
    TASK_ENVIRONMENTAL = "task_environmental_conditions"
    INDIVIDUAL_TEAM = "individual_team_actions"
    ABSENT_FAILED_DEFENCES = "absent_failed_defences"


class CausalDepth(str, enum.Enum):
    """HSG245 causal depth of one contributing factor (INV-C12 / DEC-1).

    Crossed with :class:`FishboneCategory` rather than replacing it: ICAM says
    *what kind* of factor this is, HSG245 says *how far back* it sits. Storing
    them as one flattened label would be the fifth taxonomy DEC-1 refuses.
    """

    IMMEDIATE = "immediate"
    UNDERLYING = "underlying"
    ROOT = "root"


class FiveWhysAnalysis(Base, TimestampMixin, AuditTrailMixin):
    """5-Whys Root Cause Analysis tool.

    Iteratively asks "why" to drill down to root causes.
    """

    __tablename__ = "five_whys_analyses"
    __table_args__ = {"extend_existing": True}

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Link to investigation or entity
    investigation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("investigation_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # incident, near_miss, complaint
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # Problem statement
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)

    # The 5 Whys (can have more or fewer)
    # Stored as JSON array of {why: string, answer: string, evidence: string}
    whys: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Root cause(s) identified
    root_causes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # Array of root cause strings
    primary_root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Contributing factors
    contributing_factors: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Corrective actions proposed
    proposed_actions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Metadata
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Review
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<FiveWhysAnalysis(id={self.id}, entity={self.entity_type}:{self.entity_id})>"

    def add_why(self, why_question: str, answer: str, evidence: Optional[str] = None) -> None:
        """Add a why iteration."""
        whys = self.whys or []
        whys.append(
            {
                "level": len(whys) + 1,
                "why": why_question,
                "answer": answer,
                "evidence": evidence,
            }
        )
        self.whys = whys

    def get_why_chain(self) -> str:
        """Get a readable chain of whys."""
        if not self.whys:
            return ""

        chain = [f"Problem: {self.problem_statement}"]
        for w in self.whys:
            chain.append(f"Why #{w['level']}: {w['why']}")
            chain.append(f"Because: {w['answer']}")

        if self.primary_root_cause:
            chain.append(f"Root Cause: {self.primary_root_cause}")

        return "\n".join(chain)


class FishboneDiagram(Base, TimestampMixin, AuditTrailMixin):
    """Cause-and-effect analysis, keyed by the four ICAM categories.

    INV-C12 makes this the store for an investigation's contributing factors:
    one diagram per run, each factor a cause under one ICAM category, carrying
    its optional sub-causes and its HSG245 depth. See
    ``src/domain/services/investigation_factors_service.py``.
    """

    __tablename__ = "fishbone_diagrams"
    __table_args__ = {"extend_existing": True}

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Link to investigation or entity
    investigation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("investigation_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # The effect (head of the fish)
    effect_statement: Mapped[str] = mapped_column(Text, nullable=False)

    # Causes by ICAM category (bones of the fish).
    # JSON structure:
    # {
    #   "organisational_factors": [
    #     {"id": 1, "cause": "No refresher training schedule",
    #      "sub_causes": ["Budget withdrawn", "No owner named"], "depth": "underlying"}
    #   ],
    #   "task_environmental_conditions": [...],
    #   "individual_team_actions": [...],
    #   "absent_failed_defences": [...],
    #   "_next_factor_id": 4
    # }
    #
    # ``id`` is unique within the diagram and is what the investigation factor
    # endpoints address, because a list position is not stable under a
    # concurrent edit. ``depth`` is a CausalDepth value, or absent on a row
    # written before INV-C12 — absent means "not stated", never a guessed depth.
    #
    # ``_next_factor_id`` is the high-water mark, not a category. It is here
    # rather than in a column because a deleted id must never be handed out
    # again: highest-stored-plus-one would reissue the id of the factor just
    # deleted, and a second tab still holding it would then silently edit a
    # different factor. Readers of this map skip keys whose value is not a list.
    causes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Primary causes identified (from any category)
    primary_causes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Root cause determination
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Corrective actions
    proposed_actions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Metadata
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Review
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<FishboneDiagram(id={self.id}, entity={self.entity_type}:{self.entity_id})>"

    #: Key inside ``causes`` holding the id high-water mark. Not a category:
    #: every reader here skips values that are not lists.
    NEXT_FACTOR_ID_KEY = "_next_factor_id"

    def next_cause_id(self) -> int:
        """The next unused cause id for this diagram.

        The stored high-water mark, or highest-stored-plus-one for a diagram
        written before INV-C12 that has no mark yet, whichever is larger. Taking
        the larger of the two is what makes a hand-edited or partially converted
        row safe: the mark can only ever move forward, so an id that has been
        issued is never issued again even after its factor is deleted.
        """
        causes = self.causes or {}
        highest = 0
        for key, cause_list in causes.items():
            if key == self.NEXT_FACTOR_ID_KEY or not isinstance(cause_list, list):
                continue
            for entry in cause_list:
                if not isinstance(entry, dict):
                    continue
                try:
                    highest = max(highest, int(entry.get("id") or 0))
                except (TypeError, ValueError):
                    continue
        try:
            marked = int(causes.get(self.NEXT_FACTOR_ID_KEY) or 0)
        except (TypeError, ValueError):
            marked = 0
        return max(marked, highest + 1)

    def add_cause(
        self,
        category: FishboneCategory,
        cause: str,
        sub_causes: Optional[List[str]] = None,
        depth: Optional["CausalDepth"] = None,
    ) -> dict:
        """Add a cause to one ICAM category and return the stored entry.

        ``depth`` is omitted from the entry when it is not given rather than
        defaulted: a factor whose HSG245 depth nobody recorded must not read
        back as "immediate".

        Reassigns ``self.causes`` rather than mutating it in place — this is a
        plain JSON column with no mutation tracking, so an in-place edit would
        not be persisted.
        """
        causes = {
            key: (list(value) if isinstance(value, list) else value) for key, value in (self.causes or {}).items()
        }
        cat_key = category.value

        cause_id = self.next_cause_id()
        entry: dict = {
            "id": cause_id,
            "cause": cause,
            "sub_causes": list(sub_causes or []),
        }
        if depth is not None:
            entry["depth"] = depth.value

        causes.setdefault(cat_key, []).append(entry)
        causes[self.NEXT_FACTOR_ID_KEY] = cause_id + 1
        self.causes = causes
        return entry

    def get_all_causes(self) -> List[dict]:
        """Get all causes across categories.

        Skips any key whose value is not a list — the id high-water mark lives
        in this map and is not a category.
        """
        all_causes = []
        for category, cause_list in (self.causes or {}).items():
            if not isinstance(cause_list, list):
                continue
            for cause in cause_list:
                if not isinstance(cause, dict):
                    continue
                all_causes.append(
                    {
                        "category": category,
                        "cause": cause.get("cause"),
                        "sub_causes": cause.get("sub_causes", []),
                        "depth": cause.get("depth"),
                    }
                )
        return all_causes

    def count_causes(self) -> dict:
        """Count causes by category. Non-category keys are not counted."""
        counts = {}
        for category, cause_list in (self.causes or {}).items():
            if not isinstance(cause_list, list):
                continue
            counts[category] = len(cause_list)
        return counts


class BarrierAnalysis(Base, TimestampMixin, AuditTrailMixin):
    """Barrier Analysis for understanding control failures.

    Analyzes what barriers existed, which failed, and why.
    """

    __tablename__ = "barrier_analyses"
    __table_args__ = {"extend_existing": True}

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Link to investigation or entity
    investigation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("investigation_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # Hazard/threat being analyzed
    hazard_description: Mapped[str] = mapped_column(Text, nullable=False)

    # Target (what was harmed or could have been harmed)
    target_description: Mapped[str] = mapped_column(Text, nullable=False)

    # Barriers analysis
    # JSON array of:
    # {
    #   "barrier_name": "Fall protection PPE",
    #   "barrier_type": "physical|administrative|procedural|warning",
    #   "existed": true,
    #   "status": "effective|failed|bypassed|missing",
    #   "failure_reason": "Not worn by worker",
    #   "failure_mode": "human_error|equipment_failure|design_flaw|other",
    #   "recommendations": ["Enforce PPE compliance", "Add buddy check system"]
    # }
    barriers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Summary
    barriers_that_worked: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    barriers_that_failed: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    missing_barriers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Recommendations
    recommended_new_barriers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    recommended_improvements: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Metadata
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<BarrierAnalysis(id={self.id}, entity={self.entity_type}:{self.entity_id})>"

    def add_barrier(
        self,
        barrier_name: str,
        barrier_type: str,
        existed: bool,
        status: str,
        failure_reason: Optional[str] = None,
        failure_mode: Optional[str] = None,
        recommendations: Optional[List[str]] = None,
    ) -> None:
        """Add a barrier to the analysis."""
        barriers = self.barriers or []
        barriers.append(
            {
                "barrier_name": barrier_name,
                "barrier_type": barrier_type,
                "existed": existed,
                "status": status,
                "failure_reason": failure_reason,
                "failure_mode": failure_mode,
                "recommendations": recommendations or [],
            }
        )
        self.barriers = barriers


class CAPAItem(Base, TimestampMixin, AuditTrailMixin):
    """Corrective and Preventive Action item.

    Links RCA findings to specific actions for tracking.
    """

    __tablename__ = "capa_items"
    __table_args__ = {"extend_existing": True}

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Source linkage (one of these should be set)
    five_whys_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("five_whys_analyses.id", ondelete="SET NULL"), nullable=True
    )
    fishbone_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("fishbone_diagrams.id", ondelete="SET NULL"), nullable=True
    )
    barrier_analysis_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("barrier_analyses.id", ondelete="SET NULL"), nullable=True
    )
    investigation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("investigation_runs.id", ondelete="SET NULL"), nullable=True
    )

    # CAPA details
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)  # corrective, preventive
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause_addressed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Assignment
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="open")  # open, in_progress, completed, verified, closed
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # critical, high, medium, low

    # Dates
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Verification
    verification_required: Mapped[bool] = mapped_column(Boolean, default=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Effectiveness review
    effectiveness_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_effective: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    effectiveness_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Evidence
    evidence_attachments: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # List of attachment IDs/URLs

    def __repr__(self) -> str:
        return f"<CAPAItem(id={self.id}, type={self.action_type}, status={self.status})>"
