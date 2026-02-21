"""Enterprise risk register summary service."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.risk_register import EnterpriseRisk


class RiskRegisterService:
    """Aggregation logic for the enterprise risk register summary."""

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
            .where(tenant_filter, EnterpriseRisk.next_review_date < datetime.utcnow(), not_closed)
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
