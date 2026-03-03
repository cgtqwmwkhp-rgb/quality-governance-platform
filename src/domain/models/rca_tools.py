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

from src.domain.models.base import AuditTrailMixin, TimestampMixin
from src.infrastructure.database import Base


class RCAToolType(str, enum.Enum):
    """Types of RCA tools available."""

    FIVE_WHYS = "five_whys"
    FISHBONE = "fishbone"
    FAULT_TREE = "fault_tree"
    BARRIER_ANALYSIS = "barrier_analysis"


class FishboneCategory(str, enum.Enum):
    """Standard Fishbone (6M) categories."""

    MANPOWER = "manpower"  # People
    METHOD = "method"  # Process
    MACHINE = "machine"  # Equipment
    MATERIAL = "material"  # Materials
    MEASUREMENT = "measurement"  # Metrics
    MOTHER_NATURE = "mother_nature"  # Environment


class FiveWhysAnalysis(Base, TimestampMixin, AuditTrailMixin):
    """5-Whys Root Cause Analysis tool.

    Iteratively asks "why" to drill down to root causes.
    """

    __tablename__ = "five_whys_analyses"
    __table_args__ = {"extend_existing": True}

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
    """Fishbone (Ishikawa) Diagram for cause-and-effect analysis.

    Uses 6M categories: Manpower, Method, Machine, Material, Measurement, Mother Nature
    """

    __tablename__ = "fishbone_diagrams"
    __table_args__ = {"extend_existing": True}

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

    # Causes by category (bones of the fish)
    # JSON structure:
    # {
    #   "manpower": [
    #     {"cause": "Inadequate training", "sub_causes": ["No refresher courses", "Outdated materials"]},
    #     {"cause": "Fatigue", "sub_causes": ["Long shifts", "Poor scheduling"]}
    #   ],
    #   "method": [...],
    #   "machine": [...],
    #   "material": [...],
    #   "measurement": [...],
    #   "mother_nature": [...]
    # }
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

    def add_cause(
        self,
        category: FishboneCategory,
        cause: str,
        sub_causes: Optional[List[str]] = None,
    ) -> None:
        """Add a cause to a specific category."""
        causes = self.causes or {}
        cat_key = category.value

        if cat_key not in causes:
            causes[cat_key] = []

        causes[cat_key].append(
            {
                "cause": cause,
                "sub_causes": sub_causes or [],
            }
        )

        self.causes = causes

    def get_all_causes(self) -> List[dict]:
        """Get all causes across categories."""
        all_causes = []
        for category, cause_list in (self.causes or {}).items():
            for cause in cause_list:
                all_causes.append(
                    {
                        "category": category,
                        "cause": cause["cause"],
                        "sub_causes": cause.get("sub_causes", []),
                    }
                )
        return all_causes

    def count_causes(self) -> dict:
        """Count causes by category."""
        counts = {}
        for category, cause_list in (self.causes or {}).items():
            counts[category] = len(cause_list)
        return counts


class BarrierAnalysis(Base, TimestampMixin, AuditTrailMixin):
    """Barrier Analysis for understanding control failures.

    Analyzes what barriers existed, which failed, and why.
    """

    __tablename__ = "barrier_analyses"
    __table_args__ = {"extend_existing": True}

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
