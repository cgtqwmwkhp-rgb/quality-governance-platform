"""
Enterprise Risk Management Service

Provides:
- Risk scoring (5x5 matrix)
- Heat map generation
- KRI monitoring
- Trend analysis & forecasting
- Bow-tie analysis support
"""

from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.risk_register import (
    BowTieElement,
    EnterpriseKeyRiskIndicator,
    EnterpriseRisk,
    EnterpriseRiskControl,
    RiskAppetiteStatement,
    RiskAssessmentHistory,
    RiskControlMapping,
)


class RiskScoringEngine:
    """5x5 Risk Matrix Scoring Engine"""

    LIKELIHOOD_LABELS = {
        1: "Rare",
        2: "Unlikely",
        3: "Possible",
        4: "Likely",
        5: "Almost Certain",
    }

    LIKELIHOOD_DESCRIPTIONS = {
        1: "May occur only in exceptional circumstances (<5% probability)",
        2: "Could occur but not expected (5-25% probability)",
        3: "Might occur at some time (25-50% probability)",
        4: "Will probably occur in most circumstances (50-75% probability)",
        5: "Expected to occur in most circumstances (>75% probability)",
    }

    IMPACT_LABELS = {
        1: "Insignificant",
        2: "Minor",
        3: "Moderate",
        4: "Major",
        5: "Catastrophic",
    }

    IMPACT_DESCRIPTIONS = {
        1: "No injury, minimal financial impact, no regulatory action",
        2: "First aid injury, <£10k loss, informal regulatory inquiry",
        3: "Medical treatment, £10k-100k loss, formal regulatory action",
        4: "Serious injury, £100k-1M loss, prosecution likely",
        5: "Fatality, >£1M loss, loss of license to operate",
    }

    @classmethod
    def calculate_score(cls, likelihood: int, impact: int) -> int:
        """Calculate risk score from likelihood and impact"""
        return likelihood * impact

    @classmethod
    def get_risk_level(cls, score: int) -> str:
        """Get risk level from score"""
        if score <= 4:
            return "low"
        elif score <= 9:
            return "medium"
        elif score <= 16:
            return "high"
        else:
            return "critical"

    @classmethod
    def get_risk_color(cls, score: int) -> str:
        """Get color code for risk score"""
        if score <= 4:
            return "#22c55e"  # Green
        elif score <= 9:
            return "#eab308"  # Yellow
        elif score <= 16:
            return "#f97316"  # Orange
        else:
            return "#ef4444"  # Red

    @classmethod
    def generate_matrix(cls) -> list[list[dict]]:
        """Generate full 5x5 matrix with scores and colors"""
        matrix = []
        for likelihood in range(5, 0, -1):  # 5 to 1 (top to bottom)
            row = []
            for impact in range(1, 6):  # 1 to 5 (left to right)
                score = cls.calculate_score(likelihood, impact)
                row.append(
                    {
                        "likelihood": likelihood,
                        "impact": impact,
                        "score": score,
                        "level": cls.get_risk_level(score),
                        "color": cls.get_risk_color(score),
                        "likelihood_label": cls.LIKELIHOOD_LABELS[likelihood],
                        "impact_label": cls.IMPACT_LABELS[impact],
                    }
                )
            matrix.append(row)
        return matrix


class RiskService:
    """Main Risk Management Service"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.scoring = RiskScoringEngine()

    async def create_risk(self, data: dict, created_by: Optional[int] = None) -> EnterpriseRisk:
        """Create a new risk with automatic scoring"""
        count = await self.db.scalar(select(func.count()).select_from(EnterpriseRisk)) or 0
        reference = f"RISK-{(count + 1):04d}"

        inherent_score = RiskScoringEngine.calculate_score(
            data.get("inherent_likelihood", 3), data.get("inherent_impact", 3)
        )
        residual_score = RiskScoringEngine.calculate_score(
            data.get("residual_likelihood", 2), data.get("residual_impact", 2)
        )

        appetite = (
            await self.db.execute(
                select(RiskAppetiteStatement).where(RiskAppetiteStatement.category == data.get("category"))
            )
        ).scalar_one_or_none()
        appetite_threshold = appetite.max_residual_score if appetite else 12

        risk = EnterpriseRisk(
            reference=reference,
            title=data.get("title"),
            description=data.get("description", ""),
            category=data.get("category", "operational"),
            subcategory=data.get("subcategory"),
            department=data.get("department"),
            location=data.get("location"),
            process=data.get("process"),
            inherent_likelihood=data.get("inherent_likelihood", 3),
            inherent_impact=data.get("inherent_impact", 3),
            inherent_score=inherent_score,
            residual_likelihood=data.get("residual_likelihood", 2),
            residual_impact=data.get("residual_impact", 2),
            residual_score=residual_score,
            risk_appetite=data.get("risk_appetite", "cautious"),
            appetite_threshold=appetite_threshold,
            is_within_appetite=residual_score <= appetite_threshold,
            treatment_strategy=data.get("treatment_strategy", "treat"),
            treatment_plan=data.get("treatment_plan"),
            risk_owner_id=data.get("risk_owner_id"),
            risk_owner_name=data.get("risk_owner_name"),
            tenant_id=data.get("tenant_id"),
            status="identified",
            review_frequency_days=data.get("review_frequency_days", 90),
            created_by=created_by,
        )

        risk.next_review_date = datetime.utcnow() + timedelta(days=risk.review_frequency_days)

        self.db.add(risk)
        await self.db.commit()
        await self.db.refresh(risk)

        await self._record_assessment(risk)

        return risk

    async def update_risk_assessment(
        self, risk_id: int, data: dict, assessed_by: Optional[int] = None
    ) -> EnterpriseRisk:
        """Update risk assessment scores"""
        risk = (await self.db.execute(select(EnterpriseRisk).where(EnterpriseRisk.id == risk_id))).scalar_one_or_none()
        if not risk:
            raise ValueError(f"Risk {risk_id} not found")

        if "inherent_likelihood" in data:
            risk.inherent_likelihood = data["inherent_likelihood"]
        if "inherent_impact" in data:
            risk.inherent_impact = data["inherent_impact"]
        if "residual_likelihood" in data:
            risk.residual_likelihood = data["residual_likelihood"]
        if "residual_impact" in data:
            risk.residual_impact = data["residual_impact"]

        risk.inherent_score = RiskScoringEngine.calculate_score(risk.inherent_likelihood, risk.inherent_impact)
        risk.residual_score = RiskScoringEngine.calculate_score(risk.residual_likelihood, risk.residual_impact)

        risk.is_within_appetite = risk.residual_score <= risk.appetite_threshold

        risk.last_review_date = datetime.utcnow()
        risk.next_review_date = datetime.utcnow() + timedelta(days=risk.review_frequency_days)

        if "review_notes" in data:
            risk.review_notes = data["review_notes"]

        await self.db.commit()
        await self.db.refresh(risk)

        await self._record_assessment(risk, assessed_by, data.get("assessment_notes"))

        return risk

    async def _record_assessment(
        self,
        risk: EnterpriseRisk,
        assessed_by: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Record assessment in history"""
        history = RiskAssessmentHistory(
            risk_id=risk.id,
            assessed_by=assessed_by,
            inherent_likelihood=risk.inherent_likelihood,
            inherent_impact=risk.inherent_impact,
            inherent_score=risk.inherent_score,
            residual_likelihood=risk.residual_likelihood,
            residual_impact=risk.residual_impact,
            residual_score=risk.residual_score,
            status=risk.status,
            treatment_strategy=risk.treatment_strategy,
            assessment_notes=notes,
        )
        self.db.add(history)
        await self.db.commit()

    async def get_heat_map_data(
        self, category: Optional[str] = None, department: Optional[str] = None
    ) -> dict[str, Any]:
        """Generate heat map data for visualization"""
        conditions = [EnterpriseRisk.status != "closed"]

        if category:
            conditions.append(EnterpriseRisk.category == category)
        if department:
            conditions.append(EnterpriseRisk.department == department)

        result = await self.db.execute(select(EnterpriseRisk).where(and_(*conditions)))
        risks = result.scalars().all()

        matrix = []
        for likelihood in range(5, 0, -1):
            row = []
            for impact in range(1, 6):
                cell_risks = [r for r in risks if r.residual_likelihood == likelihood and r.residual_impact == impact]
                score = RiskScoringEngine.calculate_score(likelihood, impact)
                row.append(
                    {
                        "likelihood": likelihood,
                        "impact": impact,
                        "score": score,
                        "level": RiskScoringEngine.get_risk_level(score),
                        "color": RiskScoringEngine.get_risk_color(score),
                        "risk_count": len(cell_risks),
                        "risk_ids": [r.id for r in cell_risks],
                        "risk_titles": [r.title[:30] for r in cell_risks[:5]],
                    }
                )
            matrix.append(row)

        total_risks = len(risks)
        critical_risks = len([r for r in risks if r.residual_score > 16])
        high_risks = len([r for r in risks if 12 < r.residual_score <= 16])
        outside_appetite = len([r for r in risks if not r.is_within_appetite])

        return {
            "matrix": matrix,
            "summary": {
                "total_risks": total_risks,
                "critical_risks": critical_risks,
                "high_risks": high_risks,
                "outside_appetite": outside_appetite,
                "average_inherent_score": (sum(r.inherent_score for r in risks) / total_risks if total_risks else 0),
                "average_residual_score": (sum(r.residual_score for r in risks) / total_risks if total_risks else 0),
            },
            "likelihood_labels": RiskScoringEngine.LIKELIHOOD_LABELS,
            "impact_labels": RiskScoringEngine.IMPACT_LABELS,
        }

    async def get_risk_trends(self, risk_id: Optional[int] = None, days: int = 365) -> list[dict[str, Any]]:
        """Get risk score trends over time"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        conditions = [RiskAssessmentHistory.assessment_date >= cutoff]
        if risk_id:
            conditions.append(RiskAssessmentHistory.risk_id == risk_id)

        result = await self.db.execute(
            select(RiskAssessmentHistory).where(and_(*conditions)).order_by(RiskAssessmentHistory.assessment_date)
        )
        history = result.scalars().all()

        monthly_data: dict[str, dict] = {}
        for h in history:
            month_key = h.assessment_date.strftime("%Y-%m")
            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    "month": month_key,
                    "inherent_scores": [],
                    "residual_scores": [],
                    "count": 0,
                }
            monthly_data[month_key]["inherent_scores"].append(h.inherent_score)
            monthly_data[month_key]["residual_scores"].append(h.residual_score)
            monthly_data[month_key]["count"] += 1

        trends = []
        for month, data in sorted(monthly_data.items()):
            trends.append(
                {
                    "month": month,
                    "avg_inherent": sum(data["inherent_scores"]) / len(data["inherent_scores"]),
                    "avg_residual": sum(data["residual_scores"]) / len(data["residual_scores"]),
                    "assessment_count": data["count"],
                }
            )

        return trends

    async def forecast_risk_trends(self, months_ahead: int = 6) -> list[dict[str, Any]]:
        """Simple linear forecast of risk trends"""
        historical = await self.get_risk_trends(days=365)

        if len(historical) < 3:
            return []

        x = list(range(len(historical)))
        y = [h["avg_residual"] for h in historical]

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi**2 for xi in x)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x**2) if (n * sum_x2 - sum_x**2) != 0 else 0
        intercept = (sum_y - slope * sum_x) / n

        forecast = []
        last_month = datetime.strptime(historical[-1]["month"], "%Y-%m")

        for i in range(1, months_ahead + 1):
            future_month = last_month + timedelta(days=30 * i)
            future_x = len(historical) + i - 1
            predicted = max(0, min(25, intercept + slope * future_x))  # Bound 0-25

            forecast.append(
                {
                    "month": future_month.strftime("%Y-%m"),
                    "predicted_residual": round(predicted, 2),
                    "confidence_lower": round(max(0, predicted - 2), 2),
                    "confidence_upper": round(min(25, predicted + 2), 2),
                    "is_forecast": True,
                }
            )

        return forecast


class KRIService:
    """Key Risk Indicator Monitoring Service"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_kri_value(self, kri_id: int, new_value: float) -> EnterpriseKeyRiskIndicator:
        """Update KRI with new value and check thresholds"""
        kri = (
            await self.db.execute(select(EnterpriseKeyRiskIndicator).where(EnterpriseKeyRiskIndicator.id == kri_id))
        ).scalar_one_or_none()
        if not kri:
            raise ValueError(f"KRI {kri_id} not found")

        if kri.historical_values is None:
            kri.historical_values = []

        kri.historical_values.append({"value": new_value, "date": datetime.utcnow().isoformat()})

        kri.current_value = new_value
        kri.last_updated = datetime.utcnow()

        if kri.threshold_direction == "above":
            if new_value >= kri.red_threshold:
                kri.current_status = "red"
            elif new_value >= kri.amber_threshold:
                kri.current_status = "amber"
            else:
                kri.current_status = "green"
        else:  # below
            if new_value <= kri.red_threshold:
                kri.current_status = "red"
            elif new_value <= kri.amber_threshold:
                kri.current_status = "amber"
            else:
                kri.current_status = "green"

        await self.db.commit()
        await self.db.refresh(kri)

        return kri

    async def get_kri_dashboard(self) -> dict[str, Any]:
        """Get KRI dashboard summary"""
        result = await self.db.execute(
            select(EnterpriseKeyRiskIndicator).where(EnterpriseKeyRiskIndicator.is_active == True)  # noqa: E712
        )
        kris = result.scalars().all()

        return {
            "total_kris": len(kris),
            "red_count": len([k for k in kris if k.current_status == "red"]),
            "amber_count": len([k for k in kris if k.current_status == "amber"]),
            "green_count": len([k for k in kris if k.current_status == "green"]),
            "kris": [
                {
                    "id": k.id,
                    "name": k.name,
                    "risk_id": k.risk_id,
                    "current_value": k.current_value,
                    "status": k.current_status,
                    "green_threshold": k.green_threshold,
                    "amber_threshold": k.amber_threshold,
                    "red_threshold": k.red_threshold,
                    "last_updated": (k.last_updated.isoformat() if k.last_updated else None),
                    "trend": (self._calculate_trend(k.historical_values) if k.historical_values else "stable"),
                }
                for k in kris
            ],
        }

    def _calculate_trend(self, historical: list) -> str:
        """Calculate trend from historical values"""
        if len(historical) < 2:
            return "stable"

        recent = historical[-3:] if len(historical) >= 3 else historical
        values = [h["value"] for h in recent]

        if values[-1] > values[0] * 1.1:
            return "increasing"
        elif values[-1] < values[0] * 0.9:
            return "decreasing"
        return "stable"


class BowTieService:
    """Bow-Tie Analysis Service"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_bow_tie(self, risk_id: int) -> dict[str, Any]:
        """Get bow-tie diagram data for a risk"""
        risk = (await self.db.execute(select(EnterpriseRisk).where(EnterpriseRisk.id == risk_id))).scalar_one_or_none()
        if not risk:
            raise ValueError(f"Risk {risk_id} not found")

        bt_result = await self.db.execute(
            select(BowTieElement)
            .where(BowTieElement.risk_id == risk_id)
            .order_by(BowTieElement.position, BowTieElement.order_index)
        )
        elements = bt_result.scalars().all()

        causes = [e for e in elements if e.element_type == "cause"]
        consequences = [e for e in elements if e.element_type == "consequence"]
        prevention_barriers = [e for e in elements if e.element_type == "prevention"]
        mitigation_barriers = [e for e in elements if e.element_type == "mitigation"]
        escalation_factors = [e for e in elements if e.is_escalation_factor]

        mapping_result = await self.db.execute(select(RiskControlMapping).where(RiskControlMapping.risk_id == risk_id))
        control_mappings = mapping_result.scalars().all()
        control_ids = [m.control_id for m in control_mappings]
        if control_ids:
            ctrl_result = await self.db.execute(
                select(EnterpriseRiskControl).where(EnterpriseRiskControl.id.in_(control_ids))
            )
            controls = ctrl_result.scalars().all()
        else:
            controls = []

        return {
            "risk": {
                "id": risk.id,
                "reference": risk.reference,
                "title": risk.title,
                "description": risk.description,
                "category": risk.category,
                "inherent_score": risk.inherent_score,
                "residual_score": risk.residual_score,
            },
            "causes": [{"id": c.id, "title": c.title, "description": c.description} for c in causes],
            "prevention_barriers": [
                {
                    "id": b.id,
                    "title": b.title,
                    "barrier_type": b.barrier_type,
                    "effectiveness": b.effectiveness,
                    "linked_control_id": b.linked_control_id,
                }
                for b in prevention_barriers
            ],
            "consequences": [{"id": c.id, "title": c.title, "description": c.description} for c in consequences],
            "mitigation_barriers": [
                {
                    "id": b.id,
                    "title": b.title,
                    "barrier_type": b.barrier_type,
                    "effectiveness": b.effectiveness,
                    "linked_control_id": b.linked_control_id,
                }
                for b in mitigation_barriers
            ],
            "escalation_factors": [
                {"id": e.id, "title": e.title, "description": e.description} for e in escalation_factors
            ],
            "controls": [
                {
                    "id": c.id,
                    "reference": c.reference,
                    "name": c.name,
                    "control_type": c.control_type,
                    "effectiveness": c.effectiveness,
                }
                for c in controls
            ],
        }

    async def add_bow_tie_element(
        self,
        risk_id: int,
        element_type: str,
        title: str,
        description: Optional[str] = None,
        **kwargs: Any,
    ) -> BowTieElement:
        """Add element to bow-tie diagram"""
        position = "left" if element_type in ("cause", "prevention") else "right"

        max_order = await self.db.scalar(
            select(func.max(BowTieElement.order_index)).where(
                and_(
                    BowTieElement.risk_id == risk_id,
                    BowTieElement.element_type == element_type,
                )
            )
        )
        max_order = max_order or 0

        element = BowTieElement(
            risk_id=risk_id,
            element_type=element_type,
            position=position,
            title=title,
            description=description,
            order_index=max_order + 1,
            barrier_type=kwargs.get("barrier_type"),
            linked_control_id=kwargs.get("linked_control_id"),
            effectiveness=kwargs.get("effectiveness"),
            is_escalation_factor=kwargs.get("is_escalation_factor", False),
        )

        self.db.add(element)
        await self.db.commit()
        await self.db.refresh(element)

        return element
