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

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

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

    def __init__(self, db: Session):
        self.db = db
        self.scoring = RiskScoringEngine()

    def create_risk(self, data: dict, created_by: Optional[int] = None) -> EnterpriseRisk:
        """Create a new risk with automatic scoring"""
        # Generate reference
        count = self.db.query(EnterpriseRisk).count()
        reference = f"RISK-{(count + 1):04d}"

        # Calculate scores
        inherent_score = RiskScoringEngine.calculate_score(
            data.get("inherent_likelihood", 3), data.get("inherent_impact", 3)
        )
        residual_score = RiskScoringEngine.calculate_score(
            data.get("residual_likelihood", 2), data.get("residual_impact", 2)
        )

        # Get appetite threshold for category
        appetite = (
            self.db.query(RiskAppetiteStatement).filter(RiskAppetiteStatement.category == data.get("category")).first()
        )
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
            status="identified",
            review_frequency_days=data.get("review_frequency_days", 90),
            created_by=created_by,
        )

        # Set next review date
        risk.next_review_date = datetime.utcnow() + timedelta(days=risk.review_frequency_days)

        self.db.add(risk)
        self.db.commit()
        self.db.refresh(risk)

        # Create initial assessment history
        self._record_assessment(risk)

        return risk

    def update_risk_assessment(self, risk_id: int, data: dict, assessed_by: Optional[int] = None) -> EnterpriseRisk:
        """Update risk assessment scores"""
        risk = self.db.query(EnterpriseRisk).filter(EnterpriseRisk.id == risk_id).first()
        if not risk:
            raise ValueError(f"Risk {risk_id} not found")

        # Update scores
        if "inherent_likelihood" in data:
            risk.inherent_likelihood = data["inherent_likelihood"]
        if "inherent_impact" in data:
            risk.inherent_impact = data["inherent_impact"]
        if "residual_likelihood" in data:
            risk.residual_likelihood = data["residual_likelihood"]
        if "residual_impact" in data:
            risk.residual_impact = data["residual_impact"]

        # Recalculate scores
        risk.inherent_score = RiskScoringEngine.calculate_score(risk.inherent_likelihood, risk.inherent_impact)
        risk.residual_score = RiskScoringEngine.calculate_score(risk.residual_likelihood, risk.residual_impact)

        # Check appetite
        risk.is_within_appetite = risk.residual_score <= risk.appetite_threshold

        # Update review dates
        risk.last_review_date = datetime.utcnow()
        risk.next_review_date = datetime.utcnow() + timedelta(days=risk.review_frequency_days)

        if "review_notes" in data:
            risk.review_notes = data["review_notes"]

        self.db.commit()
        self.db.refresh(risk)

        # Record assessment history
        self._record_assessment(risk, assessed_by, data.get("assessment_notes"))

        return risk

    def _record_assessment(
        self, risk: EnterpriseRisk, assessed_by: Optional[int] = None, notes: Optional[str] = None
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
        self.db.commit()

    def get_heat_map_data(self, category: Optional[str] = None, department: Optional[str] = None) -> dict[str, Any]:
        """Generate heat map data for visualization"""
        query = self.db.query(EnterpriseRisk).filter(EnterpriseRisk.status != "closed")

        if category:
            query = query.filter(EnterpriseRisk.category == category)
        if department:
            query = query.filter(EnterpriseRisk.department == department)

        risks = query.all()

        # Build matrix with risk counts
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

        # Summary stats
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

    def get_risk_trends(self, risk_id: Optional[int] = None, days: int = 365) -> list[dict[str, Any]]:
        """Get risk score trends over time"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        query = self.db.query(RiskAssessmentHistory).filter(RiskAssessmentHistory.assessment_date >= cutoff)

        if risk_id:
            query = query.filter(RiskAssessmentHistory.risk_id == risk_id)

        history = query.order_by(RiskAssessmentHistory.assessment_date).all()

        # Group by month
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

        # Calculate averages
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

    def forecast_risk_trends(self, months_ahead: int = 6) -> list[dict[str, Any]]:
        """Simple linear forecast of risk trends"""
        historical = self.get_risk_trends(days=365)

        if len(historical) < 3:
            return []

        # Simple linear regression on residual scores
        x = list(range(len(historical)))
        y = [h["avg_residual"] for h in historical]

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi**2 for xi in x)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x**2) if (n * sum_x2 - sum_x**2) != 0 else 0
        intercept = (sum_y - slope * sum_x) / n

        # Generate forecast
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

    def __init__(self, db: Session):
        self.db = db

    def update_kri_value(self, kri_id: int, new_value: float) -> EnterpriseKeyRiskIndicator:
        """Update KRI with new value and check thresholds"""
        kri = self.db.query(EnterpriseKeyRiskIndicator).filter(EnterpriseKeyRiskIndicator.id == kri_id).first()
        if not kri:
            raise ValueError(f"KRI {kri_id} not found")

        # Store historical value
        if kri.historical_values is None:
            kri.historical_values = []

        kri.historical_values.append({"value": new_value, "date": datetime.utcnow().isoformat()})

        # Update current value
        kri.current_value = new_value
        kri.last_updated = datetime.utcnow()

        # Determine status
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

        self.db.commit()
        self.db.refresh(kri)

        return kri

    def get_kri_dashboard(self) -> dict[str, Any]:
        """Get KRI dashboard summary"""
        kris = self.db.query(EnterpriseKeyRiskIndicator).filter(EnterpriseKeyRiskIndicator.is_active == True).all()

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
                    "last_updated": k.last_updated.isoformat() if k.last_updated else None,
                    "trend": self._calculate_trend(k.historical_values) if k.historical_values else "stable",
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

    def __init__(self, db: Session):
        self.db = db

    def get_bow_tie(self, risk_id: int) -> dict[str, Any]:
        """Get bow-tie diagram data for a risk"""
        risk = self.db.query(EnterpriseRisk).filter(EnterpriseRisk.id == risk_id).first()
        if not risk:
            raise ValueError(f"Risk {risk_id} not found")

        elements = (
            self.db.query(BowTieElement)
            .filter(BowTieElement.risk_id == risk_id)
            .order_by(BowTieElement.position, BowTieElement.order_index)
            .all()
        )

        # Group elements
        causes = [e for e in elements if e.element_type == "cause"]
        consequences = [e for e in elements if e.element_type == "consequence"]
        prevention_barriers = [e for e in elements if e.element_type == "prevention"]
        mitigation_barriers = [e for e in elements if e.element_type == "mitigation"]
        escalation_factors = [e for e in elements if e.is_escalation_factor]

        # Get linked controls
        control_mappings = self.db.query(RiskControlMapping).filter(RiskControlMapping.risk_id == risk_id).all()
        control_ids = [m.control_id for m in control_mappings]
        controls = (
            self.db.query(EnterpriseRiskControl).filter(EnterpriseRiskControl.id.in_(control_ids)).all()
            if control_ids
            else []
        )

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

    def add_bow_tie_element(
        self,
        risk_id: int,
        element_type: str,
        title: str,
        description: Optional[str] = None,
        **kwargs: Any,
    ) -> BowTieElement:
        """Add element to bow-tie diagram"""
        # Determine position based on type
        position = "left" if element_type in ("cause", "prevention") else "right"

        # Get next order index
        max_order = (
            self.db.query(func.max(BowTieElement.order_index))
            .filter(and_(BowTieElement.risk_id == risk_id, BowTieElement.element_type == element_type))
            .scalar()
            or 0
        )

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
        self.db.commit()
        self.db.refresh(element)

        return element
