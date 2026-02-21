"""Risk statistics and matrix aggregation service."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.risk import Risk, RiskStatus
from src.domain.services.risk_scoring import calculate_risk_level


class RiskStatisticsService:
    """Aggregation logic for operational-risk statistics and the risk matrix."""

    @staticmethod
    async def get_risk_statistics(db: AsyncSession, tenant_id: int) -> dict:
        """Compute risk register statistics for a tenant.

        Returns a dict matching the ``RiskStatistics`` schema with keys:
        total_risks, active_risks, risks_by_category, risks_by_level,
        risks_requiring_review, overdue_treatments, average_risk_score.
        """
        tenant_filter = Risk.tenant_id == tenant_id

        total_result = await db.execute(select(func.count()).select_from(Risk).where(tenant_filter))
        total_risks = total_result.scalar() or 0

        active_result = await db.execute(
            select(func.count()).select_from(Risk).where(Risk.is_active == True, tenant_filter)
        )
        active_risks = active_result.scalar() or 0

        category_result = await db.execute(
            select(Risk.category, func.count()).where(Risk.is_active == True, tenant_filter).group_by(Risk.category)
        )
        risks_by_category = {row[0] or "uncategorized": row[1] for row in category_result.all()}

        level_result = await db.execute(
            select(Risk.risk_level, func.count()).where(Risk.is_active == True, tenant_filter).group_by(Risk.risk_level)
        )
        risks_by_level = {row[0] or "unknown": row[1] for row in level_result.all()}

        review_result = await db.execute(
            select(func.count())
            .select_from(Risk)
            .where(
                and_(
                    Risk.is_active == True,
                    Risk.next_review_date <= datetime.now(timezone.utc),
                    tenant_filter,
                )
            )
        )
        risks_requiring_review = review_result.scalar() or 0

        overdue_result = await db.execute(
            select(func.count())
            .select_from(Risk)
            .where(
                and_(
                    Risk.is_active == True,
                    Risk.treatment_due_date <= datetime.now(timezone.utc),
                    Risk.status != RiskStatus.CLOSED,
                    tenant_filter,
                )
            )
        )
        overdue_treatments = overdue_result.scalar() or 0

        avg_result = await db.execute(select(func.avg(Risk.risk_score)).where(Risk.is_active == True, tenant_filter))
        average_risk_score = float(avg_result.scalar() or 0)

        return {
            "total_risks": total_risks,
            "active_risks": active_risks,
            "risks_by_category": risks_by_category,
            "risks_by_level": risks_by_level,
            "risks_requiring_review": risks_requiring_review,
            "overdue_treatments": overdue_treatments,
            "average_risk_score": round(average_risk_score, 2),
        }

    @staticmethod
    async def get_risk_matrix(db: AsyncSession, tenant_id: int) -> dict:
        """Build the 5x5 risk matrix with per-cell risk counts.

        Returns a dict matching the ``RiskMatrixResponse`` schema with keys:
        matrix, total_risks, risks_by_level.
        """
        from src.api.schemas.risk import RiskMatrixCell

        result = await db.execute(
            select(Risk.likelihood, Risk.impact, func.count())
            .where(Risk.is_active == True, Risk.tenant_id == tenant_id)
            .group_by(Risk.likelihood, Risk.impact)
        )
        risk_counts = {(row[0], row[1]): row[2] for row in result.all()}

        matrix: list[list[RiskMatrixCell]] = []
        risks_by_level = {"very_low": 0, "low": 0, "medium": 0, "high": 0, "critical": 0}
        total_risks = 0

        for likelihood in range(5, 0, -1):
            row: list[RiskMatrixCell] = []
            for impact in range(1, 6):
                score, level, color = calculate_risk_level(likelihood, impact)
                count = risk_counts.get((likelihood, impact), 0)

                row.append(
                    RiskMatrixCell(
                        likelihood=likelihood,
                        impact=impact,
                        score=score,
                        level=level,
                        color=color,
                        risk_count=count,
                    )
                )

                risks_by_level[level] += count
                total_risks += count
            matrix.append(row)

        return {
            "matrix": matrix,
            "total_risks": total_risks,
            "risks_by_level": risks_by_level,
        }
