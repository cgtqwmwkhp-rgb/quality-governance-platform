"""
AI-Powered Predictive Analytics & Intelligence Service

Features:
- Incident Prediction (ML models)
- Root Cause Clustering
- Anomaly Detection
- Natural Language Analysis
- Recommendation Engine
"""

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings

# AI Integration
try:
    import anthropic  # type: ignore[import-not-found]  # TYPE-IGNORE: MYPY-OVERRIDE

    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False


class TextAnalyzer:
    """Natural Language Processing for incident descriptions"""

    # Common keywords for classification
    HAZARD_KEYWORDS = {
        "slip": "slips_trips_falls",
        "trip": "slips_trips_falls",
        "fall": "slips_trips_falls",
        "ladder": "working_at_height",
        "height": "working_at_height",
        "scaffold": "working_at_height",
        "chemical": "hazardous_substances",
        "fume": "hazardous_substances",
        "toxic": "hazardous_substances",
        "lifting": "manual_handling",
        "heavy": "manual_handling",
        "back": "manual_handling",
        "vehicle": "vehicle_incident",
        "car": "vehicle_incident",
        "van": "vehicle_incident",
        "traffic": "vehicle_incident",
        "electric": "electrical",
        "shock": "electrical",
        "cable": "electrical",
        "fire": "fire_explosion",
        "burn": "fire_explosion",
        "heat": "fire_explosion",
        "machinery": "machinery",
        "equipment": "machinery",
        "tool": "machinery",
        "noise": "noise_vibration",
        "vibration": "noise_vibration",
        "hand arm": "noise_vibration",
        "stress": "mental_health",
        "anxiety": "mental_health",
        "fatigue": "mental_health",
        "workload": "mental_health",
    }

    SEVERITY_INDICATORS = {
        "high": [
            "fatality",
            "fatal",
            "death",
            "amputation",
            "hospital",
            "critical",
            "severe",
            "major",
        ],
        "medium": [
            "injury",
            "medical",
            "treatment",
            "doctor",
            "broken",
            "fracture",
            "laceration",
        ],
        "low": ["first aid", "minor", "near miss", "close call", "slight", "bruise"],
    }

    @classmethod
    def extract_keywords(cls, text: str) -> list[str]:
        """Extract relevant keywords from text"""
        text_lower = text.lower()
        found_keywords = []

        for keyword, category in cls.HAZARD_KEYWORDS.items():
            if keyword in text_lower:
                found_keywords.append(category)

        return list(set(found_keywords))

    @classmethod
    def estimate_severity(cls, text: str) -> str:
        """Estimate severity from text description"""
        text_lower = text.lower()

        for severity, indicators in cls.SEVERITY_INDICATORS.items():
            for indicator in indicators:
                if indicator in text_lower:
                    return severity

        return "low"

    @classmethod
    def extract_entities(cls, text: str) -> dict[str, list[str]]:
        """Extract named entities from text"""
        entities: dict[str, list[str]] = {
            "locations": [],
            "equipment": [],
            "body_parts": [],
            "actions": [],
        }

        # Simple pattern matching for common entities
        location_patterns = [
            r"at (?:the )?([A-Z][a-z]+ ?(?:site|depot|office|warehouse|yard))",
            r"in (?:the )?([A-Z][a-z]+ ?(?:area|zone|room|building))",
        ]

        body_parts = [
            "head",
            "neck",
            "shoulder",
            "arm",
            "elbow",
            "wrist",
            "hand",
            "finger",
            "back",
            "chest",
            "hip",
            "leg",
            "knee",
            "ankle",
            "foot",
            "toe",
            "eye",
            "ear",
        ]

        text_lower = text.lower()
        for part in body_parts:
            if part in text_lower:
                entities["body_parts"].append(part)

        return entities


class AnomalyDetector:
    """Detect anomalies in incident patterns"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def detect_frequency_anomalies(
        self, entity: str, entity_type: str = "department", lookback_days: int = 90
    ) -> dict[str, Any]:
        """Detect if incident frequency is abnormal for an entity"""
        from src.domain.models.incident import Incident

        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        # Get incidents for this entity
        if entity_type == "department":
            result = await self.db.execute(
                select(Incident).where(and_(Incident.department == entity, Incident.reported_date >= cutoff))  # type: ignore[attr-defined]  # SA columns  # TYPE-IGNORE: MYPY-OVERRIDE
            )
            recent_incidents = result.scalars().all()
        elif entity_type == "location":
            result = await self.db.execute(
                select(Incident).where(
                    and_(
                        Incident.location.ilike(f"%{entity}%"),  # type: ignore[attr-defined]  # SA column  # TYPE-IGNORE: MYPY-OVERRIDE
                        Incident.reported_date >= cutoff,  # type: ignore[attr-defined]  # SA column  # TYPE-IGNORE: MYPY-OVERRIDE
                    )
                )
            )
            recent_incidents = result.scalars().all()
        else:
            recent_incidents = []

        # Calculate weekly frequency
        weeks: dict[str, int] = defaultdict(int)
        for inc in recent_incidents:
            if inc.reported_date:
                week_key = inc.reported_date.strftime("%Y-W%W")
                weeks[week_key] += 1

        if len(weeks) < 4:
            return {"is_anomaly": False, "reason": "Insufficient data"}

        values = list(weeks.values())
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev = variance**0.5 if variance > 0 else 0

        # Get current week count
        current_week = datetime.now(timezone.utc).strftime("%Y-W%W")
        current_count = weeks.get(current_week, 0)

        # Anomaly if > 2 standard deviations above mean
        threshold = mean + (2 * std_dev)
        is_anomaly = current_count > threshold and current_count > mean * 1.5

        return {
            "is_anomaly": is_anomaly,
            "entity": entity,
            "entity_type": entity_type,
            "current_count": current_count,
            "average": round(mean, 2),
            "threshold": round(threshold, 2),
            "std_dev": round(std_dev, 2),
            "severity": ("high" if current_count > mean * 2 else "medium" if is_anomaly else "low"),
            "message": (
                f"Incident frequency for {entity} is {current_count}, which is significantly above the average of {mean:.1f}"
                if is_anomaly
                else f"Incident frequency for {entity} is within normal range"
            ),
        }

    async def detect_pattern_anomalies(self, lookback_days: int = 30) -> list[dict[str, Any]]:
        """Detect unusual patterns across all incidents"""
        from src.domain.models.incident import Incident

        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        result = await self.db.execute(select(Incident).where(Incident.reported_date >= cutoff))  # type: ignore[attr-defined]  # SA column  # TYPE-IGNORE: MYPY-OVERRIDE
        recent = result.scalars().all()

        anomalies = []

        # Check for clustering by category
        category_counts: Counter = Counter()
        for inc in recent:
            if inc.category:  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                category_counts[inc.category] += 1  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE

        if category_counts:
            total = sum(category_counts.values())
            for category, count in category_counts.items():
                percentage = (count / total) * 100
                if percentage > 40:  # More than 40% in one category
                    anomalies.append(
                        {
                            "type": "category_clustering",
                            "category": category,
                            "percentage": round(percentage, 1),
                            "count": count,
                            "message": f"{percentage:.1f}% of incidents are {category} - investigate root cause",
                        }
                    )

        # Check for time-based patterns (e.g., all incidents on Monday)
        day_counts: Counter = Counter()
        hour_counts: Counter = Counter()
        for inc in recent:
            if inc.incident_date:
                day_counts[inc.incident_date.strftime("%A")] += 1
                hour_counts[inc.incident_date.hour] += 1

        if day_counts:
            total_days = sum(day_counts.values())
            for day, count in day_counts.items():
                percentage = (count / total_days) * 100
                if percentage > 30:  # More than 30% on one day
                    anomalies.append(
                        {
                            "type": "day_clustering",
                            "day": day,
                            "percentage": round(percentage, 1),
                            "count": count,
                            "message": f"{percentage:.1f}% of incidents occur on {day}s",
                        }
                    )

        return anomalies


class IncidentPredictor:
    """ML-based incident prediction"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def predict_risk_factors(self, lookback_days: int = 365) -> list[dict[str, Any]]:
        """Identify conditions that predict higher incident likelihood"""
        from src.domain.models.incident import Incident

        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        result = await self.db.execute(select(Incident).where(Incident.reported_date >= cutoff))  # type: ignore[attr-defined]  # SA column  # TYPE-IGNORE: MYPY-OVERRIDE
        incidents = result.scalars().all()

        if not incidents:
            return []

        risk_factors = []

        # Analyze by department
        dept_counts: Counter = Counter()
        for inc in incidents:
            if inc.department:
                dept_counts[inc.department] += 1

        total = len(incidents)
        for dept, count in dept_counts.most_common(5):
            risk_factors.append(
                {
                    "factor_type": "department",
                    "factor_value": dept,
                    "incident_count": count,
                    "percentage": round((count / total) * 100, 1),
                    "risk_level": "high" if (count / total) > 0.25 else "medium",
                }
            )

        # Analyze by time of day
        high_risk_hours: list[int] = []
        for hour in range(24):
            hour_incidents = [i for i in incidents if i.incident_date and i.incident_date.hour == hour]
            if len(hour_incidents) / max(total, 1) > 0.08:  # >8% in one hour
                high_risk_hours.append(hour)

        if high_risk_hours:
            risk_factors.append(
                {
                    "factor_type": "time_of_day",
                    "factor_value": f"{min(high_risk_hours)}:00 - {max(high_risk_hours) + 1}:00",
                    "high_risk_hours": high_risk_hours,
                    "risk_level": "medium",
                }
            )

        # Analyze by weather/season (if available)
        month_counts: Counter = Counter()
        for inc in incidents:
            if inc.incident_date:
                month_counts[inc.incident_date.month] += 1

        if month_counts:
            peak_month = month_counts.most_common(1)[0]
            month_names = [
                "",
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ]
            risk_factors.append(
                {
                    "factor_type": "seasonal",
                    "factor_value": month_names[peak_month[0]],
                    "incident_count": peak_month[1],
                    "risk_level": "low",
                }
            )

        return risk_factors

    async def get_similar_incidents(self, description: str, limit: int = 5) -> list[dict[str, Any]]:
        """Find similar past incidents using keyword matching"""
        from src.domain.models.incident import Incident

        keywords = TextAnalyzer.extract_keywords(description)
        if not keywords:
            return []

        # Simple keyword-based similarity
        result = await self.db.execute(
            select(Incident).where(Incident.description.isnot(None)).order_by(desc(Incident.reported_date)).limit(1000)  # type: ignore[attr-defined]  # SA columns  # TYPE-IGNORE: MYPY-OVERRIDE
        )
        all_incidents = result.scalars().all()

        scored = []
        for inc in all_incidents:
            if not inc.description:
                continue
            inc_keywords = TextAnalyzer.extract_keywords(inc.description)
            overlap = len(set(keywords) & set(inc_keywords))
            if overlap > 0:
                scored.append((inc, overlap))

        scored.sort(key=lambda x: x[1], reverse=True)

        return [
            {
                "id": inc.id,
                "title": inc.title,
                "description": inc.description[:200] if inc.description else "",
                "date": inc.incident_date.isoformat() if inc.incident_date else None,
                "category": inc.category,  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                "severity": inc.severity,
                "root_cause": inc.root_cause,
                "corrective_actions": inc.corrective_actions,  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                "similarity_score": score,
            }
            for inc, score in scored[:limit]
        ]


class RecommendationEngine:
    """AI-powered recommendation engine"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.claude_client = None
        if CLAUDE_AVAILABLE and settings.anthropic_api_key:
            self.claude_client = anthropic.Anthropic()

    def get_corrective_action_recommendations(
        self, incident_description: str, category: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Get recommended corrective actions based on incident"""
        # First try AI-powered recommendations
        if self.claude_client:
            try:
                return self._get_ai_recommendations(incident_description, category)
            except Exception:
                pass  # Fall back to rule-based

        # Rule-based recommendations
        return self._get_rule_based_recommendations(incident_description, category)

    def _get_ai_recommendations(self, description: str, category: Optional[str] = None) -> list[dict[str, Any]]:
        """Get recommendations from Claude AI"""
        prompt = f"""Analyze this workplace incident and provide 3-5 specific corrective action recommendations.

Incident Description: {description}
{f'Category: {category}' if category else ''}

For each recommendation, provide:
1. A clear action title
2. Detailed description of what needs to be done
3. Priority (high/medium/low)
4. Timeframe for completion
5. Who should be responsible

Format as JSON array with objects containing: title, description, priority, timeframe, responsible_role"""

        assert self.claude_client is not None
        message = self.claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse response
        try:
            content = message.content[0].text
            # Extract JSON from response
            json_match = re.search(r"\[[\s\S]*\]", content)
            if json_match:
                recommendations = json.loads(json_match.group())
                return recommendations
        except (json.JSONDecodeError, IndexError):
            pass

        return []

    def _get_rule_based_recommendations(self, description: str, category: Optional[str] = None) -> list[dict[str, Any]]:
        """Rule-based fallback recommendations"""
        keywords = TextAnalyzer.extract_keywords(description)

        recommendations = []

        # Generic recommendations based on keywords
        keyword_actions = {
            "slips_trips_falls": [
                {
                    "title": "Conduct floor condition assessment",
                    "description": "Inspect floor surfaces, drainage, and anti-slip treatments",
                    "priority": "high",
                    "timeframe": "24 hours",
                    "responsible_role": "Facilities Manager",
                },
                {
                    "title": "Review housekeeping procedures",
                    "description": "Update and communicate housekeeping standards",
                    "priority": "medium",
                    "timeframe": "1 week",
                    "responsible_role": "Team Leader",
                },
            ],
            "working_at_height": [
                {
                    "title": "Review working at height risk assessment",
                    "description": "Update risk assessment and safe system of work",
                    "priority": "high",
                    "timeframe": "Immediate",
                    "responsible_role": "H&S Manager",
                },
                {
                    "title": "Verify competency of personnel",
                    "description": "Check training records and certifications",
                    "priority": "high",
                    "timeframe": "24 hours",
                    "responsible_role": "Training Coordinator",
                },
            ],
            "manual_handling": [
                {
                    "title": "Review manual handling assessment",
                    "description": "Reassess task using TILE methodology",
                    "priority": "high",
                    "timeframe": "48 hours",
                    "responsible_role": "H&S Advisor",
                },
                {
                    "title": "Consider mechanical aids",
                    "description": "Evaluate options for reducing manual handling",
                    "priority": "medium",
                    "timeframe": "1 week",
                    "responsible_role": "Operations Manager",
                },
            ],
            "vehicle_incident": [
                {
                    "title": "Review driving standards",
                    "description": "Assess driver behavior and vehicle roadworthiness",
                    "priority": "high",
                    "timeframe": "Immediate",
                    "responsible_role": "Fleet Manager",
                },
                {
                    "title": "Consider telematics review",
                    "description": "Analyze vehicle data for patterns",
                    "priority": "medium",
                    "timeframe": "48 hours",
                    "responsible_role": "Fleet Manager",
                },
            ],
        }

        for keyword in keywords:
            if keyword in keyword_actions:
                recommendations.extend(keyword_actions[keyword])

        # Add generic recommendations if none found
        if not recommendations:
            recommendations = [
                {
                    "title": "Conduct incident investigation",
                    "description": "Perform thorough root cause analysis",
                    "priority": "high",
                    "timeframe": "48 hours",
                    "responsible_role": "H&S Manager",
                },
                {
                    "title": "Review relevant risk assessments",
                    "description": "Update risk assessments based on findings",
                    "priority": "medium",
                    "timeframe": "1 week",
                    "responsible_role": "Department Manager",
                },
                {
                    "title": "Communicate lessons learned",
                    "description": "Share findings with relevant personnel",
                    "priority": "medium",
                    "timeframe": "1 week",
                    "responsible_role": "H&S Manager",
                },
            ]

        return recommendations


class RootCauseAnalyzer:
    """AI-powered root cause analysis"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def cluster_incidents(self, lookback_days: int = 180) -> list[dict[str, Any]]:
        """Cluster similar incidents to identify systemic issues"""
        from src.domain.models.incident import Incident

        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        result = await self.db.execute(
            select(Incident).where(and_(Incident.reported_date >= cutoff, Incident.description.isnot(None)))  # type: ignore[attr-defined]  # SA columns  # TYPE-IGNORE: MYPY-OVERRIDE
        )
        incidents = result.scalars().all()

        # Group by extracted keywords
        clusters: dict[str, list] = defaultdict(list)
        for inc in incidents:
            keywords = TextAnalyzer.extract_keywords(inc.description or "")
            for kw in keywords:
                clusters[kw].append(
                    {
                        "id": inc.id,
                        "title": inc.title,
                        "date": (inc.incident_date.isoformat() if inc.incident_date else None),
                        "department": inc.department,
                    }
                )

        # Return clusters with multiple incidents
        result_list = []
        for category, cluster_incidents in clusters.items():
            if len(cluster_incidents) >= 3:  # At least 3 similar incidents
                result_list.append(
                    {
                        "category": category,
                        "incident_count": len(cluster_incidents),
                        "incidents": cluster_incidents[:10],  # First 10
                        "departments_affected": list(
                            set(i["department"] for i in cluster_incidents if i["department"])
                        ),
                        "suggested_action": f"Investigate systemic causes of {category.replace('_', ' ')} incidents",
                        "priority": (
                            "high"
                            if len(cluster_incidents) >= 10
                            else "medium" if len(cluster_incidents) >= 5 else "low"
                        ),
                    }
                )

        result_list.sort(key=lambda x: x["incident_count"], reverse=True)  # type: ignore[arg-type, return-value]  # TYPE-IGNORE: MYPY-OVERRIDE
        return result_list

    def analyze_5_whys(self, incident_id: int, answers: list[str]) -> dict[str, Any]:
        """Guide 5 Whys analysis"""
        # Generate follow-up questions based on answers
        analysis = {
            "incident_id": incident_id,
            "whys": [],
            "root_cause_identified": len(answers) >= 5,
            "suggested_root_cause": None,
            "recommendations": [],
        }

        for i, answer in enumerate(answers):
            analysis["whys"].append(  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                {
                    "level": i + 1,
                    "question": f"Why did this happen? (Level {i + 1})",
                    "answer": answer,
                }
            )

        if len(answers) >= 5:
            # The last answer is typically the root cause
            analysis["suggested_root_cause"] = answers[-1]

            # Generate recommendations based on root cause keywords
            root_keywords = TextAnalyzer.extract_keywords(answers[-1])
            recommendations = RecommendationEngine(self.db)._get_rule_based_recommendations(answers[-1], None)
            analysis["recommendations"] = recommendations

        return analysis
