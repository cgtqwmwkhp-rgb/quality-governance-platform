"""
Analytics Service - Advanced Analytics and Forecasting

Features:
- Data aggregation across modules
- Trend analysis with forecasting
- Benchmark comparisons
- Cost calculations
- ROI tracking
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Enterprise analytics service for cross-module insights.

    Provides:
    - Time series analysis
    - Statistical forecasting
    - Benchmark comparisons
    - Cost calculations
    """

    def __init__(self) -> None:
        self.cache: Dict[str, Any] = {}

    # ==================== Data Aggregation ====================

    def get_kpi_summary(
        self,
        time_range: str = "last_30_days",
        filters: Optional[Dict[str, Any]] = None,
        tenant_id: int | None = None,
    ) -> Dict[str, Any]:
        """
        Get summary KPIs across all modules.

        Returns key metrics for dashboard overview.
        """
        # Mock data for demonstration
        return {
            "incidents": {
                "total": 47,
                "open": 12,
                "closed": 35,
                "trend": -8.5,  # % change from previous period
                "avg_resolution_days": 4.2,
            },
            "actions": {
                "total": 156,
                "open": 34,
                "overdue": 8,
                "completed_on_time_rate": 87.5,
                "trend": 12.3,
            },
            "audits": {
                "total": 23,
                "completed": 18,
                "in_progress": 5,
                "avg_score": 89.4,
                "trend": 3.2,
            },
            "risks": {
                "total": 89,
                "high": 12,
                "medium": 34,
                "low": 43,
                "mitigated": 67,
            },
            "compliance": {
                "overall_score": 94.2,
                "iso_9001": 96.1,
                "iso_14001": 92.8,
                "iso_45001": 93.7,
            },
            "training": {
                "completion_rate": 91.2,
                "expiring_soon": 14,
                "overdue": 3,
            },
        }

    def get_trend_data(
        self,
        data_source: str,
        metric: str,
        granularity: str = "daily",
        time_range: str = "last_30_days",
        group_by: Optional[str] = None,
        tenant_id: int | None = None,
    ) -> Dict[str, Any]:
        """
        Get time series trend data for charting.

        Args:
            data_source: Source module (incidents, actions, etc.)
            metric: Metric to track (count, resolution_time, etc.)
            granularity: Time granularity (daily, weekly, monthly)
            time_range: Time range to analyze
            group_by: Optional grouping dimension

        Returns:
            Time series data with labels and values
        """
        # Generate mock trend data
        days = 30 if time_range == "last_30_days" else 90
        labels = []
        values = []

        base_value = 10
        for i in range(days):
            date = datetime.utcnow() - timedelta(days=days - i - 1)
            labels.append(date.strftime("%Y-%m-%d"))
            # Add some variance
            variance = math.sin(i / 5) * 3 + (i / days) * 2
            values.append(max(0, base_value + variance + (i % 7) - 3))

        return {
            "labels": labels,
            "datasets": [
                {
                    "label": f"{data_source} - {metric}",
                    "data": values,
                    "borderColor": "#10B981",
                    "backgroundColor": "rgba(16, 185, 129, 0.1)",
                }
            ],
            "summary": {
                "total": sum(values),
                "average": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "trend_direction": "up" if values[-1] > values[0] else "down",
                "trend_percentage": ((values[-1] - values[0]) / max(values[0], 1))
                * 100,
            },
        }

    # ==================== Forecasting ====================

    def forecast_trend(
        self,
        historical_data: List[float],
        periods_ahead: int = 12,
        confidence_level: float = 0.95,
    ) -> Dict[str, Any]:
        """
        Generate trend forecast with confidence intervals.

        Uses simple exponential smoothing for demonstration.
        In production, would use more sophisticated methods.

        Args:
            historical_data: Historical values
            periods_ahead: Number of periods to forecast
            confidence_level: Confidence level for intervals

        Returns:
            Forecast with confidence intervals
        """
        if not historical_data or len(historical_data) < 3:
            return {"error": "Insufficient data for forecasting"}

        # Simple exponential smoothing
        alpha = 0.3  # Smoothing factor
        n = len(historical_data)

        # Calculate smoothed values
        smoothed = [historical_data[0]]
        for i in range(1, n):
            smoothed.append(alpha * historical_data[i] + (1 - alpha) * smoothed[-1])

        # Calculate trend
        trend = (smoothed[-1] - smoothed[0]) / n

        # Generate forecast
        last_value = smoothed[-1]
        forecast_values = []
        lower_bounds = []
        upper_bounds = []

        # Calculate standard error
        errors = [historical_data[i] - smoothed[i] for i in range(n)]
        std_error = math.sqrt(sum(e**2 for e in errors) / n)

        # Z-score for confidence level
        z_score = 1.96 if confidence_level == 0.95 else 1.645

        for i in range(1, periods_ahead + 1):
            forecast = last_value + (trend * i)
            margin = z_score * std_error * math.sqrt(i)

            forecast_values.append(forecast)
            lower_bounds.append(forecast - margin)
            upper_bounds.append(forecast + margin)

        return {
            "forecast": forecast_values,
            "lower_bound": lower_bounds,
            "upper_bound": upper_bounds,
            "confidence_level": confidence_level,
            "trend_direction": "increasing" if trend > 0 else "decreasing",
            "trend_strength": abs(trend),
            "model": "exponential_smoothing",
        }

    # ==================== Benchmarking ====================

    def get_benchmark_comparison(
        self,
        metric: str,
        industry: str = "utilities",
        region: str = "uk",
        tenant_id: int | None = None,
    ) -> Dict[str, Any]:
        """
        Compare organization metrics against industry benchmarks.

        Args:
            metric: Metric to compare
            industry: Industry for comparison
            region: Geographic region

        Returns:
            Benchmark comparison data
        """
        # Mock benchmark data
        benchmarks = {
            "incident_rate": {
                "your_value": 2.3,
                "industry_average": 3.8,
                "industry_median": 3.5,
                "percentile_25": 4.2,
                "percentile_75": 2.8,
                "percentile_90": 1.9,
                "your_percentile": 72,
                "trend": "improving",
            },
            "audit_score": {
                "your_value": 89.4,
                "industry_average": 82.1,
                "industry_median": 83.5,
                "percentile_25": 78.0,
                "percentile_75": 88.0,
                "percentile_90": 92.5,
                "your_percentile": 78,
                "trend": "stable",
            },
            "action_completion_rate": {
                "your_value": 87.5,
                "industry_average": 79.2,
                "industry_median": 81.0,
                "percentile_25": 72.0,
                "percentile_75": 86.0,
                "percentile_90": 93.0,
                "your_percentile": 76,
                "trend": "improving",
            },
            "training_compliance": {
                "your_value": 91.2,
                "industry_average": 84.5,
                "industry_median": 86.0,
                "percentile_25": 78.0,
                "percentile_75": 90.0,
                "percentile_90": 95.0,
                "your_percentile": 74,
                "trend": "stable",
            },
        }

        return benchmarks.get(
            metric,
            {
                "error": f"No benchmark data available for {metric}",
            },
        )

    def get_benchmark_summary(
        self,
        industry: str = "utilities",
        tenant_id: int | None = None,
    ) -> Dict[str, Any]:
        """Get summary of all benchmark comparisons."""
        metrics = [
            "incident_rate",
            "audit_score",
            "action_completion_rate",
            "training_compliance",
        ]

        comparisons = {}
        total_percentile = 0
        above_average_count = 0

        for metric in metrics:
            data = self.get_benchmark_comparison(metric, industry)
            if "error" not in data:
                comparisons[metric] = data
                total_percentile += data.get("your_percentile", 50)
                if data.get("your_value", 0) > data.get("industry_average", 0):
                    above_average_count += 1

        return {
            "comparisons": comparisons,
            "overall_percentile": total_percentile / len(metrics),
            "above_average_count": above_average_count,
            "total_metrics": len(metrics),
            "performance_rating": self._get_performance_rating(
                total_percentile / len(metrics)
            ),
        }

    def _get_performance_rating(self, percentile: float) -> str:
        """Convert percentile to performance rating."""
        if percentile >= 90:
            return "Excellent"
        elif percentile >= 75:
            return "Good"
        elif percentile >= 50:
            return "Average"
        elif percentile >= 25:
            return "Below Average"
        else:
            return "Needs Improvement"

    # ==================== Cost Analysis ====================

    def calculate_cost_of_non_compliance(
        self,
        time_range: str = "last_12_months",
        tenant_id: int | None = None,
    ) -> Dict[str, Any]:
        """
        Calculate total cost of non-compliance.

        Includes direct and indirect costs from incidents,
        regulatory fines, lost productivity, etc.
        """
        # Mock cost data
        return {
            "total_cost": 127500.00,
            "currency": "GBP",
            "breakdown": {
                "incident_costs": {
                    "amount": 45000.00,
                    "count": 47,
                    "avg_per_incident": 957.45,
                    "categories": {
                        "medical_expenses": 12000.00,
                        "lost_time": 18000.00,
                        "equipment_damage": 8000.00,
                        "investigation": 7000.00,
                    },
                },
                "regulatory_fines": {
                    "amount": 25000.00,
                    "count": 2,
                },
                "legal_costs": {
                    "amount": 15000.00,
                    "count": 3,
                },
                "remediation": {
                    "amount": 22500.00,
                    "count": 8,
                },
                "productivity_loss": {
                    "amount": 20000.00,
                    "estimated_hours": 500,
                },
            },
            "trend": {
                "vs_previous_period": -12.5,  # % reduction
                "direction": "improving",
            },
            "projected_annual": 145000.00,
            "cost_per_employee": 425.00,
            "recommendations": [
                {
                    "action": "Implement additional safety training",
                    "estimated_savings": 15000.00,
                    "priority": "high",
                },
                {
                    "action": "Upgrade PPE equipment",
                    "estimated_savings": 8000.00,
                    "priority": "medium",
                },
                {
                    "action": "Automate compliance monitoring",
                    "estimated_savings": 12000.00,
                    "priority": "high",
                },
            ],
        }

    # ==================== ROI Tracking ====================

    def calculate_roi(
        self,
        investment_id: Optional[int] = None,
        tenant_id: int | None = None,
    ) -> Dict[str, Any]:
        """
        Calculate ROI for safety investments.

        Args:
            investment_id: Specific investment, or None for all

        Returns:
            ROI metrics and breakdown
        """
        # Mock ROI data
        investments = [
            {
                "id": 1,
                "name": "Safety Management System Upgrade",
                "category": "technology",
                "investment": 50000.00,
                "annual_savings": 35000.00,
                "incidents_prevented": 12,
                "roi_percentage": 70.0,
                "payback_months": 17,
                "status": "active",
            },
            {
                "id": 2,
                "name": "Enhanced PPE Program",
                "category": "equipment",
                "investment": 25000.00,
                "annual_savings": 18000.00,
                "incidents_prevented": 8,
                "roi_percentage": 72.0,
                "payback_months": 17,
                "status": "active",
            },
            {
                "id": 3,
                "name": "Comprehensive Training Program",
                "category": "training",
                "investment": 40000.00,
                "annual_savings": 28000.00,
                "incidents_prevented": 15,
                "roi_percentage": 70.0,
                "payback_months": 17,
                "status": "active",
            },
        ]

        if investment_id:
            investment = next(
                (i for i in investments if i["id"] == investment_id), None
            )
            if investment:
                return {"investment": investment}
            return {"error": "Investment not found"}

        # Pre-calculated values from mock data
        # 50000 + 25000 + 40000 = 115000
        total_investment = 115000.00
        # 35000 + 18000 + 28000 = 81000
        total_savings = 81000.00
        # 12 + 8 + 15 = 35
        total_prevented = 35
        # 17 + 17 + 17 = 51
        total_payback = 51

        return {
            "investments": investments,
            "summary": {
                "total_investment": total_investment,
                "total_annual_savings": total_savings,
                "total_incidents_prevented": total_prevented,
                "overall_roi": (total_savings / total_investment) * 100,
                "average_payback_months": total_payback / len(investments),
                "cost_per_incident_prevented": total_investment / total_prevented,
            },
            "by_category": {
                "technology": {
                    "investment": 50000.00,
                    "savings": 35000.00,
                    "roi": 70.0,
                },
                "equipment": {
                    "investment": 25000.00,
                    "savings": 18000.00,
                    "roi": 72.0,
                },
                "training": {
                    "investment": 40000.00,
                    "savings": 28000.00,
                    "roi": 70.0,
                },
            },
        }

    # ==================== Report Generation ====================

    def generate_executive_summary(
        self,
        time_range: str = "last_month",
        tenant_id: int | None = None,
    ) -> Dict[str, Any]:
        """
        Generate executive summary for automated reports.

        Returns structured data for PDF/PowerPoint generation.
        """
        kpis = self.get_kpi_summary(time_range)
        costs = self.calculate_cost_of_non_compliance(time_range)
        roi = self.calculate_roi()
        benchmarks = self.get_benchmark_summary()

        return {
            "report_date": datetime.utcnow().isoformat(),
            "time_range": time_range,
            "executive_summary": {
                "headline": "Safety Performance Improved by 8.5%",
                "key_achievements": [
                    "Incident rate reduced by 8.5% vs previous period",
                    "Audit scores improved to 89.4% average",
                    "Action completion rate at 87.5%",
                    f"ROI on safety investments: {roi['summary']['overall_roi']:.1f}%",
                ],
                "areas_of_concern": [
                    f"{kpis['actions']['overdue']} overdue actions require attention",
                    f"{kpis['training']['expiring_soon']} training certifications expiring soon",
                ],
                "recommendations": costs.get("recommendations", []),
            },
            "kpis": kpis,
            "financial": {
                "cost_of_non_compliance": costs["total_cost"],
                "total_investment": roi["summary"]["total_investment"],
                "total_savings": roi["summary"]["total_annual_savings"],
                "net_benefit": roi["summary"]["total_annual_savings"]
                - costs["total_cost"],
            },
            "benchmarks": {
                "overall_percentile": benchmarks["overall_percentile"],
                "performance_rating": benchmarks["performance_rating"],
                "above_average_count": benchmarks["above_average_count"],
            },
            "trends": {
                "incidents": {"direction": "down", "change": -8.5},
                "audits": {"direction": "up", "change": 3.2},
                "compliance": {"direction": "stable", "change": 0.5},
            },
        }


# Singleton instance
analytics_service = AnalyticsService()
