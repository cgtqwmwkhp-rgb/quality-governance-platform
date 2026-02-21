"""Standards library domain service.

Extracts business logic from standards routes into a testable service class.
Raises domain exceptions instead of HTTPException.
"""

import logging
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.standard import Clause, Control, Standard
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)


class StandardService:
    """Handles CRUD for standards, clauses, and controls."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- Standard CRUD ----

    async def list_standards(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        is_active: Optional[bool] = True,
    ):
        """List standards with pagination and optional search/filter."""
        query = select(Standard)

        if search:
            search_filter = f"%{search}%"
            query = query.where(
                (Standard.code.ilike(search_filter))
                | (Standard.name.ilike(search_filter))
                | (Standard.full_name.ilike(search_filter))
            )
        if is_active is not None:
            query = query.where(Standard.is_active == is_active)

        query = query.order_by(Standard.code)
        params = PaginationParams(page=page, page_size=page_size)
        paginated = await paginate(self.db, query, params)
        track_metric("standards.accessed")
        return paginated

    async def create_standard(self, standard_data: BaseModel) -> Standard:
        """Create a new standard.

        Raises:
            ValueError: If a standard with the same code already exists.
        """
        data = standard_data.model_dump()
        result = await self.db.execute(select(Standard).where(Standard.code == data.get("code")))
        if result.scalar_one_or_none():
            raise ValueError("DUPLICATE_ENTITY")

        standard = Standard(**data)
        self.db.add(standard)
        await self.db.commit()
        await self.db.refresh(standard)
        return standard

    async def get_standard(self, standard_id: int) -> Standard:
        """Get a standard by ID with clauses and controls eagerly loaded.

        Raises:
            LookupError: If the standard is not found.
        """
        result = await self.db.execute(
            select(Standard)
            .options(selectinload(Standard.clauses).selectinload(Clause.controls))
            .where(Standard.id == standard_id)
        )
        standard = result.scalar_one_or_none()
        if not standard:
            raise LookupError(f"Standard with ID {standard_id} not found")
        return standard

    async def update_standard(self, standard_id: int, standard_data: BaseModel) -> Standard:
        """Update a standard.

        Raises:
            LookupError: If the standard is not found.
        """
        standard = await self._get_standard_or_raise(standard_id)
        apply_updates(standard, standard_data, set_updated_at=False)
        await self.db.commit()
        await self.db.refresh(standard)
        return standard

    async def get_compliance_score(self, standard_id: int) -> dict[str, Any]:
        """Calculate compliance score for a standard based on control status."""
        standard = await self._get_standard_or_raise(standard_id)

        control_query = (
            select(Control)
            .join(Clause, Control.clause_id == Clause.id)
            .where(Clause.standard_id == standard_id)
            .where(Control.is_active == True)
            .where(Control.is_applicable == True)
        )
        control_result = await self.db.execute(control_query)
        controls: list[Control] = list(control_result.scalars().all())
        total_controls = len(controls)

        if total_controls == 0:
            return {
                "standard_id": standard_id,
                "standard_code": standard.code,
                "total_controls": 0,
                "implemented_count": 0,
                "partial_count": 0,
                "not_implemented_count": 0,
                "compliance_percentage": 0,
                "setup_required": True,
            }

        implemented_count = sum(1 for c in controls if c.implementation_status == "implemented")
        partial_count = sum(1 for c in controls if c.implementation_status == "partial")
        not_implemented_count = total_controls - implemented_count - partial_count
        compliance_percentage = round((implemented_count + 0.5 * partial_count) / total_controls * 100)

        return {
            "standard_id": standard_id,
            "standard_code": standard.code,
            "total_controls": total_controls,
            "implemented_count": implemented_count,
            "partial_count": partial_count,
            "not_implemented_count": not_implemented_count,
            "compliance_percentage": compliance_percentage,
            "setup_required": False,
        }

    async def list_standard_controls(self, standard_id: int) -> list[dict[str, Any]]:
        """List all controls for a standard (flat view).

        Raises:
            LookupError: If the standard is not found.
        """
        await self._get_standard_or_raise(standard_id)

        query = (
            select(Control, Clause.clause_number, Clause.sort_order)
            .join(Clause, Control.clause_id == Clause.id)
            .where(Clause.standard_id == standard_id)
            .where(Control.is_active == True)
            .order_by(
                Clause.sort_order,
                Clause.clause_number,
                Control.control_number,
                Control.id,
            )
        )
        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "id": control.id,
                "clause_id": control.clause_id,
                "clause_number": clause_number,
                "control_number": control.control_number,
                "title": control.title,
                "implementation_status": control.implementation_status,
                "is_applicable": control.is_applicable,
                "is_active": control.is_active,
            }
            for control, clause_number, _ in rows
        ]

    # ---- Clause CRUD ----

    async def list_clauses(
        self,
        standard_id: int,
        parent_clause_id: Optional[int] = None,
    ) -> list[Clause]:
        """List clauses for a standard.

        Raises:
            LookupError: If the standard is not found.
        """
        await self._get_standard_or_raise(standard_id)

        query = (
            select(Clause)
            .options(selectinload(Clause.controls))
            .where(Clause.standard_id == standard_id)
            .where(Clause.is_active == True)
        )

        if parent_clause_id is not None:
            query = query.where(Clause.parent_clause_id == parent_clause_id)
        else:
            query = query.where(Clause.parent_clause_id.is_(None))

        query = query.order_by(Clause.sort_order, Clause.clause_number)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_clause(self, standard_id: int, clause_data: BaseModel) -> Clause:
        """Create a new clause for a standard.

        Raises:
            LookupError: If the standard is not found.
        """
        await self._get_standard_or_raise(standard_id)

        clause = Clause(
            standard_id=standard_id,
            **clause_data.model_dump(exclude={"standard_id"}),
        )
        self.db.add(clause)
        await self.db.commit()

        result = await self.db.execute(
            select(Clause).options(selectinload(Clause.controls)).where(Clause.id == clause.id)
        )
        return result.scalar_one()

    async def get_clause(self, clause_id: int) -> Clause:
        """Get a clause by ID.

        Raises:
            LookupError: If the clause is not found.
        """
        result = await self.db.execute(
            select(Clause).options(selectinload(Clause.controls)).where(Clause.id == clause_id)
        )
        clause = result.scalar_one_or_none()
        if not clause:
            raise LookupError(f"Clause with ID {clause_id} not found")
        return clause

    async def update_clause(self, clause_id: int, clause_data: BaseModel) -> Clause:
        """Update a clause.

        Raises:
            LookupError: If the clause is not found.
        """
        clause = await self.get_clause(clause_id)
        apply_updates(clause, clause_data, set_updated_at=False)
        await self.db.commit()
        await self.db.refresh(clause)
        return clause

    # ---- Control CRUD ----

    async def create_control(self, clause_id: int, control_data: BaseModel) -> Control:
        """Create a new control for a clause.

        Raises:
            LookupError: If the clause is not found.
        """
        await self.get_clause(clause_id)

        control = Control(
            clause_id=clause_id,
            **control_data.model_dump(exclude={"clause_id"}),
        )
        self.db.add(control)
        await self.db.commit()
        await self.db.refresh(control)
        return control

    async def get_control(self, control_id: int) -> Control:
        """Get a control by ID.

        Raises:
            LookupError: If the control is not found.
        """
        result = await self.db.execute(select(Control).where(Control.id == control_id))
        control = result.scalar_one_or_none()
        if not control:
            raise LookupError(f"Control with ID {control_id} not found")
        return control

    async def update_control(self, control_id: int, control_data: BaseModel) -> Control:
        """Update a control.

        Raises:
            LookupError: If the control is not found.
        """
        control = await self.get_control(control_id)
        apply_updates(control, control_data, set_updated_at=False)
        await self.db.commit()
        await self.db.refresh(control)
        return control

    # ---- Helpers ----

    async def _get_standard_or_raise(self, standard_id: int) -> Standard:
        """Fetch a standard by ID or raise LookupError."""
        result = await self.db.execute(select(Standard).where(Standard.id == standard_id))
        standard = result.scalar_one_or_none()
        if not standard:
            raise LookupError(f"Standard with ID {standard_id} not found")
        return standard
