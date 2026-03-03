"""RCA Tools Service.

Provides services for 5-Whys, Fishbone diagrams, and CAPA management.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.rca_tools import (
    BarrierAnalysis,
    CAPAItem,
    FishboneCategory,
    FishboneDiagram,
    FiveWhysAnalysis,
    RCAToolType,
)

logger = logging.getLogger(__name__)


class FiveWhysService:
    """Service for 5-Whys analysis."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_analysis(
        self,
        problem_statement: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        investigation_id: Optional[int] = None,
    ) -> FiveWhysAnalysis:
        """Create a new 5-Whys analysis."""
        analysis = FiveWhysAnalysis(
            problem_statement=problem_statement,
            entity_type=entity_type,
            entity_id=entity_id,
            investigation_id=investigation_id,
            whys=[],
        )
        self.db.add(analysis)
        await self.db.commit()
        await self.db.refresh(analysis)
        return analysis

    async def add_why_iteration(
        self,
        analysis_id: int,
        why_question: str,
        answer: str,
        evidence: Optional[str] = None,
    ) -> FiveWhysAnalysis:
        """Add a why iteration to an existing analysis."""
        result = await self.db.execute(select(FiveWhysAnalysis).where(FiveWhysAnalysis.id == analysis_id))
        analysis = result.scalar_one_or_none()

        if not analysis:
            raise ValueError(f"Analysis {analysis_id} not found")

        analysis.add_why(why_question, answer, evidence)
        await self.db.commit()
        await self.db.refresh(analysis)
        return analysis

    async def set_root_cause(
        self,
        analysis_id: int,
        primary_root_cause: str,
        contributing_factors: Optional[List[str]] = None,
    ) -> FiveWhysAnalysis:
        """Set the root cause for an analysis."""
        result = await self.db.execute(select(FiveWhysAnalysis).where(FiveWhysAnalysis.id == analysis_id))
        analysis = result.scalar_one_or_none()

        if not analysis:
            raise ValueError(f"Analysis {analysis_id} not found")

        analysis.primary_root_cause = primary_root_cause
        analysis.contributing_factors = contributing_factors
        analysis.root_causes = [primary_root_cause] + (contributing_factors or [])

        await self.db.commit()
        await self.db.refresh(analysis)
        return analysis

    async def complete_analysis(
        self,
        analysis_id: int,
        user_id: int,
        proposed_actions: Optional[List[Dict]] = None,
    ) -> FiveWhysAnalysis:
        """Mark analysis as complete."""
        result = await self.db.execute(select(FiveWhysAnalysis).where(FiveWhysAnalysis.id == analysis_id))
        analysis = result.scalar_one_or_none()

        if not analysis:
            raise ValueError(f"Analysis {analysis_id} not found")

        analysis.completed = True
        analysis.completed_at = datetime.utcnow()
        analysis.completed_by_id = user_id
        analysis.proposed_actions = proposed_actions

        await self.db.commit()
        await self.db.refresh(analysis)
        return analysis

    async def get_analysis(self, analysis_id: int) -> Optional[FiveWhysAnalysis]:
        """Get an analysis by ID."""
        result = await self.db.execute(select(FiveWhysAnalysis).where(FiveWhysAnalysis.id == analysis_id))
        return result.scalar_one_or_none()

    async def get_analyses_for_entity(
        self,
        entity_type: str,
        entity_id: int,
    ) -> List[FiveWhysAnalysis]:
        """Get all 5-Whys analyses for an entity."""
        result = await self.db.execute(
            select(FiveWhysAnalysis)
            .where(
                and_(
                    FiveWhysAnalysis.entity_type == entity_type,
                    FiveWhysAnalysis.entity_id == entity_id,
                )
            )
            .order_by(FiveWhysAnalysis.created_at.desc())
        )
        return list(result.scalars().all())


class FishboneService:
    """Service for Fishbone diagram analysis."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_diagram(
        self,
        effect_statement: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        investigation_id: Optional[int] = None,
    ) -> FishboneDiagram:
        """Create a new Fishbone diagram."""
        diagram = FishboneDiagram(
            effect_statement=effect_statement,
            entity_type=entity_type,
            entity_id=entity_id,
            investigation_id=investigation_id,
            causes={cat.value: [] for cat in FishboneCategory},
        )
        self.db.add(diagram)
        await self.db.commit()
        await self.db.refresh(diagram)
        return diagram

    async def add_cause(
        self,
        diagram_id: int,
        category: str,
        cause: str,
        sub_causes: Optional[List[str]] = None,
    ) -> FishboneDiagram:
        """Add a cause to a category."""
        result = await self.db.execute(select(FishboneDiagram).where(FishboneDiagram.id == diagram_id))
        diagram = result.scalar_one_or_none()

        if not diagram:
            raise ValueError(f"Diagram {diagram_id} not found")

        try:
            cat_enum = FishboneCategory(category)
        except ValueError:
            raise ValueError(f"Invalid category: {category}")

        diagram.add_cause(cat_enum, cause, sub_causes)
        await self.db.commit()
        await self.db.refresh(diagram)
        return diagram

    async def set_root_cause(
        self,
        diagram_id: int,
        root_cause: str,
        root_cause_category: str,
        primary_causes: Optional[List[str]] = None,
    ) -> FishboneDiagram:
        """Set the root cause determination."""
        result = await self.db.execute(select(FishboneDiagram).where(FishboneDiagram.id == diagram_id))
        diagram = result.scalar_one_or_none()

        if not diagram:
            raise ValueError(f"Diagram {diagram_id} not found")

        diagram.root_cause = root_cause
        diagram.root_cause_category = root_cause_category
        diagram.primary_causes = primary_causes

        await self.db.commit()
        await self.db.refresh(diagram)
        return diagram

    async def complete_diagram(
        self,
        diagram_id: int,
        user_id: int,
        proposed_actions: Optional[List[Dict]] = None,
    ) -> FishboneDiagram:
        """Mark diagram as complete."""
        result = await self.db.execute(select(FishboneDiagram).where(FishboneDiagram.id == diagram_id))
        diagram = result.scalar_one_or_none()

        if not diagram:
            raise ValueError(f"Diagram {diagram_id} not found")

        diagram.completed = True
        diagram.completed_at = datetime.utcnow()
        diagram.completed_by_id = user_id
        diagram.proposed_actions = proposed_actions

        await self.db.commit()
        await self.db.refresh(diagram)
        return diagram

    async def get_diagram(self, diagram_id: int) -> Optional[FishboneDiagram]:
        """Get a diagram by ID."""
        result = await self.db.execute(select(FishboneDiagram).where(FishboneDiagram.id == diagram_id))
        return result.scalar_one_or_none()

    async def get_diagrams_for_entity(
        self,
        entity_type: str,
        entity_id: int,
    ) -> List[FishboneDiagram]:
        """Get all Fishbone diagrams for an entity."""
        result = await self.db.execute(
            select(FishboneDiagram)
            .where(
                and_(
                    FishboneDiagram.entity_type == entity_type,
                    FishboneDiagram.entity_id == entity_id,
                )
            )
            .order_by(FishboneDiagram.created_at.desc())
        )
        return list(result.scalars().all())


class CAPAService:
    """Service for Corrective and Preventive Actions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_capa(
        self,
        action_type: str,
        title: str,
        description: str,
        root_cause_addressed: Optional[str] = None,
        five_whys_id: Optional[int] = None,
        fishbone_id: Optional[int] = None,
        investigation_id: Optional[int] = None,
        assigned_to_id: Optional[int] = None,
        due_date: Optional[datetime] = None,
        priority: str = "medium",
    ) -> CAPAItem:
        """Create a new CAPA item."""
        capa = CAPAItem(
            action_type=action_type,
            title=title,
            description=description,
            root_cause_addressed=root_cause_addressed,
            five_whys_id=five_whys_id,
            fishbone_id=fishbone_id,
            investigation_id=investigation_id,
            assigned_to_id=assigned_to_id,
            due_date=due_date,
            priority=priority,
            status="open",
        )
        self.db.add(capa)
        await self.db.commit()
        await self.db.refresh(capa)
        return capa

    async def update_status(
        self,
        capa_id: int,
        status: str,
        notes: Optional[str] = None,
    ) -> CAPAItem:
        """Update CAPA status."""
        result = await self.db.execute(select(CAPAItem).where(CAPAItem.id == capa_id))
        capa = result.scalar_one_or_none()

        if not capa:
            raise ValueError(f"CAPA {capa_id} not found")

        capa.status = status
        if status == "completed":
            capa.completed_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(capa)
        return capa

    async def verify_capa(
        self,
        capa_id: int,
        user_id: int,
        verification_notes: Optional[str] = None,
        is_effective: bool = True,
    ) -> CAPAItem:
        """Verify a CAPA has been completed effectively."""
        result = await self.db.execute(select(CAPAItem).where(CAPAItem.id == capa_id))
        capa = result.scalar_one_or_none()

        if not capa:
            raise ValueError(f"CAPA {capa_id} not found")

        capa.verified_at = datetime.utcnow()
        capa.verified_by_id = user_id
        capa.verification_notes = verification_notes
        capa.is_effective = is_effective

        if is_effective:
            capa.status = "verified"

        await self.db.commit()
        await self.db.refresh(capa)
        return capa

    async def get_capas_for_investigation(
        self,
        investigation_id: int,
    ) -> List[CAPAItem]:
        """Get all CAPAs for an investigation."""
        result = await self.db.execute(
            select(CAPAItem).where(CAPAItem.investigation_id == investigation_id).order_by(CAPAItem.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_overdue_capas(self) -> List[CAPAItem]:
        """Get all overdue CAPA items."""
        now = datetime.utcnow()
        result = await self.db.execute(
            select(CAPAItem)
            .where(
                and_(
                    CAPAItem.due_date < now,
                    CAPAItem.status.in_(["open", "in_progress"]),
                )
            )
            .order_by(CAPAItem.due_date)
        )
        return list(result.scalars().all())
