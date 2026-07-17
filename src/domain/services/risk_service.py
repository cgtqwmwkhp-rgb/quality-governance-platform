"""
Enterprise Risk Management Service

Provides:
- Risk scoring (5x5 matrix)
- Heat map generation
- KRI monitoring
- Trend analysis & forecasting
- Bow-tie analysis support
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.risk_register import (
    BowTieElement,
    EnterpriseKeyRiskIndicator,
    EnterpriseRisk,
    EnterpriseRiskControl,
    RiskActivityEvent,
    RiskAppetiteStatement,
    RiskAssessmentHistory,
    RiskControlMapping,
    RiskNote,
)


def naive_utc_cutoff(days: int) -> datetime:
    """Naive UTC timestamp for comparisons against naive DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)


def naive_utc_now() -> datetime:
    """Current naive UTC timestamp for risk_register DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


ScoreTrend = str  # increasing | stable | decreasing

SCORE_TREND_TAG_KEY = "score_trend"

RISK_EVENT_ASSESSED = "assessed"
RISK_EVENT_NOTE_ADDED = "note_added"


def compute_net_score_trend(previous: Optional[int], current: int) -> ScoreTrend:
    """Derive residual-score direction from the last two net scores."""
    if previous is None:
        return "stable"
    if current > previous:
        return "increasing"
    if current < previous:
        return "decreasing"
    return "stable"


def read_score_trend_from_tags(tags: Optional[list | dict]) -> Optional[ScoreTrend]:
    """Read persisted score trend from the risk tags JSON blob."""
    if not isinstance(tags, dict):
        return None
    trend = tags.get(SCORE_TREND_TAG_KEY)
    if trend in {"increasing", "stable", "decreasing"}:
        return trend
    return None


def write_score_trend_to_tags(tags: Optional[list | dict], trend: ScoreTrend) -> dict:
    """Persist score trend in tags without a dedicated column (W1; no Alembic)."""
    merged = dict(tags) if isinstance(tags, dict) else {}
    merged[SCORE_TREND_TAG_KEY] = trend
    return merged


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

    # Canonical bands: low ≤4, medium 5–9, high 10–16, critical ≥17
    LEVEL_SCORE_RANGES = {
        "low": (1, 4),
        "medium": (5, 9),
        "high": (10, 16),
        "critical": (17, 25),
    }

    @classmethod
    def get_risk_level(cls, score: int) -> str:
        """Get risk level from score using canonical 5×5 bands."""
        if score <= 4:
            return "low"
        if score <= 9:
            return "medium"
        if score <= 16:
            return "high"
        return "critical"

    @classmethod
    def get_risk_color(cls, score: int) -> str:
        """Get color code for risk score (aligned with get_risk_level)."""
        level = cls.get_risk_level(score)
        return {
            "low": "#22c55e",
            "medium": "#eab308",
            "high": "#f97316",
            "critical": "#ef4444",
        }[level]

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
        stmt = select(func.count(EnterpriseRisk.id))
        if data.get("tenant_id") is not None:
            stmt = stmt.where(EnterpriseRisk.tenant_id == data["tenant_id"])
        count_result = await self.db.execute(stmt)
        count = count_result.scalar_one()
        reference = f"RISK-{(count + 1):04d}"

        inherent_score = RiskScoringEngine.calculate_score(
            data.get("inherent_likelihood", 3), data.get("inherent_impact", 3)
        )
        residual_score = RiskScoringEngine.calculate_score(
            data.get("residual_likelihood", 2), data.get("residual_impact", 2)
        )

        result = await self.db.execute(
            select(RiskAppetiteStatement).where(RiskAppetiteStatement.category == data.get("category"))
        )
        appetite = result.scalar_one_or_none()
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
            status="open",
            review_frequency_days=data.get("review_frequency_days", 90),
            created_by=created_by,
            tenant_id=data.get("tenant_id"),
        )

        risk.next_review_date = datetime.now(timezone.utc) + timedelta(days=risk.review_frequency_days)

        self.db.add(risk)
        await self.db.commit()
        await self.db.refresh(risk)

        from src.infrastructure.monitoring.azure_monitor import record_risk_created

        record_risk_created()

        await self._record_assessment(risk)

        return risk

    async def update_risk_assessment(
        self, risk_id: int, data: dict, assessed_by: Optional[int] = None
    ) -> EnterpriseRisk:
        """Update risk assessment scores and append history in one transaction."""
        result = await self.db.execute(select(EnterpriseRisk).where(EnterpriseRisk.id == risk_id))
        risk = result.scalar_one_or_none()
        if not risk:
            raise ValueError(f"Risk {risk_id} not found")

        prev_history = await self.db.execute(
            select(RiskAssessmentHistory.residual_score)
            .where(RiskAssessmentHistory.risk_id == risk_id)
            .order_by(RiskAssessmentHistory.assessment_date.desc())
            .limit(1)
        )
        previous_net_score = prev_history.scalar_one_or_none()

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

        now = naive_utc_now()
        if "last_review_date" in data and data["last_review_date"] is not None:
            risk.last_review_date = data["last_review_date"]
        else:
            risk.last_review_date = now

        if "next_review_date" in data and data["next_review_date"] is not None:
            risk.next_review_date = data["next_review_date"]
        else:
            risk.next_review_date = now + timedelta(days=risk.review_frequency_days)

        if "review_notes" in data:
            risk.review_notes = data["review_notes"]

        manual_trend = data.get("trend")
        if manual_trend in {"increasing", "stable", "decreasing"}:
            score_trend: ScoreTrend = manual_trend
        else:
            score_trend = compute_net_score_trend(previous_net_score, risk.residual_score)
        risk.tags = write_score_trend_to_tags(risk.tags, score_trend)

        risk.updated_at = now

        history = self._build_assessment_history(
            risk,
            assessed_by=assessed_by,
            notes=data.get("assessment_notes"),
        )
        self.db.add(history)

        activity = self._build_assessment_activity_event(
            risk,
            actor_id=assessed_by,
            score_trend=score_trend,
            previous_net_score=previous_net_score,
        )
        self.db.add(activity)

        await self.db.commit()
        await self.db.refresh(risk)

        return risk

    def _build_assessment_history(
        self,
        risk: EnterpriseRisk,
        assessed_by: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> RiskAssessmentHistory:
        """Build an assessment history row (caller adds + commits)."""
        return RiskAssessmentHistory(
            risk_id=risk.id,
            tenant_id=risk.tenant_id,
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

    def _build_assessment_activity_event(
        self,
        risk: EnterpriseRisk,
        *,
        actor_id: Optional[int],
        score_trend: ScoreTrend,
        previous_net_score: Optional[int],
    ) -> RiskActivityEvent:
        """Build an assess activity row (caller adds + commits)."""
        if actor_id is None:
            raise ValueError("actor_id is required for assessment activity events")
        summary = (
            f"Assessment saved — net score {risk.residual_score} "
            f"(trend {score_trend})"
        )
        payload: dict[str, Any] = {
            "inherent_score": risk.inherent_score,
            "residual_score": risk.residual_score,
            "previous_residual_score": previous_net_score,
            "trend": score_trend,
            "status": risk.status,
            "treatment_strategy": risk.treatment_strategy,
        }
        return RiskActivityEvent(
            tenant_id=risk.tenant_id,
            risk_id=risk.id,
            event_type=RISK_EVENT_ASSESSED,
            summary=summary,
            payload=payload,
            actor_id=actor_id,
        )

    async def append_risk_note(
        self,
        risk: EnterpriseRisk,
        *,
        body: str,
        created_by_id: int,
    ) -> RiskNote:
        """Append a note and matching activity event in one transaction."""
        note = RiskNote(
            tenant_id=risk.tenant_id,
            risk_id=risk.id,
            body=body,
            created_by_id=created_by_id,
            created_at=naive_utc_now(),
        )
        self.db.add(note)
        await self.db.flush()
        preview = body.strip()
        if len(preview) > 120:
            preview = f"{preview[:117]}..."
        activity = RiskActivityEvent(
            tenant_id=risk.tenant_id,
            risk_id=risk.id,
            event_type=RISK_EVENT_NOTE_ADDED,
            summary=f"Note added: {preview}",
            payload={"note_id": note.id},
            actor_id=created_by_id,
            created_at=naive_utc_now(),
        )
        self.db.add(activity)
        await self.db.commit()
        await self.db.refresh(note)
        return note

    async def _record_assessment(
        self,
        risk: EnterpriseRisk,
        assessed_by: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Record assessment in history (create path; separate commit)."""
        history = self._build_assessment_history(risk, assessed_by=assessed_by, notes=notes)
        self.db.add(history)
        await self.db.commit()

    @staticmethod
    def resolve_score_trend(
        risk: EnterpriseRisk,
        history: list[RiskAssessmentHistory],
    ) -> ScoreTrend:
        """Return persisted or computed net-score trend for profile/list surfaces."""
        stored = read_score_trend_from_tags(getattr(risk, "tags", None))
        if stored:
            return stored
        if len(history) >= 2:
            latest = history[0].residual_score
            prior = history[1].residual_score
            return compute_net_score_trend(prior, latest)
        if len(history) == 1:
            return "stable"
        return "stable"

    async def get_heat_map_data(
        self,
        category: Optional[str] = None,
        department: Optional[str] = None,
        status: Optional[str] = None,
        tenant_id: Optional[int] = None,
        score_type: str = "residual",
    ) -> dict[str, Any]:
        """Generate interactive heat map data (residual/inherent placement).

        score_type:
          - residual: place by residual L×I (default)
          - inherent: place by inherent L×I
          - delta: residual matrix + per-cell movers (inherent→residual)
        """
        if score_type not in {"residual", "inherent", "delta"}:
            score_type = "residual"

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stmt = select(EnterpriseRisk)
        if status:
            stmt = stmt.where(EnterpriseRisk.status == status)
        else:
            stmt = stmt.where(EnterpriseRisk.status != "closed")
        stmt = stmt.where(
            or_(
                EnterpriseRisk.suggestion_triage_status.is_(None),
                EnterpriseRisk.suggestion_triage_status == "accepted",
            )
        )
        if tenant_id is not None:
            stmt = stmt.where(EnterpriseRisk.tenant_id == tenant_id)
        if category:
            stmt = stmt.where(EnterpriseRisk.category == category)
        if department:
            stmt = stmt.where(EnterpriseRisk.department == department)

        result = await self.db.execute(stmt)
        risks = list(result.scalars().all())

        place_attr = "inherent" if score_type == "inherent" else "residual"
        buckets: dict[tuple[int, int], list[Any]] = {}
        for r in risks:
            lik = getattr(r, f"{place_attr}_likelihood")
            imp = getattr(r, f"{place_attr}_impact")
            if not (1 <= lik <= 5 and 1 <= imp <= 5):
                continue
            buckets.setdefault((lik, imp), []).append(r)

        max_count = max((len(v) for v in buckets.values()), default=1)

        # Appetite overlay threshold (default 12; max residual from any active statement)
        appetite_threshold = 12
        appetite_stmt = select(RiskAppetiteStatement).where(RiskAppetiteStatement.is_active == True)  # noqa: E712
        if tenant_id is not None:
            appetite_stmt = appetite_stmt.where(
                or_(
                    RiskAppetiteStatement.tenant_id == tenant_id,
                    RiskAppetiteStatement.tenant_id.is_(None),
                )
            )
        appetite_result = await self.db.execute(appetite_stmt)
        statements = list(appetite_result.scalars().all())
        thresholds = [s.max_residual_score for s in statements if s.max_residual_score is not None]
        if thresholds:
            appetite_threshold = min(thresholds)

        matrix = []
        for likelihood in range(5, 0, -1):
            row = []
            for impact in range(1, 6):
                cell_risks = buckets.get((likelihood, impact), [])
                # Stable rank: residual score desc for drawer
                cell_risks_sorted = sorted(cell_risks, key=lambda r: r.residual_score, reverse=True)
                score = RiskScoringEngine.calculate_score(likelihood, impact)
                risk_ids_all = [r.id for r in cell_risks_sorted]
                truncated = len(risk_ids_all) > 50
                risk_ids = risk_ids_all[:50]
                titles = [r.title for r in cell_risks_sorted[:8]]
                owners: list[str] = []
                for r in cell_risks_sorted:
                    name = (r.risk_owner_name or "").strip()
                    if name and name not in owners:
                        owners.append(name)
                    if len(owners) >= 3:
                        break
                overdue_count = sum(
                    1 for r in cell_risks_sorted if r.next_review_date is not None and r.next_review_date < now
                )
                outside_appetite_count = sum(1 for r in cell_risks_sorted if not r.is_within_appetite)
                intensity = (len(cell_risks_sorted) / max_count) if max_count else 0.0

                movers: list[dict[str, Any]] = []
                if score_type == "delta":
                    for r in cell_risks_sorted[:10]:
                        if r.inherent_likelihood != r.residual_likelihood or r.inherent_impact != r.residual_impact:
                            movers.append(
                                {
                                    "id": r.id,
                                    "title": r.title,
                                    "from": [r.inherent_likelihood, r.inherent_impact],
                                    "to": [r.residual_likelihood, r.residual_impact],
                                    "inherent_score": r.inherent_score,
                                    "residual_score": r.residual_score,
                                }
                            )

                row.append(
                    {
                        "likelihood": likelihood,
                        "impact": impact,
                        "score": score,
                        "level": RiskScoringEngine.get_risk_level(score),
                        "color": RiskScoringEngine.get_risk_color(score),
                        "risk_count": len(cell_risks_sorted),
                        "risk_ids": risk_ids,
                        "risk_ids_truncated": truncated,
                        "risk_titles": titles,
                        "owners_sample": owners,
                        "overdue_count": overdue_count,
                        "outside_appetite_count": outside_appetite_count,
                        "intensity": round(intensity, 3),
                        "above_appetite_band": score > appetite_threshold,
                        "movers": movers,
                    }
                )
            matrix.append(row)

        total_risks = len(risks)
        critical_risks = sum(1 for r in risks if RiskScoringEngine.get_risk_level(r.residual_score) == "critical")
        high_risks = sum(1 for r in risks if RiskScoringEngine.get_risk_level(r.residual_score) == "high")
        medium_risks = sum(1 for r in risks if RiskScoringEngine.get_risk_level(r.residual_score) == "medium")
        low_risks = sum(1 for r in risks if RiskScoringEngine.get_risk_level(r.residual_score) == "low")
        outside_appetite = sum(1 for r in risks if not r.is_within_appetite)

        # Compat flat cells for older clients
        cells = [
            {
                "likelihood": cell["likelihood"],
                "impact": cell["impact"],
                "count": cell["risk_count"],
                "risks": [
                    {"id": rid, "title": title}
                    for rid, title in zip(cell["risk_ids"], cell["risk_titles"], strict=False)
                ],
            }
            for row in matrix
            for cell in row
        ]

        return {
            "matrix": matrix,
            "cells": cells,
            "summary": {
                "total_risks": total_risks,
                "critical_risks": critical_risks,
                "high_risks": high_risks,
                "medium_risks": medium_risks,
                "low_risks": low_risks,
                "outside_appetite": outside_appetite,
                "average_inherent_score": (sum(r.inherent_score for r in risks) / total_risks if total_risks else 0),
                "average_residual_score": (sum(r.residual_score for r in risks) / total_risks if total_risks else 0),
            },
            "likelihood_labels": RiskScoringEngine.LIKELIHOOD_LABELS,
            "impact_labels": RiskScoringEngine.IMPACT_LABELS,
            "score_type": score_type if score_type != "delta" else "residual",
            "view_mode": score_type,
            "filters_applied": {
                "category": category,
                "department": department,
                "status": status,
                "score_type": score_type,
            },
            "appetite_overlay": {
                "threshold": appetite_threshold,
                "source": "risk_appetite_statements" if statements else "default",
            },
        }

    async def get_risk_trends(
        self,
        risk_id: Optional[int] = None,
        days: int = 365,
        tenant_id: Optional[int] = None,
        include_movers: bool = False,
    ) -> Union[list[dict[str, Any]], dict[str, Any]]:
        """Get risk score trends over time.

        When include_movers=True, returns {"series": [...], "top_movers": [...]} for board pack /
        executive sparklines. Default remains a list for backward compatibility.
        """
        # assessment_date is stored naive UTC; bind a naive cutoff so asyncpg
        # does not raise on aware-vs-naive comparisons (prod /trends 500).
        cutoff = naive_utc_cutoff(days)

        stmt = (
            select(RiskAssessmentHistory)
            .join(EnterpriseRisk, EnterpriseRisk.id == RiskAssessmentHistory.risk_id)
            .where(RiskAssessmentHistory.assessment_date >= cutoff)
        )
        if tenant_id is not None:
            stmt = stmt.where(EnterpriseRisk.tenant_id == tenant_id)
        if risk_id:
            stmt = stmt.where(RiskAssessmentHistory.risk_id == risk_id)

        stmt = stmt.order_by(RiskAssessmentHistory.assessment_date)
        result = await self.db.execute(stmt)
        history = result.scalars().all()

        monthly_data: dict[str, dict] = {}
        per_risk: dict[int, list[tuple[datetime, int]]] = {}
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
            per_risk.setdefault(h.risk_id, []).append((h.assessment_date, h.residual_score))

        trends = []
        for month, data in sorted(monthly_data.items()):
            inherent_scores = [s for s in data["inherent_scores"] if s is not None]
            residual_scores = [s for s in data["residual_scores"] if s is not None]
            trends.append(
                {
                    "month": month,
                    "avg_inherent": (sum(inherent_scores) / len(inherent_scores)) if inherent_scores else 0,
                    "avg_residual": (sum(residual_scores) / len(residual_scores)) if residual_scores else 0,
                    "assessment_count": data["count"],
                }
            )

        if not include_movers:
            return trends

        movers: list[dict[str, Any]] = []
        risk_ids = list(per_risk.keys())
        titles: dict[int, str] = {}
        if risk_ids:
            title_result = await self.db.execute(
                select(EnterpriseRisk.id, EnterpriseRisk.title).where(EnterpriseRisk.id.in_(risk_ids))
            )
            titles = {row[0]: row[1] for row in title_result.all()}
        for rid, points in per_risk.items():
            if len(points) < 2:
                continue
            points_sorted = sorted(points, key=lambda p: p[0])
            delta = points_sorted[-1][1] - points_sorted[0][1]
            movers.append(
                {
                    "id": rid,
                    "title": titles.get(rid, f"Risk {rid}"),
                    "from_score": points_sorted[0][1],
                    "to_score": points_sorted[-1][1],
                    "delta": delta,
                }
            )
        movers.sort(key=lambda m: abs(m["delta"]), reverse=True)
        return {"series": trends, "top_movers": movers[:10]}

    async def forecast_risk_trends(
        self,
        months_ahead: int = 6,
        tenant_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Simple linear forecast of risk trends"""
        historical = await self.get_risk_trends(days=365, tenant_id=tenant_id)

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
        result = await self.db.execute(
            select(EnterpriseKeyRiskIndicator).where(EnterpriseKeyRiskIndicator.id == kri_id)
        )
        kri = result.scalar_one_or_none()
        if not kri:
            raise ValueError(f"KRI {kri_id} not found")

        if kri.historical_values is None:
            kri.historical_values = []

        kri.historical_values.append({"value": new_value, "date": datetime.now(timezone.utc).isoformat()})

        kri.current_value = new_value
        kri.last_updated = datetime.now(timezone.utc)

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

    async def get_kri_dashboard(self, tenant_id: Optional[int] = None) -> dict[str, Any]:
        """Get KRI dashboard summary"""
        stmt = select(EnterpriseKeyRiskIndicator).where(EnterpriseKeyRiskIndicator.is_active == True)  # noqa: E712
        if tenant_id is not None:
            stmt = stmt.join(EnterpriseRisk, EnterpriseRisk.id == EnterpriseKeyRiskIndicator.risk_id).where(
                EnterpriseRisk.tenant_id == tenant_id
            )

        result = await self.db.execute(stmt)
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
        result = await self.db.execute(select(EnterpriseRisk).where(EnterpriseRisk.id == risk_id))
        risk = result.scalar_one_or_none()
        if not risk:
            raise ValueError(f"Risk {risk_id} not found")

        result = await self.db.execute(
            select(BowTieElement)
            .where(BowTieElement.risk_id == risk_id)
            .order_by(BowTieElement.position, BowTieElement.order_index)
        )
        elements = result.scalars().all()

        causes = [e for e in elements if e.element_type == "cause"]
        consequences = [e for e in elements if e.element_type == "consequence"]
        prevention_barriers = [e for e in elements if e.element_type == "prevention"]
        mitigation_barriers = [e for e in elements if e.element_type == "mitigation"]
        escalation_factors = [e for e in elements if e.is_escalation_factor]

        result = await self.db.execute(select(RiskControlMapping).where(RiskControlMapping.risk_id == risk_id))
        control_mappings = result.scalars().all()
        control_ids = [m.control_id for m in control_mappings]

        if control_ids:
            result = await self.db.execute(
                select(EnterpriseRiskControl).where(EnterpriseRiskControl.id.in_(control_ids))
            )
            controls = result.scalars().all()
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

        max_order_result = await self.db.execute(
            select(func.max(BowTieElement.order_index)).where(
                and_(
                    BowTieElement.risk_id == risk_id,
                    BowTieElement.element_type == element_type,
                )
            )
        )
        max_order = max_order_result.scalar_one_or_none() or 0

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
            tenant_id=kwargs.get("tenant_id"),
        )

        self.db.add(element)
        await self.db.commit()
        await self.db.refresh(element)

        return element
