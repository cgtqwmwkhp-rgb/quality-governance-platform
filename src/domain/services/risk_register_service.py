"""Enterprise risk register service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import ConflictError, NotFoundError
from src.domain.models.risk_register import (
    EnterpriseKeyRiskIndicator,
    EnterpriseRisk,
    EnterpriseRiskControl,
    RiskAppetiteStatement,
    RiskAssessmentHistory,
    RiskControlMapping,
)


class RiskRegisterService:
    """Aggregation and CRUD logic for the enterprise risk register."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Risk listing
    # ------------------------------------------------------------------

    def build_risk_list_query(
        self,
        tenant_id: int,
        *,
        category: str | None = None,
        department: str | None = None,
        status: str | None = None,
        min_score: int | None = None,
        outside_appetite: bool | None = None,
    ):
        """Return an un-executed *Select* for filtered risk listing."""
        conditions = [EnterpriseRisk.tenant_id == tenant_id]
        if category:
            conditions.append(EnterpriseRisk.category == category)
        if department:
            conditions.append(EnterpriseRisk.department == department)
        if status:
            conditions.append(EnterpriseRisk.status == status)
        if min_score:
            conditions.append(EnterpriseRisk.residual_score >= min_score)
        if outside_appetite:
            conditions.append(EnterpriseRisk.is_within_appetite == False)  # noqa: E712
        return select(EnterpriseRisk).where(and_(*conditions)).order_by(
            EnterpriseRisk.residual_score.desc()
        )

    # ------------------------------------------------------------------
    # Risk detail
    # ------------------------------------------------------------------

    async def get_risk_detail(
        self, risk_id: int, tenant_id: int
    ) -> dict[str, Any]:
        """Load a risk with controls, KRIs, and recent assessment history.

        Returns dict with keys: risk, controls, kris, assessment_history.
        Raises NotFoundError if the risk does not exist.
        """
        result = await self.db.execute(
            select(EnterpriseRisk).where(
                EnterpriseRisk.id == risk_id,
                EnterpriseRisk.tenant_id == tenant_id,
            )
        )
        risk = result.scalar_one_or_none()
        if not risk:
            raise NotFoundError(f"Risk {risk_id} not found")

        mapping_result = await self.db.execute(
            select(RiskControlMapping).where(RiskControlMapping.risk_id == risk_id)
        )
        control_ids = [m.control_id for m in mapping_result.scalars().all()]
        controls: list[EnterpriseRiskControl] = []
        if control_ids:
            ctrl_result = await self.db.execute(
                select(EnterpriseRiskControl).where(
                    EnterpriseRiskControl.id.in_(control_ids)
                )
            )
            controls = list(ctrl_result.scalars().all())

        kri_result = await self.db.execute(
            select(EnterpriseKeyRiskIndicator).where(
                EnterpriseKeyRiskIndicator.risk_id == risk_id
            )
        )
        kris = list(kri_result.scalars().all())

        hist_result = await self.db.execute(
            select(RiskAssessmentHistory)
            .where(RiskAssessmentHistory.risk_id == risk_id)
            .order_by(RiskAssessmentHistory.assessment_date.desc())
            .limit(10)
        )
        history = list(hist_result.scalars().all())

        return {
            "risk": risk,
            "controls": controls,
            "kris": kris,
            "assessment_history": history,
        }

    # ------------------------------------------------------------------
    # Risk mutations
    # ------------------------------------------------------------------

    async def update_risk(
        self, risk_id: int, tenant_id: int, updates: dict[str, Any]
    ) -> EnterpriseRisk:
        """Apply field-level updates to a risk (not scores)."""
        result = await self.db.execute(
            select(EnterpriseRisk).where(
                EnterpriseRisk.id == risk_id,
                EnterpriseRisk.tenant_id == tenant_id,
            )
        )
        risk = result.scalar_one_or_none()
        if not risk:
            raise NotFoundError(f"Risk {risk_id} not found")

        for field, value in updates.items():
            if value is not None and hasattr(risk, field):
                setattr(risk, field, value)

        await self.db.commit()
        await self.db.refresh(risk)
        return risk

    async def soft_delete_risk(self, risk_id: int, tenant_id: int) -> None:
        """Soft-delete by setting status to closed."""
        result = await self.db.execute(
            select(EnterpriseRisk).where(
                EnterpriseRisk.id == risk_id,
                EnterpriseRisk.tenant_id == tenant_id,
            )
        )
        risk = result.scalar_one_or_none()
        if not risk:
            raise NotFoundError(f"Risk {risk_id} not found")

        risk.status = "closed"
        risk.updated_at = datetime.now(timezone.utc)
        await self.db.commit()

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    async def list_controls(self) -> list[EnterpriseRiskControl]:
        """List all active risk controls."""
        result = await self.db.execute(
            select(EnterpriseRiskControl).where(
                EnterpriseRiskControl.is_active == True  # noqa: E712
            )
        )
        return list(result.scalars().all())

    async def create_control(
        self, data: dict[str, Any]
    ) -> EnterpriseRiskControl:
        """Create a control with auto-generated reference."""
        count = (
            await self.db.scalar(
                select(func.count()).select_from(EnterpriseRiskControl)
            )
            or 0
        )
        reference = f"CTRL-{(count + 1):04d}"
        control = EnterpriseRiskControl(reference=reference, **data)
        self.db.add(control)
        await self.db.commit()
        await self.db.refresh(control)
        return control

    async def link_control_to_risk(
        self,
        risk_id: int,
        control_id: int,
        tenant_id: int,
        *,
        reduces_likelihood: bool = True,
        reduces_impact: bool = False,
    ) -> RiskControlMapping:
        """Link a control to a risk; raises ConflictError on duplicate."""
        risk = (
            await self.db.execute(
                select(EnterpriseRisk).where(
                    EnterpriseRisk.id == risk_id,
                    EnterpriseRisk.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not risk:
            raise NotFoundError(f"Risk {risk_id} not found")

        ctrl = (
            await self.db.execute(
                select(EnterpriseRiskControl).where(
                    EnterpriseRiskControl.id == control_id,
                )
            )
        ).scalar_one_or_none()
        if not ctrl:
            raise NotFoundError(f"Control {control_id} not found")

        existing = (
            await self.db.execute(
                select(RiskControlMapping).where(
                    RiskControlMapping.risk_id == risk_id,
                    RiskControlMapping.control_id == control_id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise ConflictError("Control already linked to this risk")

        mapping = RiskControlMapping(
            risk_id=risk_id,
            control_id=control_id,
            reduces_likelihood=reduces_likelihood,
            reduces_impact=reduces_impact,
        )
        self.db.add(mapping)
        await self.db.commit()
        return mapping

    # ------------------------------------------------------------------
    # Appetite statements
    # ------------------------------------------------------------------

    async def list_appetite_statements(self) -> list[RiskAppetiteStatement]:
        """List active appetite statements."""
        result = await self.db.execute(
            select(RiskAppetiteStatement).where(
                RiskAppetiteStatement.is_active == True  # noqa: E712
            )
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    @staticmethod
    async def get_risk_summary(db: AsyncSession, tenant_id: int) -> dict:
        """Compute the overall risk register summary for a tenant.

        Returns a dict matching the ``RiskSummaryResponse`` schema with keys:
        total_risks, by_level, outside_appetite, overdue_review, escalated,
        by_category.
        """
        tenant_filter = EnterpriseRisk.tenant_id == tenant_id
        not_closed = EnterpriseRisk.status != "closed"

        total_risks = await db.scalar(select(func.count()).select_from(EnterpriseRisk).where(tenant_filter, not_closed))
        critical_risks = await db.scalar(
            select(func.count())
            .select_from(EnterpriseRisk)
            .where(tenant_filter, EnterpriseRisk.residual_score > 16, not_closed)
        )
        high_risks = await db.scalar(
            select(func.count())
            .select_from(EnterpriseRisk)
            .where(tenant_filter, EnterpriseRisk.residual_score.between(12, 16), not_closed)
        )
        medium_risks = await db.scalar(
            select(func.count())
            .select_from(EnterpriseRisk)
            .where(tenant_filter, EnterpriseRisk.residual_score.between(5, 11), not_closed)
        )
        low_risks = await db.scalar(
            select(func.count())
            .select_from(EnterpriseRisk)
            .where(tenant_filter, EnterpriseRisk.residual_score <= 4, not_closed)
        )
        outside_appetite = await db.scalar(
            select(func.count())
            .select_from(EnterpriseRisk)
            .where(tenant_filter, EnterpriseRisk.is_within_appetite == False, not_closed)  # noqa: E712
        )
        overdue_review = await db.scalar(
            select(func.count())
            .select_from(EnterpriseRisk)
            .where(tenant_filter, EnterpriseRisk.next_review_date < datetime.now(timezone.utc), not_closed)
        )
        escalated = await db.scalar(
            select(func.count())
            .select_from(EnterpriseRisk)
            .where(tenant_filter, EnterpriseRisk.is_escalated == True, not_closed)  # noqa: E712
        )

        result = await db.execute(
            select(EnterpriseRisk.category, func.count(EnterpriseRisk.id))
            .where(tenant_filter, not_closed)
            .group_by(EnterpriseRisk.category)
        )
        categories = result.all()

        return {
            "total_risks": total_risks,
            "by_level": {
                "critical": critical_risks,
                "high": high_risks,
                "medium": medium_risks,
                "low": low_risks,
            },
            "outside_appetite": outside_appetite,
            "overdue_review": overdue_review,
            "escalated": escalated,
            "by_category": {cat: count for cat, count in categories},
        }
