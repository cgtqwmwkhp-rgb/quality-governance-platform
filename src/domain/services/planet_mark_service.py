"""Planet Mark carbon management business logic.

Encapsulates DEFRA emission factor calculations, CO2e computation,
data quality scoring, fleet efficiency, certification readiness,
and all Planet Mark data operations (reporting years, emission sources,
improvement actions, fleet, utilities, dashboard).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import NotFoundError
from src.domain.models.planet_mark import (
    CarbonEvidence,
    CarbonReportingYear,
    EmissionSource,
    FleetEmissionRecord,
    ImprovementAction,
    Scope3CategoryData,
    UtilityMeterReading,
)
from src.infrastructure.monitoring.azure_monitor import track_metric

EMISSION_FACTORS: dict[str, dict[str, Any]] = {
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

DATA_QUALITY_CRITERIA: dict[str, dict[str, Any]] = {
    "actual": {"score": 4, "label": "Actual metered/verified data"},
    "calculated": {"score": 3, "label": "Calculated from activity data"},
    "estimated": {"score": 2, "label": "Estimates from proxy data"},
    "extrapolated": {"score": 1, "label": "Rough extrapolations"},
    "missing": {"score": 0, "label": "No data available"},
}

SCOPE3_CATEGORIES = [
    {
        "number": 1,
        "name": "Purchased goods and services",
        "description": "Extraction, production, and transportation of goods and services purchased",
    },
    {
        "number": 2,
        "name": "Capital goods",
        "description": "Extraction, production, and transportation of capital goods purchased",
    },
    {
        "number": 3,
        "name": "Fuel and energy-related activities",
        "description": "Upstream emissions of purchased fuels and electricity not in Scope 1 or 2",
    },
    {
        "number": 4,
        "name": "Upstream transportation and distribution",
        "description": "Transportation and distribution of products purchased, between tier 1 suppliers and own operations",
    },
    {
        "number": 5,
        "name": "Waste generated in operations",
        "description": "Disposal and treatment of waste generated in operations",
    },
    {
        "number": 6,
        "name": "Business travel",
        "description": "Transportation of employees for business-related activities",
    },
    {
        "number": 7,
        "name": "Employee commuting",
        "description": "Transportation of employees between homes and worksites",
    },
    {
        "number": 8,
        "name": "Upstream leased assets",
        "description": "Operation of assets leased by the reporting company",
    },
    {
        "number": 9,
        "name": "Downstream transportation and distribution",
        "description": "Transportation and distribution of products sold",
    },
    {
        "number": 10,
        "name": "Processing of sold products",
        "description": "Processing of intermediate products sold by downstream companies",
    },
    {"number": 11, "name": "Use of sold products", "description": "End use of goods and services sold"},
    {
        "number": 12,
        "name": "End-of-life treatment of sold products",
        "description": "Waste disposal and treatment of products sold",
    },
    {
        "number": 13,
        "name": "Downstream leased assets",
        "description": "Operation of assets owned and leased to other entities",
    },
    {"number": 14, "name": "Franchises", "description": "Operation of franchises"},
    {"number": 15, "name": "Investments", "description": "Operation of investments"},
]


async def _get_entity(db: AsyncSession, model: type, entity_id: int, *, tenant_id: int | None = None) -> Any:
    """Fetch entity by PK or raise ``NotFoundError``."""
    stmt = select(model).where(model.id == entity_id)  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
    if tenant_id is not None:
        stmt = stmt.where(model.tenant_id == tenant_id)  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
    result = await db.execute(stmt)
    entity = result.scalar_one_or_none()
    if entity is None:
        raise NotFoundError(f"{model.__name__} with ID {entity_id} not found")
    return entity


class PlanetMarkService:
    """Business logic and data operations for Planet Mark carbon management."""

    # ---- Pure calculations (no DB) ----

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
        return int(DATA_QUALITY_CRITERIA.get(level, {"score": 2})["score"])

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
        return int(round((scope1_score + scope2_score + scope3_score) / 3, 0))

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
        return fuel_litres * float(ef["factor"]), ef

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

    # ---- Reporting year operations ----

    @staticmethod
    async def list_reporting_years(db: AsyncSession) -> dict[str, Any]:
        result = await db.execute(select(CarbonReportingYear).order_by(desc(CarbonReportingYear.year_number)))
        years = list(result.scalars().all())
        return {
            "total": len(years),
            "years": [
                {
                    "id": y.id,
                    "year_label": y.year_label,
                    "year_number": y.year_number,
                    "period": f"{y.period_start.strftime('%d %b %Y')} - {y.period_end.strftime('%d %b %Y')}",
                    "average_fte": y.average_fte,
                    "total_emissions": y.total_emissions,
                    "emissions_per_fte": y.emissions_per_fte,
                    "scope_1": y.scope_1_total,
                    "scope_2_market": y.scope_2_market,
                    "scope_3": y.scope_3_total,
                    "data_quality": y.overall_data_quality,
                    "certification_status": y.certification_status,
                    "is_baseline": y.is_baseline_year,
                }
                for y in years
            ],
        }

    @staticmethod
    async def create_reporting_year(
        db: AsyncSession,
        year_data: dict[str, Any],
    ) -> dict[str, Any]:
        year = CarbonReportingYear(**year_data)
        db.add(year)
        await db.commit()
        await db.refresh(year)

        for cat in SCOPE3_CATEGORIES:
            scope3 = Scope3CategoryData(
                reporting_year_id=year.id,
                category_number=cat["number"],
                category_name=cat["name"],
                category_description=cat["description"],
                is_relevant=True,
                is_measured=False,
            )
            db.add(scope3)
        await db.commit()

        track_metric("planet_mark.reporting_year_created", 1)
        return {"id": year.id, "year_label": year.year_label, "message": "Reporting year created"}

    @staticmethod
    async def get_reporting_year_detail(
        db: AsyncSession,
        year_id: int,
        tenant_id: int,
    ) -> dict[str, Any]:
        year = await _get_entity(db, CarbonReportingYear, year_id, tenant_id=tenant_id)

        result = await db.execute(select(EmissionSource).where(EmissionSource.reporting_year_id == year_id))
        sources = result.scalars().all()

        scope1_sources = [s for s in sources if s.scope == "scope_1"]
        scope2_sources = [s for s in sources if s.scope == "scope_2"]
        scope3_sources = [s for s in sources if s.scope == "scope_3"]

        return {
            "id": year.id,
            "year_label": year.year_label,
            "year_number": year.year_number,
            "organization_name": year.organization_name,
            "period_start": year.period_start.isoformat(),
            "period_end": year.period_end.isoformat(),
            "average_fte": year.average_fte,
            "is_baseline_year": year.is_baseline_year,
            "emissions": {
                "scope_1": {
                    "total": year.scope_1_total,
                    "sources": [{"name": s.source_name, "co2e": s.co2e_tonnes} for s in scope1_sources],
                },
                "scope_2": {
                    "location_based": year.scope_2_location,
                    "market_based": year.scope_2_market,
                    "sources": [{"name": s.source_name, "co2e": s.co2e_tonnes} for s in scope2_sources],
                },
                "scope_3": {
                    "total": year.scope_3_total,
                    "categories_measured": len([s for s in scope3_sources if s.co2e_tonnes > 0]),
                },
                "total_market_based": year.total_emissions,
                "per_fte": year.emissions_per_fte,
            },
            "data_quality": {
                "scope_1": year.scope_1_data_quality,
                "scope_2": year.scope_2_data_quality,
                "scope_3": year.scope_3_data_quality,
                "overall": year.overall_data_quality,
            },
            "targets": {
                "reduction_target_percent": year.reduction_target_percent,
                "target_emissions_per_fte": year.target_emissions_per_fte,
            },
            "certification": {
                "status": year.certification_status,
                "certificate_number": year.certificate_number,
                "certification_date": year.certification_date.isoformat() if year.certification_date else None,
                "expiry_date": year.expiry_date.isoformat() if year.expiry_date else None,
            },
        }

    # ---- Emission sources ----

    @staticmethod
    async def add_emission_source(
        db: AsyncSession,
        year_id: int,
        tenant_id: int,
        source_data: dict[str, Any],
    ) -> dict[str, Any]:
        year = await _get_entity(db, CarbonReportingYear, year_id, tenant_id=tenant_id)

        activity_value = source_data.get("activity_value", 0.0)
        activity_type = source_data.get("activity_type", "")
        data_quality_level = source_data.get("data_quality_level", "estimated")

        co2e_kg, co2e_tonnes, emission_factor = PlanetMarkService.calculate_co2e(activity_value, activity_type)
        dq_score = PlanetMarkService.get_data_quality_score(data_quality_level)

        source = EmissionSource(  # type: ignore[misc]  # SA model kwargs  # TYPE-IGNORE: MYPY-OVERRIDE
            reporting_year_id=year_id,
            emission_factor=emission_factor["factor"],
            emission_factor_unit=emission_factor["unit"],
            emission_factor_source=emission_factor["source"],
            co2e_tonnes=co2e_tonnes,
            data_quality_score=dq_score,
            **source_data,
        )
        db.add(source)

        await PlanetMarkService.recalculate_year_totals(db, year)
        await db.commit()
        await db.refresh(source)

        return {
            "id": source.id,
            "co2e_tonnes": co2e_tonnes,
            "emission_factor": emission_factor,
            "message": "Emission source added",
        }

    @staticmethod
    async def list_emission_sources(
        db: AsyncSession,
        year_id: int,
        *,
        scope: str | None = None,
    ) -> dict[str, Any]:
        stmt = select(EmissionSource).where(EmissionSource.reporting_year_id == year_id)
        if scope:
            stmt = stmt.where(EmissionSource.scope == scope)

        result = await db.execute(stmt.order_by(desc(EmissionSource.co2e_tonnes)))
        sources = result.scalars().all()

        total = sum(float(s.co2e_tonnes) for s in sources)

        return {
            "year_id": year_id,
            "total_co2e": total,
            "sources": [
                {
                    "id": s.id,
                    "source_name": s.source_name,
                    "source_category": s.source_category,
                    "scope": s.scope,
                    "activity_value": s.activity_value,
                    "activity_unit": s.activity_unit,
                    "co2e_tonnes": s.co2e_tonnes,
                    "percentage": round((float(s.co2e_tonnes) / total * 100), 1) if total > 0 else 0,
                    "data_quality": s.data_quality_level,
                }
                for s in sources
            ],
        }

    # ---- Scope 3 ----

    @staticmethod
    async def get_scope3_breakdown(
        db: AsyncSession,
        year_id: int,
    ) -> dict[str, Any]:
        result = await db.execute(
            select(Scope3CategoryData)
            .where(Scope3CategoryData.reporting_year_id == year_id)
            .order_by(Scope3CategoryData.category_number)
        )
        categories = result.scalars().all()

        if not categories:
            return {
                "year_id": year_id,
                "categories": SCOPE3_CATEGORIES,
                "measured_count": 0,
                "total_co2e": 0,
            }

        total = sum(float(c.total_co2e) for c in categories)
        measured = len([c for c in categories if c.is_measured])

        return {
            "year_id": year_id,
            "measured_count": measured,
            "total_measured": 15,
            "total_co2e": total,
            "categories": [
                {
                    "number": c.category_number,
                    "name": c.category_name,
                    "description": c.category_description,
                    "is_relevant": c.is_relevant,
                    "is_measured": c.is_measured,
                    "total_co2e": c.total_co2e,
                    "percentage": round((float(c.total_co2e) / total * 100), 1) if total > 0 else 0,
                    "data_quality_score": c.data_quality_score,
                    "calculation_method": c.calculation_method,
                    "exclusion_reason": c.exclusion_reason,
                }
                for c in categories
            ],
        }

    # ---- Improvement actions ----

    @staticmethod
    async def list_improvement_actions(
        db: AsyncSession,
        year_id: int,
        *,
        status_filter: str | None = None,
    ) -> dict[str, Any]:
        stmt = select(ImprovementAction).where(ImprovementAction.reporting_year_id == year_id)  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
        if status_filter:
            stmt = stmt.where(ImprovementAction.status == status_filter)  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE

        result = await db.execute(stmt.order_by(ImprovementAction.time_bound))  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
        actions = result.scalars().all()

        now = datetime.utcnow()
        completed = len([a for a in actions if a.status == "completed"])
        in_progress = len([a for a in actions if a.status == "in_progress"])
        overdue = len([a for a in actions if a.status != "completed" and a.time_bound and a.time_bound < now])

        return {
            "year_id": year_id,
            "summary": {
                "total": len(actions),
                "completed": completed,
                "in_progress": in_progress,
                "overdue": overdue,
                "completion_rate": round((completed / len(actions) * 100), 1) if actions else 0,
            },
            "actions": [
                {
                    "id": a.id,
                    "action_id": a.action_id,
                    "action_title": a.action_title,
                    "owner": a.achievable_owner,
                    "deadline": a.time_bound.isoformat(),
                    "scheduled_month": a.scheduled_month,
                    "status": a.status,
                    "progress_percent": a.progress_percent,
                    "target_scope": a.target_scope,
                    "expected_reduction_pct": a.expected_reduction_pct,
                    "is_overdue": a.status != "completed" and bool(a.time_bound and a.time_bound < now),
                }
                for a in actions
            ],
        }

    @staticmethod
    async def create_improvement_action(
        db: AsyncSession,
        year_id: int,
        tenant_id: int,
        action_data: dict[str, Any],
    ) -> dict[str, Any]:
        await _get_entity(db, CarbonReportingYear, year_id, tenant_id=tenant_id)

        count_result = await db.execute(
            select(func.count()).select_from(ImprovementAction).where(ImprovementAction.reporting_year_id == year_id)
        )
        count = count_result.scalar_one()
        action_id = f"ACT-{(count + 1):03d}"

        action = ImprovementAction(  # type: ignore[misc]  # SA model kwargs  # TYPE-IGNORE: MYPY-OVERRIDE
            reporting_year_id=year_id,
            action_id=action_id,
            status="planned",
            **action_data,
        )
        db.add(action)
        await db.commit()
        await db.refresh(action)

        return {"id": action.id, "action_id": action_id, "message": "Improvement action created"}

    @staticmethod
    async def update_action_status(
        db: AsyncSession,
        year_id: int,
        action_id: int,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        result = await db.execute(
            select(ImprovementAction).where(
                ImprovementAction.id == action_id, ImprovementAction.reporting_year_id == year_id
            )
        )
        action = result.scalar_one_or_none()
        if not action:
            raise NotFoundError(f"Action {action_id} not found in year {year_id}")

        for key, value in updates.items():
            setattr(action, key, value)
        if hasattr(action, "updated_at"):
            action.updated_at = datetime.utcnow()
        await db.commit()
        return {"message": "Action updated", "id": action.id}

    # ---- Data quality ----

    @staticmethod
    async def get_data_quality_assessment(
        db: AsyncSession,
        year_id: int,
        tenant_id: int,
    ) -> dict[str, Any]:
        await _get_entity(db, CarbonReportingYear, year_id, tenant_id=tenant_id)

        result = await db.execute(select(EmissionSource).where(EmissionSource.reporting_year_id == year_id))
        sources = result.scalars().all()

        scope1 = PlanetMarkService.calculate_scope_quality([s for s in sources if s.scope == "scope_1"])
        scope2 = PlanetMarkService.calculate_scope_quality([s for s in sources if s.scope == "scope_2"])
        scope3 = PlanetMarkService.calculate_scope_quality([s for s in sources if s.scope == "scope_3"])

        overall = PlanetMarkService.calculate_overall_data_quality(scope1["score"], scope2["score"], scope3["score"])

        return {
            "year_id": year_id,
            "overall_score": int(overall),
            "max_score": 16,
            "scopes": {
                "scope_1": scope1,
                "scope_2": scope2,
                "scope_3": scope3,
            },
            "priority_improvements": [
                {"action": "Complete fuel-card audit for 100% fleet coverage", "impact": "Scope 1 +2 points"},
                {"action": "Install smart electricity meters", "impact": "Scope 2 +3 points"},
                {"action": "Engage top 10 suppliers for specific data", "impact": "Scope 3 +2 points"},
            ],
            "target_scores": {
                "scope_1_2": "≥12/16 (Planet Mark requirement)",
                "scope_3": "≥11/16 (Planet Mark requirement)",
            },
        }

    # ---- Fleet ----

    @staticmethod
    async def add_fleet_record(
        db: AsyncSession,
        year_id: int,
        tenant_id: int,
        fleet_data: dict[str, Any],
    ) -> dict[str, Any]:
        await _get_entity(db, CarbonReportingYear, year_id, tenant_id=tenant_id)

        fuel_litres = fleet_data.get("fuel_litres", 0.0)
        fuel_type = fleet_data.get("fuel_type", "diesel")
        mileage = fleet_data.get("mileage")

        co2e_kg, _ = PlanetMarkService.calculate_fleet_co2e(fuel_litres, fuel_type)
        l_per_100km = PlanetMarkService.calculate_fuel_efficiency(fuel_litres, mileage)

        record = FleetEmissionRecord(  # type: ignore[misc]  # SA model kwargs  # TYPE-IGNORE: MYPY-OVERRIDE
            reporting_year_id=year_id,
            co2e_kg=co2e_kg,
            litres_per_100km=l_per_100km,
            **fleet_data,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        return {
            "id": record.id,
            "co2e_kg": co2e_kg,
            "litres_per_100km": l_per_100km,
            "message": "Fleet record added",
        }

    @staticmethod
    async def get_fleet_summary(
        db: AsyncSession,
        year_id: int,
    ) -> dict[str, Any]:
        result = await db.execute(select(FleetEmissionRecord).where(FleetEmissionRecord.reporting_year_id == year_id))
        records = result.scalars().all()

        if not records:
            return {"year_id": year_id, "message": "No fleet data", "total_co2e": 0}

        vehicles: dict[str, dict[str, Any]] = {}
        for r in records:
            if r.vehicle_registration not in vehicles:
                vehicles[r.vehicle_registration] = {
                    "registration": r.vehicle_registration,
                    "type": r.vehicle_type,
                    "fuel_type": r.fuel_type,
                    "total_litres": 0,
                    "total_co2e_kg": 0,
                    "total_mileage": 0,
                }
            vehicles[r.vehicle_registration]["total_litres"] += r.fuel_litres
            vehicles[r.vehicle_registration]["total_co2e_kg"] += r.co2e_kg
            if r.mileage:
                vehicles[r.vehicle_registration]["total_mileage"] += r.mileage

        for v in vehicles.values():
            efficiency = PlanetMarkService.calculate_fuel_efficiency(v["total_litres"], v["total_mileage"])
            v["litres_per_100km"] = round(efficiency, 2) if efficiency is not None else None

        sorted_vehicles = sorted(vehicles.values(), key=lambda x: x["total_co2e_kg"], reverse=True)
        total_co2e = sum(v["total_co2e_kg"] for v in vehicles.values()) / 1000  # type: ignore[misc]  # TYPE-IGNORE: MYPY-OVERRIDE

        return {
            "year_id": year_id,
            "total_litres": sum(v["total_litres"] for v in vehicles.values()),
            "total_co2e_tonnes": round(total_co2e, 2),
            "vehicle_count": len(vehicles),
            "vehicles": sorted_vehicles[:10],
            "eco_driving_target": "≤ 8.5 L/100km",
        }

    # ---- Utilities ----

    @staticmethod
    async def add_utility_reading(
        db: AsyncSession,
        year_id: int,
        tenant_id: int,
        reading_data: dict[str, Any],
    ) -> dict[str, Any]:
        await _get_entity(db, CarbonReportingYear, year_id, tenant_id=tenant_id)

        reading = UtilityMeterReading(  # type: ignore[misc]  # SA model kwargs  # TYPE-IGNORE: MYPY-OVERRIDE
            reporting_year_id=year_id,
            **reading_data,
        )
        db.add(reading)
        await db.commit()
        await db.refresh(reading)
        return {"id": reading.id, "message": "Utility reading added"}

    # ---- Certification ----

    @staticmethod
    async def get_certification_status(
        db: AsyncSession,
        year_id: int,
        tenant_id: int,
    ) -> dict[str, Any]:
        year = await _get_entity(db, CarbonReportingYear, year_id, tenant_id=tenant_id)

        result = await db.execute(select(CarbonEvidence).where(CarbonEvidence.reporting_year_id == year_id))
        evidence = result.scalars().all()

        result = await db.execute(select(ImprovementAction).where(ImprovementAction.reporting_year_id == year_id))
        actions = result.scalars().all()

        required_evidence = [
            {
                "type": "utility_bill",
                "category": "scope_2",
                "description": "Electricity bills (12 months)",
                "required": True,
            },
            {"type": "utility_bill", "category": "scope_1", "description": "Gas bills (12 months)", "required": True},
            {
                "type": "fuel_card_report",
                "category": "scope_1",
                "description": "Fleet fuel card statements",
                "required": True,
            },
            {"type": "waste_manifest", "category": "scope_3", "description": "Waste transfer notes", "required": False},
            {
                "type": "travel_expense",
                "category": "scope_3",
                "description": "Business travel records",
                "required": False,
            },
            {
                "type": "improvement_action",
                "category": "certification",
                "description": "Improvement plan evidence",
                "required": True,
            },
        ]

        for req in required_evidence:
            matching = [e for e in evidence if e.document_type == req["type"]]
            req["uploaded"] = len(matching) > 0
            req["verified"] = any(e.is_verified for e in matching)

        readiness = PlanetMarkService.calculate_certification_readiness(required_evidence)

        return {
            "year_id": year_id,
            "year_label": year.year_label,
            "status": year.certification_status,
            "certificate_number": year.certificate_number,
            "certification_date": year.certification_date.isoformat() if year.certification_date else None,
            "expiry_date": year.expiry_date.isoformat() if year.expiry_date else None,
            "readiness_percent": round(readiness, 0),
            "evidence_checklist": required_evidence,
            "actions_completed": len([a for a in actions if a.status == "completed"]),
            "actions_total": len(actions),
            "data_quality_met": int(year.overall_data_quality or 0) >= 12,
            "next_steps": (
                [
                    "Complete all required evidence uploads",
                    "Verify Scope 1 & 2 data quality ≥ 12/16",
                    "Complete improvement actions",
                    "Submit for Planet Mark assessment",
                ]
                if year.certification_status == "draft"
                else []
            ),
        }

    # ---- Dashboard ----

    @staticmethod
    async def get_carbon_dashboard(db: AsyncSession) -> dict[str, Any] | None:
        """Return dashboard data, or ``None`` when no reporting years exist."""
        result = await db.execute(select(CarbonReportingYear).order_by(desc(CarbonReportingYear.year_number)).limit(3))
        years = list(result.scalars().all())

        if not years:
            return None

        current_year = years[0]

        baseline_result = await db.execute(
            select(CarbonReportingYear).where(CarbonReportingYear.is_baseline_year == True)  # type: ignore[attr-defined]  # noqa: E712  # TYPE-IGNORE: MYPY-OVERRIDE
        )
        baseline = baseline_result.scalars().first()  # noqa: F841

        yoy_change: float | None = None
        if len(years) >= 2:
            prev_year = years[1]
            if prev_year.emissions_per_fte and current_year.emissions_per_fte:
                yoy_change = (
                    (float(current_year.emissions_per_fte) - float(prev_year.emissions_per_fte))
                    / float(prev_year.emissions_per_fte)
                ) * 100

        actions_result = await db.execute(
            select(ImprovementAction).where(ImprovementAction.reporting_year_id == current_year.id)
        )
        actions = list(actions_result.scalars().all())

        dashboard_now = datetime.utcnow()
        overdue_actions = [
            a for a in actions if a.status != "completed" and a.time_bound and a.time_bound < dashboard_now
        ]

        return {
            "current_year": {
                "id": current_year.id,
                "label": current_year.year_label,
                "total_emissions": current_year.total_emissions,
                "emissions_per_fte": current_year.emissions_per_fte,
                "fte": current_year.average_fte,
                "yoy_change_percent": round(yoy_change, 1) if yoy_change else None,
                "on_track": yoy_change is not None and yoy_change <= -5,
            },
            "emissions_breakdown": {
                "scope_1": {"value": current_year.scope_1_total, "label": "Direct (Fleet, Gas)"},
                "scope_2": {"value": current_year.scope_2_market, "label": "Indirect (Electricity)"},
                "scope_3": {"value": current_year.scope_3_total, "label": "Value Chain"},
            },
            "data_quality": {
                "scope_1_2": int(current_year.scope_1_data_quality or 0) + int(current_year.scope_2_data_quality or 0),
                "scope_3": int(current_year.scope_3_data_quality or 0),
                "target": 12,
            },
            "certification": {
                "status": current_year.certification_status,
                "expiry_date": current_year.expiry_date.isoformat() if current_year.expiry_date else None,
            },
            "actions": {
                "total": len(actions),
                "completed": len([a for a in actions if a.status == "completed"]),
                "overdue": len(overdue_actions),
            },
            "targets": {
                "reduction_percent": current_year.reduction_target_percent,
                "target_per_fte": current_year.target_emissions_per_fte,
            },
            "historical_years": [
                {"label": y.year_label, "total": y.total_emissions, "per_fte": y.emissions_per_fte} for y in years
            ],
        }

    # ---- Year totals recalculation ----

    @staticmethod
    async def recalculate_year_totals(db: AsyncSession, year: CarbonReportingYear) -> None:
        """Recalculate total emissions for a reporting year from its sources."""
        result = await db.execute(select(EmissionSource).where(EmissionSource.reporting_year_id == year.id))
        sources = result.scalars().all()

        totals = PlanetMarkService.calculate_year_totals(sources)

        year.scope_1_total = totals["scope_1_total"]
        year.scope_2_market = totals["scope_2_market"]
        year.scope_3_total = totals["scope_3_total"]
        year.total_emissions = totals["total_emissions"]

        if year.average_fte > 0:
            year.emissions_per_fte = year.total_emissions / year.average_fte

        year.scope_1_data_quality = totals["scope_1_data_quality"]
        year.scope_2_data_quality = totals["scope_2_data_quality"]
        year.scope_3_data_quality = totals["scope_3_data_quality"]
        year.overall_data_quality = totals["overall_data_quality"]
