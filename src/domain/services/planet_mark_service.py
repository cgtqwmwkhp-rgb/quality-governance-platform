"""Planet Mark carbon management business logic.

Encapsulates DEFRA emission factor calculations, CO2e computation,
data quality scoring, fleet efficiency, and certification readiness.
"""

from __future__ import annotations

EMISSION_FACTORS = {
    "diesel_litres": {"factor": 2.51229, "unit": "kgCO2e/litre", "source": "DEFRA 2024"},
    "petrol_litres": {"factor": 2.16802, "unit": "kgCO2e/litre", "source": "DEFRA 2024"},
    "natural_gas_kwh": {"factor": 0.18254, "unit": "kgCO2e/kWh", "source": "DEFRA 2024"},
    "electricity_kwh_uk": {"factor": 0.20705, "unit": "kgCO2e/kWh", "source": "DEFRA 2024 (location)"},
    "electricity_kwh_market": {"factor": 0.43360, "unit": "kgCO2e/kWh", "source": "DEFRA 2024 (market)"},
    "waste_general_kg": {"factor": 0.44672, "unit": "kgCO2e/kg", "source": "DEFRA 2024"},
    "waste_recycled_kg": {"factor": 0.02140, "unit": "kgCO2e/kg", "source": "DEFRA 2024"},
    "rail_km": {"factor": 0.03549, "unit": "kgCO2e/km", "source": "DEFRA 2024"},
    "flight_short_km": {"factor": 0.24587, "unit": "kgCO2e/km", "source": "DEFRA 2024"},
    "car_average_km": {"factor": 0.17081, "unit": "kgCO2e/km", "source": "DEFRA 2024"},
}

DATA_QUALITY_CRITERIA = {
    "actual": {"score": 4, "label": "Actual metered/verified data"},
    "calculated": {"score": 3, "label": "Calculated from activity data"},
    "estimated": {"score": 2, "label": "Estimates from proxy data"},
    "extrapolated": {"score": 1, "label": "Rough extrapolations"},
    "missing": {"score": 0, "label": "No data available"},
}


class PlanetMarkService:
    """Pure-function service for Planet Mark carbon calculations."""

    @staticmethod
    def get_emission_factor(activity_type: str) -> dict:
        """Look up DEFRA emission factor for *activity_type*."""
        return EMISSION_FACTORS.get(activity_type, {"factor": 0, "unit": "", "source": ""})

    @staticmethod
    def calculate_co2e(activity_value: float, activity_type: str) -> tuple[float, float, dict]:
        """Return *(co2e_kg, co2e_tonnes, emission_factor_dict)*."""
        ef = PlanetMarkService.get_emission_factor(activity_type)
        co2e_kg = activity_value * ef["factor"]
        return co2e_kg, co2e_kg / 1000, ef

    @staticmethod
    def get_data_quality_score(level: str) -> int:
        """Map a quality level string to its 0-4 score."""
        return DATA_QUALITY_CRITERIA.get(level, {"score": 2})["score"]

    @staticmethod
    def calculate_scope_quality(scope_sources: list) -> dict:
        """Weighted data-quality assessment for a single scope.

        Each source must expose `co2e_tonnes`, `data_quality_score`, and
        `data_quality_level` attributes.
        """
        if not scope_sources:
            return {"score": 0, "actual_pct": 0, "recommendations": ["No data recorded"]}

        total_emissions = sum(s.co2e_tonnes for s in scope_sources)
        weighted_score = sum(s.data_quality_score * s.co2e_tonnes for s in scope_sources)
        avg_score = (weighted_score / total_emissions) if total_emissions > 0 else 0

        actual_count = len([s for s in scope_sources if s.data_quality_level == "actual"])
        actual_pct = (actual_count / len(scope_sources) * 100) if scope_sources else 0

        recommendations: list[str] = []
        if avg_score < 3:
            recommendations.append("Increase use of actual metered data")
        if actual_pct < 80:
            recommendations.append("Install smart meters for automatic readings")
        if any(s.data_quality_level == "extrapolated" for s in scope_sources):
            recommendations.append("Replace extrapolated data with calculated values")

        return {
            "score": round(avg_score * 4, 0),
            "actual_pct": round(actual_pct, 1),
            "source_count": len(scope_sources),
            "recommendations": recommendations or ["Data quality is good"],
        }

    @staticmethod
    def calculate_overall_data_quality(scope1_score: float, scope2_score: float, scope3_score: float) -> int:
        """Average the three scope scores into a single 0-16 integer."""
        return round((scope1_score + scope2_score + scope3_score) / 3, 0)

    @staticmethod
    def calculate_avg_quality(sources: list) -> int:
        """Unweighted average data quality score scaled to 0-16."""
        if not sources:
            return 0
        total = sum(s.data_quality_score for s in sources)
        return int((total / len(sources)) * 4)

    @staticmethod
    def calculate_fleet_co2e(fuel_litres: float, fuel_type: str) -> tuple[float, dict]:
        """Return *(co2e_kg, emission_factor_dict)* for a fleet fuel record."""
        ef = EMISSION_FACTORS.get(f"{fuel_type.lower()}_litres", EMISSION_FACTORS["diesel_litres"])
        return fuel_litres * ef["factor"], ef

    @staticmethod
    def calculate_fuel_efficiency(fuel_litres: float, mileage: float | None) -> float | None:
        """Return litres per 100 km, or *None* when mileage is unavailable."""
        if mileage and mileage > 0:
            return (fuel_litres / mileage) * 100
        return None

    @staticmethod
    def calculate_certification_readiness(required_evidence: list[dict]) -> float:
        """Percentage of *required* evidence items that have been uploaded."""
        required_total = sum(1 for r in required_evidence if r.get("required"))
        if required_total == 0:
            return 0
        required_complete = sum(1 for r in required_evidence if r.get("required") and r.get("uploaded"))
        return required_complete / required_total * 100

    @staticmethod
    def calculate_year_totals(sources: list) -> dict:
        """Aggregate emission totals and quality scores by scope.

        Returns a dict suitable for patching onto a ``CarbonReportingYear``.
        """
        scope1 = sum(s.co2e_tonnes for s in sources if s.scope == "scope_1")
        scope2 = sum(s.co2e_tonnes for s in sources if s.scope == "scope_2")
        scope3 = sum(s.co2e_tonnes for s in sources if s.scope == "scope_3")

        s1_sources = [s for s in sources if s.scope == "scope_1"]
        s2_sources = [s for s in sources if s.scope == "scope_2"]
        s3_sources = [s for s in sources if s.scope == "scope_3"]

        s1_dq = PlanetMarkService.calculate_avg_quality(s1_sources)
        s2_dq = PlanetMarkService.calculate_avg_quality(s2_sources)
        s3_dq = PlanetMarkService.calculate_avg_quality(s3_sources)

        return {
            "scope_1_total": scope1,
            "scope_2_market": scope2,
            "scope_3_total": scope3,
            "total_emissions": scope1 + scope2 + scope3,
            "scope_1_data_quality": s1_dq,
            "scope_2_data_quality": s2_dq,
            "scope_3_data_quality": s3_dq,
            "overall_data_quality": (s1_dq + s2_dq + s3_dq) // 3,
        }
