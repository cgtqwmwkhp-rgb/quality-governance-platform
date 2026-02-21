"""
Planet Mark Carbon Management API Routes

Features:
- Multi-year carbon footprint tracking
- Scope 1, 2, 3 emissions management
- All 15 GHG Protocol Scope 3 categories
- Data quality scoring (0-16) with auto-calculation
- SMART improvement action tracking
- Certification lifecycle management
- ISO 14001 cross-mapping
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
from src.api.schemas.setup_required import setup_required_response
from src.api.utils.entity import get_or_404
from src.api.utils.update import apply_updates
from src.domain.models.planet_mark import (
    CarbonEvidence,
    CarbonReportingYear,
    DataQualityAssessment,
    EmissionSource,
    FleetEmissionRecord,
    ImprovementAction,
    Scope3CategoryData,
    SupplierEmissionData,
    UtilityMeterReading,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ GHG Protocol Scope 3 Categories ============

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

# DEFRA 2024 Emission Factors (simplified)
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

# Data Quality Scoring Criteria
DATA_QUALITY_CRITERIA = {
    "actual": {"score": 4, "label": "Actual metered/verified data"},
    "calculated": {"score": 3, "label": "Calculated from activity data"},
    "estimated": {"score": 2, "label": "Estimates from proxy data"},
    "extrapolated": {"score": 1, "label": "Rough extrapolations"},
    "missing": {"score": 0, "label": "No data available"},
}


# ============ Pydantic Schemas ============


class ReportingYearCreate(BaseModel):
    year_label: str = Field(..., min_length=4, max_length=20)
    year_number: int = Field(..., ge=1)
    period_start: datetime
    period_end: datetime
    average_fte: float = Field(..., gt=0)
    organization_name: str = Field(default="Plantexpand Limited")
    sites_included: Optional[list] = None
    is_baseline_year: bool = False
    reduction_target_percent: float = Field(default=5.0)


class EmissionSourceCreate(BaseModel):
    source_name: str
    source_category: str
    scope: str
    scope_3_category: Optional[str] = None
    activity_type: str
    activity_value: float
    activity_unit: str
    data_quality_level: str = "estimated"
    data_source: Optional[str] = None


class ImprovementActionCreate(BaseModel):
    action_title: str
    specific: str
    measurable: str
    achievable_owner: str
    relevant: Optional[str] = None
    time_bound: datetime
    scheduled_month: Optional[str] = None
    target_scope: Optional[str] = None
    target_source: Optional[str] = None
    expected_reduction_pct: Optional[float] = None


class ActionStatusUpdate(BaseModel):
    status: str
    progress_percent: int = Field(ge=0, le=100)
    actual_completion_date: Optional[datetime] = None
    actual_reduction_achieved: Optional[float] = None
    lessons_learned: Optional[str] = None


class FleetRecordCreate(BaseModel):
    vehicle_registration: str
    vehicle_type: Optional[str] = None
    fuel_type: str
    month: str
    fuel_litres: float
    fuel_cost: Optional[float] = None
    mileage: Optional[float] = None
    data_source: str = "fuel_card"
    driver_name: Optional[str] = None


class UtilityReadingCreate(BaseModel):
    meter_reference: str
    utility_type: str
    site_name: str
    reading_date: datetime
    reading_value: float
    reading_unit: str
    reading_type: str = "actual_read"
    consumption: Optional[float] = None
    supplier_name: Optional[str] = None
    is_renewable: bool = False


# ============ Reporting Years ============


@router.get("/years", response_model=dict)
async def list_reporting_years(
    request: Request,
    db: DbSession,
) -> dict[str, Any]:
    """List all carbon reporting years with comparison"""
    try:
        result = await db.execute(select(CarbonReportingYear).order_by(desc(CarbonReportingYear.year_number)))
        years = list(result.scalars().all())
    except (ProgrammingError, OperationalError) as e:
        logger.warning(
            "Planet Mark years query failed (likely missing table): %s",
            str(e)[:200],
            extra={"request_id": get_request_id(request)},
        )
        return setup_required_response(
            module="planet-mark",
            message="Planet Mark module not initialized. Database migrations may need to be applied.",
            next_action="Run database migrations with: alembic upgrade head",
            request_id=get_request_id(request),
        )
    except Exception as e:
        logger.error(
            "Planet Mark years query failed unexpectedly: %s: %s",
            type(e).__name__,
            str(e)[:500],
            extra={"request_id": get_request_id(request)},
        )
        return setup_required_response(
            module="planet-mark",
            message=f"Planet Mark query failed: {type(e).__name__}. Check server logs.",
            next_action="Review application logs for request_id and contact support.",
            request_id=get_request_id(request),
        )

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


@router.post("/years", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_reporting_year(
    year_data: ReportingYearCreate,
    db: DbSession,
) -> dict[str, Any]:
    """Create a new carbon reporting year"""
    year = CarbonReportingYear(
        **year_data.model_dump(),
    )
    db.add(year)
    await db.commit()
    await db.refresh(year)

    # Initialize Scope 3 categories
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

    return {"id": year.id, "year_label": year.year_label, "message": "Reporting year created"}


@router.get("/years/{year_id}", response_model=dict)
async def get_reporting_year(
    year_id: int,
    db: DbSession,
) -> dict[str, Any]:
    """Get detailed reporting year data"""
    year = await get_or_404(db, CarbonReportingYear, year_id)

    # Get emission sources
    result = await db.execute(select(EmissionSource).where(EmissionSource.reporting_year_id == year_id))
    sources = result.scalars().all()

    # Calculate scope breakdowns
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


# ============ Emission Sources ============


@router.post("/years/{year_id}/sources", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_emission_source(
    year_id: int,
    source_data: EmissionSourceCreate,
    db: DbSession,
) -> dict[str, Any]:
    """Add an emission source with auto-calculation"""
    year = await get_or_404(db, CarbonReportingYear, year_id)

    # Auto-calculate emissions using DEFRA factors
    ef_key = source_data.activity_type
    emission_factor = EMISSION_FACTORS.get(ef_key, {"factor": 0, "unit": "", "source": ""})

    co2e_kg = source_data.activity_value * emission_factor["factor"]
    co2e_tonnes = co2e_kg / 1000

    # Get data quality score
    dq_score = DATA_QUALITY_CRITERIA.get(source_data.data_quality_level, {"score": 2})["score"]

    source = EmissionSource(
        reporting_year_id=year_id,
        emission_factor=emission_factor["factor"],
        emission_factor_unit=emission_factor["unit"],
        emission_factor_source=emission_factor["source"],
        co2e_tonnes=co2e_tonnes,
        data_quality_score=dq_score,
        **source_data.model_dump(),
    )
    db.add(source)

    # Update year totals
    await _recalculate_year_totals(db, year)

    await db.commit()
    await db.refresh(source)

    return {
        "id": source.id,
        "co2e_tonnes": co2e_tonnes,
        "emission_factor": emission_factor,
        "message": "Emission source added",
    }


@router.get("/years/{year_id}/sources", response_model=dict)
async def list_emission_sources(
    year_id: int,
    db: DbSession,
    scope: Optional[str] = Query(None),
) -> dict[str, Any]:
    """List emission sources for a year"""
    stmt = select(EmissionSource).where(EmissionSource.reporting_year_id == year_id)

    if scope:
        stmt = stmt.where(EmissionSource.scope == scope)

    result = await db.execute(stmt.order_by(desc(EmissionSource.co2e_tonnes)))
    sources = result.scalars().all()

    total = sum(s.co2e_tonnes for s in sources)

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
                "percentage": round((s.co2e_tonnes / total * 100), 1) if total > 0 else 0,
                "data_quality": s.data_quality_level,
            }
            for s in sources
        ],
    }


# ============ Scope 3 Categories ============


@router.get("/years/{year_id}/scope3", response_model=dict)
async def get_scope3_breakdown(
    year_id: int,
    db: DbSession,
) -> dict[str, Any]:
    """Get Scope 3 category breakdown"""
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

    total = sum(c.total_co2e for c in categories)
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
                "percentage": round((c.total_co2e / total * 100), 1) if total > 0 else 0,
                "data_quality_score": c.data_quality_score,
                "calculation_method": c.calculation_method,
                "exclusion_reason": c.exclusion_reason,
            }
            for c in categories
        ],
    }


# ============ Improvement Actions ============


@router.get("/years/{year_id}/actions", response_model=dict)
async def list_improvement_actions(
    year_id: int,
    db: DbSession,
    status: Optional[str] = Query(None),
) -> dict[str, Any]:
    """List SMART improvement actions"""
    stmt = select(ImprovementAction).where(ImprovementAction.reporting_year_id == year_id)

    if status:
        stmt = stmt.where(ImprovementAction.status == status)

    result = await db.execute(stmt.order_by(ImprovementAction.time_bound))
    actions = result.scalars().all()

    # Summary
    completed = len([a for a in actions if a.status == "completed"])
    in_progress = len([a for a in actions if a.status == "in_progress"])
    overdue = len([a for a in actions if a.status != "completed" and a.time_bound < datetime.utcnow()])

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
                "is_overdue": a.status != "completed" and a.time_bound < datetime.utcnow(),
            }
            for a in actions
        ],
    }


@router.post("/years/{year_id}/actions", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_improvement_action(
    year_id: int,
    action_data: ImprovementActionCreate,
    db: DbSession,
) -> dict[str, Any]:
    """Create a SMART improvement action"""
    await get_or_404(db, CarbonReportingYear, year_id)

    count_result = await db.execute(
        select(func.count()).select_from(ImprovementAction).where(ImprovementAction.reporting_year_id == year_id)
    )
    count = count_result.scalar_one()
    action_id = f"ACT-{(count + 1):03d}"

    action = ImprovementAction(
        reporting_year_id=year_id,
        action_id=action_id,
        status="planned",
        **action_data.model_dump(),
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)

    return {"id": action.id, "action_id": action_id, "message": "Improvement action created"}


@router.put("/years/{year_id}/actions/{action_id}", response_model=dict)
async def update_action_status(
    year_id: int,
    action_id: int,
    status_data: ActionStatusUpdate,
    db: DbSession,
) -> dict[str, Any]:
    """Update improvement action status"""
    result = await db.execute(
        select(ImprovementAction).where(
            ImprovementAction.id == action_id, ImprovementAction.reporting_year_id == year_id
        )
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    apply_updates(action, status_data)
    await db.commit()

    return {"message": "Action updated", "id": action.id}


# ============ Data Quality ============


@router.get("/years/{year_id}/data-quality", response_model=dict)
async def get_data_quality_assessment(
    year_id: int,
    db: DbSession,
) -> dict[str, Any]:
    """Get data quality assessment with recommendations"""
    year = await get_or_404(db, CarbonReportingYear, year_id)

    result = await db.execute(select(EmissionSource).where(EmissionSource.reporting_year_id == year_id))
    sources = result.scalars().all()

    # Calculate quality by scope
    def calc_scope_quality(scope_sources):
        if not scope_sources:
            return {"score": 0, "actual_pct": 0, "recommendations": ["No data recorded"]}

        total_emissions = sum(s.co2e_tonnes for s in scope_sources)
        weighted_score = sum(s.data_quality_score * s.co2e_tonnes for s in scope_sources)
        avg_score = (weighted_score / total_emissions) if total_emissions > 0 else 0

        actual_count = len([s for s in scope_sources if s.data_quality_level == "actual"])
        actual_pct = (actual_count / len(scope_sources) * 100) if scope_sources else 0

        recommendations = []
        if avg_score < 3:
            recommendations.append("Increase use of actual metered data")
        if actual_pct < 80:
            recommendations.append("Install smart meters for automatic readings")
        if any(s.data_quality_level == "extrapolated" for s in scope_sources):
            recommendations.append("Replace extrapolated data with calculated values")

        return {
            "score": round(avg_score * 4, 0),  # Scale to 0-16
            "actual_pct": round(actual_pct, 1),
            "source_count": len(scope_sources),
            "recommendations": recommendations or ["Data quality is good"],
        }

    scope1 = calc_scope_quality([s for s in sources if s.scope == "scope_1"])
    scope2 = calc_scope_quality([s for s in sources if s.scope == "scope_2"])
    scope3 = calc_scope_quality([s for s in sources if s.scope == "scope_3"])

    overall = round((scope1["score"] + scope2["score"] + scope3["score"]) / 3, 0)

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


# ============ Fleet Integration ============


@router.post("/years/{year_id}/fleet", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_fleet_record(
    year_id: int,
    fleet_data: FleetRecordCreate,
    db: DbSession,
) -> dict[str, Any]:
    """Add fleet fuel consumption record"""
    await get_or_404(db, CarbonReportingYear, year_id)

    # Calculate emissions
    ef = EMISSION_FACTORS.get(f"{fleet_data.fuel_type.lower()}_litres", EMISSION_FACTORS["diesel_litres"])
    co2e_kg = fleet_data.fuel_litres * ef["factor"]

    # Calculate efficiency if mileage provided
    l_per_100km = None
    if fleet_data.mileage and fleet_data.mileage > 0:
        l_per_100km = (fleet_data.fuel_litres / fleet_data.mileage) * 100

    record = FleetEmissionRecord(
        reporting_year_id=year_id,
        co2e_kg=co2e_kg,
        litres_per_100km=l_per_100km,
        **fleet_data.model_dump(),
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


@router.get("/years/{year_id}/fleet/summary", response_model=dict)
async def get_fleet_summary(
    year_id: int,
    db: DbSession,
) -> dict[str, Any]:
    """Get fleet emissions summary with driver leaderboard"""
    result = await db.execute(select(FleetEmissionRecord).where(FleetEmissionRecord.reporting_year_id == year_id))
    records = result.scalars().all()

    if not records:
        return {"year_id": year_id, "message": "No fleet data", "total_co2e": 0}

    # Aggregate by vehicle
    vehicles = {}
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

    # Calculate efficiency
    for v in vehicles.values():
        if v["total_mileage"] > 0:
            v["litres_per_100km"] = round((v["total_litres"] / v["total_mileage"]) * 100, 2)
        else:
            v["litres_per_100km"] = None

    # Sort by emissions (worst first)
    sorted_vehicles = sorted(vehicles.values(), key=lambda x: x["total_co2e_kg"], reverse=True)

    total_co2e = sum(v["total_co2e_kg"] for v in vehicles.values()) / 1000  # tonnes

    return {
        "year_id": year_id,
        "total_litres": sum(v["total_litres"] for v in vehicles.values()),
        "total_co2e_tonnes": round(total_co2e, 2),
        "vehicle_count": len(vehicles),
        "vehicles": sorted_vehicles[:10],  # Top 10 emitters
        "eco_driving_target": "≤ 8.5 L/100km",
    }


# ============ Utility Integration ============


@router.post("/years/{year_id}/utilities", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_utility_reading(
    year_id: int,
    reading_data: UtilityReadingCreate,
    db: DbSession,
) -> dict[str, Any]:
    """Add utility meter reading"""
    await get_or_404(db, CarbonReportingYear, year_id)

    reading = UtilityMeterReading(
        reporting_year_id=year_id,
        **reading_data.model_dump(),
    )
    db.add(reading)
    await db.commit()
    await db.refresh(reading)

    return {"id": reading.id, "message": "Utility reading added"}


# ============ Certification ============


@router.get("/years/{year_id}/certification", response_model=dict)
async def get_certification_status(
    year_id: int,
    db: DbSession,
) -> dict[str, Any]:
    """Get certification status and evidence checklist"""
    year = await get_or_404(db, CarbonReportingYear, year_id)

    result = await db.execute(select(CarbonEvidence).where(CarbonEvidence.reporting_year_id == year_id))
    evidence = result.scalars().all()

    result = await db.execute(select(ImprovementAction).where(ImprovementAction.reporting_year_id == year_id))
    actions = result.scalars().all()

    # Evidence checklist
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
        {"type": "travel_expense", "category": "scope_3", "description": "Business travel records", "required": False},
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

    # Calculate readiness
    required_complete = sum(1 for r in required_evidence if r["required"] and r["uploaded"])
    required_total = sum(1 for r in required_evidence if r["required"])
    readiness = (required_complete / required_total * 100) if required_total > 0 else 0

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
        "data_quality_met": year.overall_data_quality >= 12,
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


# ============ Dashboard ============


@router.get("/dashboard", response_model=dict)
async def get_carbon_dashboard(
    request: Request,
    db: DbSession,
) -> dict[str, Any]:
    """Get Planet Mark carbon management dashboard"""
    try:
        result = await db.execute(select(CarbonReportingYear).order_by(desc(CarbonReportingYear.year_number)).limit(3))
        years = list(result.scalars().all())
    except (ProgrammingError, OperationalError) as e:
        logger.warning(
            "Planet Mark dashboard query failed (likely missing table): %s",
            str(e)[:200],
            extra={"request_id": get_request_id(request)},
        )
        return setup_required_response(
            module="planet-mark",
            message="Planet Mark module not initialized. Database migrations may need to be applied.",
            next_action="Run database migrations with: alembic upgrade head",
            request_id=get_request_id(request),
        )
    except Exception as e:
        logger.error(
            "Planet Mark dashboard query failed unexpectedly: %s: %s",
            type(e).__name__,
            str(e)[:500],
            extra={"request_id": get_request_id(request)},
        )
        return setup_required_response(
            module="planet-mark",
            message=f"Planet Mark query failed: {type(e).__name__}. Check server logs.",
            next_action="Review application logs for request_id and contact support.",
            request_id=get_request_id(request),
        )

    if not years:
        return setup_required_response(
            module="planet-mark",
            message="No carbon reporting years configured",
            next_action="Create a reporting year via POST /api/v1/planet-mark/years",
            request_id=get_request_id(request),
        )

    current_year = years[0]

    baseline_result = await db.execute(select(CarbonReportingYear).where(CarbonReportingYear.is_baseline_year == True))
    baseline = baseline_result.scalars().first()

    yoy_change = None
    if len(years) >= 2:
        prev_year = years[1]
        if prev_year.emissions_per_fte and current_year.emissions_per_fte:
            yoy_change = (
                (current_year.emissions_per_fte - prev_year.emissions_per_fte) / prev_year.emissions_per_fte
            ) * 100

    actions_result = await db.execute(
        select(ImprovementAction).where(ImprovementAction.reporting_year_id == current_year.id)
    )
    actions = list(actions_result.scalars().all())

    overdue_actions = [a for a in actions if a.status != "completed" and a.time_bound < datetime.utcnow()]

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
            "scope_1_2": (current_year.scope_1_data_quality or 0) + (current_year.scope_2_data_quality or 0),
            "scope_3": current_year.scope_3_data_quality or 0,
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


# ============ ISO 14001 Cross-Mapping ============


@router.get("/iso14001-mapping", response_model=dict)
async def get_iso14001_mapping() -> dict[str, Any]:
    """Get Planet Mark to ISO 14001 cross-mapping"""
    return {
        "description": "Cross-mapping between Planet Mark requirements and ISO 14001:2015 clauses",
        "mappings": [
            {
                "pm_requirement": "Carbon footprint measurement",
                "pm_category": "emissions_measurement",
                "iso14001_clause": "6.1.2",
                "iso14001_title": "Environmental aspects",
                "mapping_type": "direct",
                "notes": "GHG emissions are significant environmental aspects",
            },
            {
                "pm_requirement": "Improvement targets (5% reduction)",
                "pm_category": "improvement_plan",
                "iso14001_clause": "6.2",
                "iso14001_title": "Environmental objectives and planning",
                "mapping_type": "direct",
                "notes": "Carbon reduction objectives with measurable targets",
            },
            {
                "pm_requirement": "SMART improvement actions",
                "pm_category": "improvement_plan",
                "iso14001_clause": "6.2.2",
                "iso14001_title": "Planning actions to achieve objectives",
                "mapping_type": "direct",
                "notes": "Actions with owners, deadlines, and measures",
            },
            {
                "pm_requirement": "Data quality and monitoring",
                "pm_category": "data_quality",
                "iso14001_clause": "9.1.1",
                "iso14001_title": "Monitoring, measurement, analysis, evaluation",
                "mapping_type": "direct",
                "notes": "Calibrated meters, verified data, trending",
            },
            {
                "pm_requirement": "Evidence documentation",
                "pm_category": "certification",
                "iso14001_clause": "7.5",
                "iso14001_title": "Documented information",
                "mapping_type": "direct",
                "notes": "Bills, invoices, certificates as controlled documents",
            },
            {
                "pm_requirement": "Annual certification audit",
                "pm_category": "certification",
                "iso14001_clause": "9.2",
                "iso14001_title": "Internal audit",
                "mapping_type": "partial",
                "notes": "External Planet Mark assessment supplements internal audits",
            },
            {
                "pm_requirement": "Continual improvement",
                "pm_category": "improvement_plan",
                "iso14001_clause": "10.3",
                "iso14001_title": "Continual improvement",
                "mapping_type": "direct",
                "notes": "Year-on-year emission reductions demonstrate improvement",
            },
            {
                "pm_requirement": "Supplier engagement (Scope 3)",
                "pm_category": "emissions_measurement",
                "iso14001_clause": "8.1",
                "iso14001_title": "Operational planning and control",
                "mapping_type": "partial",
                "notes": "Outsourced processes and supply chain control",
            },
        ],
    }


# ============ Helper Functions ============


async def _recalculate_year_totals(db: AsyncSession, year: CarbonReportingYear) -> None:
    """Recalculate total emissions for a reporting year"""
    result = await db.execute(select(EmissionSource).where(EmissionSource.reporting_year_id == year.id))
    sources = result.scalars().all()

    scope1 = sum(s.co2e_tonnes for s in sources if s.scope == "scope_1")
    scope2 = sum(s.co2e_tonnes for s in sources if s.scope == "scope_2")
    scope3 = sum(s.co2e_tonnes for s in sources if s.scope == "scope_3")

    year.scope_1_total = scope1
    year.scope_2_market = scope2
    year.scope_3_total = scope3
    year.total_emissions = scope1 + scope2 + scope3

    if year.average_fte > 0:
        year.emissions_per_fte = year.total_emissions / year.average_fte

    # Update data quality scores (simplified)
    s1_sources = [s for s in sources if s.scope == "scope_1"]
    s2_sources = [s for s in sources if s.scope == "scope_2"]
    s3_sources = [s for s in sources if s.scope == "scope_3"]

    year.scope_1_data_quality = _calc_avg_quality(s1_sources)
    year.scope_2_data_quality = _calc_avg_quality(s2_sources)
    year.scope_3_data_quality = _calc_avg_quality(s3_sources)
    year.overall_data_quality = (year.scope_1_data_quality + year.scope_2_data_quality + year.scope_3_data_quality) // 3


def _calc_avg_quality(sources: list) -> int:
    """Calculate average data quality score"""
    if not sources:
        return 0
    total = sum(s.data_quality_score for s in sources)
    return int((total / len(sources)) * 4)  # Scale to 0-16
