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
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
from src.api.schemas.setup_required import setup_required_response
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
    {
        "number": 11,
        "name": "Use of sold products",
        "description": "End use of goods and services sold",
    },
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
    "diesel_litres": {
        "factor": 2.51229,
        "unit": "kgCO2e/litre",
        "source": "DEFRA 2024",
    },
    "petrol_litres": {
        "factor": 2.16802,
        "unit": "kgCO2e/litre",
        "source": "DEFRA 2024",
    },
    "natural_gas_kwh": {
        "factor": 0.18254,
        "unit": "kgCO2e/kWh",
        "source": "DEFRA 2024",
    },
    "electricity_kwh_uk": {
        "factor": 0.20705,
        "unit": "kgCO2e/kWh",
        "source": "DEFRA 2024 (location)",
    },
    "electricity_kwh_market": {
        "factor": 0.43360,
        "unit": "kgCO2e/kWh",
        "source": "DEFRA 2024 (market)",
    },
    "waste_general_kg": {
        "factor": 0.44672,
        "unit": "kgCO2e/kg",
        "source": "DEFRA 2024",
    },
    "waste_recycled_kg": {
        "factor": 0.02140,
        "unit": "kgCO2e/kg",
        "source": "DEFRA 2024",
    },
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
    current_user: CurrentUser,
) -> dict[str, Any]:
    """List all carbon reporting years with comparison"""
    try:
        result = await db.execute(
            select(CarbonReportingYear)
            .where(CarbonReportingYear.tenant_id == current_user.tenant_id)
            .order_by(desc(CarbonReportingYear.year_number))
        )
        years = result.scalars().all()
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
            message="Planet Mark query failed. Check server logs.",
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


@router.post("/years", response_model=dict, status_code=201)
async def create_reporting_year(
    year_data: ReportingYearCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Create a new carbon reporting year"""
    year = CarbonReportingYear(
        tenant_id=current_user.tenant_id,
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

    return {
        "id": year.id,
        "year_label": year.year_label,
        "message": "Reporting year created",
    }


@router.get("/years/{year_id}", response_model=dict)
async def get_reporting_year(
    year_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get detailed reporting year data"""
    year = (
        await db.execute(
            select(CarbonReportingYear).where(
                CarbonReportingYear.id == year_id,
                CarbonReportingYear.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not year:
        raise HTTPException(status_code=404, detail="Reporting year not found")

    # Get emission sources (distinct DB result variable so mypy infers EmissionSource rows)
    sources: list[EmissionSource] = list(
        (
            await db.execute(
                select(EmissionSource).where(
                    EmissionSource.reporting_year_id == year_id,
                    EmissionSource.tenant_id == current_user.tenant_id,
                )
            )
        )
        .scalars()
        .all()
    )

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
            "certification_date": (year.certification_date.isoformat() if year.certification_date else None),
            "expiry_date": year.expiry_date.isoformat() if year.expiry_date else None,
        },
    }


# ============ Emission Sources ============


@router.post("/years/{year_id}/sources", response_model=dict, status_code=201)
async def add_emission_source(
    year_id: int,
    source_data: EmissionSourceCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Add an emission source with auto-calculation"""
    result = await db.execute(
        select(CarbonReportingYear).where(
            CarbonReportingYear.id == year_id,
            CarbonReportingYear.tenant_id == current_user.tenant_id,
        )
    )
    year = result.scalar_one_or_none()
    if not year:
        raise HTTPException(status_code=404, detail="Reporting year not found")

    # Auto-calculate emissions using DEFRA factors
    ef_key = source_data.activity_type
    emission_factor = EMISSION_FACTORS.get(ef_key, {"factor": 0, "unit": "", "source": ""})
    factor_val = float(cast(Any, emission_factor["factor"]))

    co2e_kg = float(source_data.activity_value) * factor_val
    co2e_tonnes = co2e_kg / 1000

    # Get data quality score
    dq_score = DATA_QUALITY_CRITERIA.get(source_data.data_quality_level, {"score": 2})["score"]

    source = EmissionSource(
        reporting_year_id=year_id,
        emission_factor=factor_val,
        emission_factor_unit=str(emission_factor["unit"]),
        emission_factor_source=str(emission_factor.get("source") or ""),
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
    current_user: CurrentUser,
    scope: Optional[str] = Query(None),
) -> dict[str, Any]:
    """List emission sources for a year"""
    stmt = select(EmissionSource).where(
        EmissionSource.reporting_year_id == year_id,
        EmissionSource.tenant_id == current_user.tenant_id,
    )

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
                "percentage": (round((s.co2e_tonnes / total * 100), 1) if total > 0 else 0),
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
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get Scope 3 category breakdown"""
    try:
        result = await db.execute(
            select(Scope3CategoryData)
            .where(
                Scope3CategoryData.reporting_year_id == year_id,
                Scope3CategoryData.tenant_id == current_user.tenant_id,
            )
            .order_by(Scope3CategoryData.category_number)
        )
        categories = result.scalars().all()
    except (ProgrammingError, OperationalError) as e:
        logger.warning("Planet Mark scope 3 query failed (likely missing schema): %s", str(e)[:200])
        return setup_required_response(
            module="planet-mark",
            message="Planet Mark Scope 3 categories are not initialized in this environment.",
            next_action="Apply the latest Planet Mark database migrations before using Scope 3 breakdowns.",
        )

    if not categories:
        # Return default categories
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
                "percentage": (round((c.total_co2e / total * 100), 1) if total > 0 else 0),
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
    current_user: CurrentUser,
    status: Optional[str] = Query(None),
) -> dict[str, Any]:
    """List SMART improvement actions"""
    try:
        stmt = select(ImprovementAction).where(
            ImprovementAction.reporting_year_id == year_id,
            ImprovementAction.tenant_id == current_user.tenant_id,
        )

        if status:
            stmt = stmt.where(ImprovementAction.status == status)

        result = await db.execute(stmt.order_by(ImprovementAction.time_bound))
        actions = result.scalars().all()
    except (ProgrammingError, OperationalError) as e:
        logger.warning("Planet Mark actions query failed (likely missing schema): %s", str(e)[:200])
        return setup_required_response(
            module="planet-mark",
            message="Planet Mark improvement actions are not initialized in this environment.",
            next_action="Apply the latest Planet Mark database migrations before using live actions.",
        )

    # Summary
    completed = len([a for a in actions if a.status == "completed"])
    in_progress = len([a for a in actions if a.status == "in_progress"])
    overdue = len([a for a in actions if a.status != "completed" and a.time_bound < datetime.now(timezone.utc)])

    return {
        "year_id": year_id,
        "summary": {
            "total": len(actions),
            "completed": completed,
            "in_progress": in_progress,
            "overdue": overdue,
            "completion_rate": (round((completed / len(actions) * 100), 1) if actions else 0),
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
                "is_overdue": a.status != "completed" and a.time_bound < datetime.now(timezone.utc),
            }
            for a in actions
        ],
    }


@router.post("/years/{year_id}/actions", response_model=dict, status_code=201)
async def create_improvement_action(
    year_id: int,
    action_data: ImprovementActionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Create a SMART improvement action"""
    result = await db.execute(
        select(CarbonReportingYear).where(
            CarbonReportingYear.id == year_id,
            CarbonReportingYear.tenant_id == current_user.tenant_id,
        )
    )
    year = result.scalar_one_or_none()
    if not year:
        raise HTTPException(status_code=404, detail="Reporting year not found")

    count_result = await db.execute(
        select(func.count())
        .select_from(ImprovementAction)
        .where(
            ImprovementAction.reporting_year_id == year_id,
            ImprovementAction.tenant_id == current_user.tenant_id,
        )
    )
    count = int(count_result.scalar() or 0)
    action_id = f"ACT-{(count + 1):03d}"

    action = ImprovementAction(
        tenant_id=current_user.tenant_id,
        reporting_year_id=year_id,
        action_id=action_id,
        status="planned",
        **action_data.model_dump(),
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)

    return {
        "id": action.id,
        "action_id": action_id,
        "message": "Improvement action created",
    }


@router.put("/years/{year_id}/actions/{action_id}", response_model=dict)
async def update_action_status(
    year_id: int,
    action_id: int,
    status_data: ActionStatusUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Update improvement action status"""
    result = await db.execute(
        select(ImprovementAction).where(
            ImprovementAction.id == action_id,
            ImprovementAction.reporting_year_id == year_id,
            ImprovementAction.tenant_id == current_user.tenant_id,
        )
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    for key, value in status_data.model_dump(exclude_unset=True).items():
        setattr(action, key, value)

    # Auto-complete: 100% progress → completed status + timestamp
    if action.progress_percent == 100 and action.status != "completed":
        action.status = "completed"
        action.actual_completion_date = datetime.now(timezone.utc)

    action.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Action updated", "id": action.id}


@router.post("/years/{year_id}/actions/bulk-status", response_model=dict)
async def bulk_update_action_status(
    year_id: int,
    payload: dict,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Bulk-update status for multiple improvement actions"""
    action_ids: list[int] = payload.get("action_ids", [])
    new_status: str = payload.get("status", "")
    if not action_ids or not new_status:
        raise HTTPException(status_code=422, detail="action_ids and status are required")

    result = await db.execute(
        select(ImprovementAction).where(
            ImprovementAction.id.in_(action_ids),
            ImprovementAction.reporting_year_id == year_id,
            ImprovementAction.tenant_id == current_user.tenant_id,
        )
    )
    actions = result.scalars().all()

    now = datetime.now(timezone.utc)
    updated_ids = []
    for action in actions:
        action.status = new_status
        action.updated_at = now
        if new_status == "completed":
            action.progress_percent = 100
            action.actual_completion_date = now
        updated_ids.append(action.id)

    await db.commit()
    return {"updated_count": len(updated_ids), "updated_ids": updated_ids}


@router.get("/years/{year_id}/actions/summary", response_model=dict)
async def get_actions_summary(
    year_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """KPI summary for improvement actions dashboard"""
    result = await db.execute(
        select(ImprovementAction).where(
            ImprovementAction.reporting_year_id == year_id,
            ImprovementAction.tenant_id == current_user.tenant_id,
        )
    )
    actions = result.scalars().all()
    now = datetime.now(timezone.utc)

    total = len(actions)
    completed = [a for a in actions if a.status == "completed"]
    in_progress = [a for a in actions if a.status == "in_progress"]
    overdue = [a for a in actions if a.status not in ("completed",) and a.time_bound < now]
    avg_progress = round(sum(a.progress_percent or 0 for a in actions) / total, 1) if total else 0

    return {
        "year_id": year_id,
        "total": total,
        "completed": len(completed),
        "in_progress": len(in_progress),
        "overdue": len(overdue),
        "not_started": total - len(completed) - len(in_progress),
        "completion_rate_percent": (round(len(completed) / total * 100, 1) if total else 0),
        "avg_progress_percent": avg_progress,
    }


# ============ Data Quality ============


@router.get("/years/{year_id}/data-quality", response_model=dict)
async def get_data_quality_assessment(
    year_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get data quality assessment with recommendations"""
    year = (
        await db.execute(
            select(CarbonReportingYear).where(
                CarbonReportingYear.id == year_id,
                CarbonReportingYear.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not year:
        raise HTTPException(status_code=404, detail="Reporting year not found")

    sources: list[EmissionSource] = list(
        (
            await db.execute(
                select(EmissionSource).where(
                    EmissionSource.reporting_year_id == year_id,
                    EmissionSource.tenant_id == current_user.tenant_id,
                )
            )
        )
        .scalars()
        .all()
    )

    # Calculate quality by scope
    def calc_scope_quality(scope_sources: list[EmissionSource]) -> dict[str, Any]:
        if not scope_sources:
            return {
                "score": 0,
                "actual_pct": 0,
                "recommendations": ["No data recorded"],
            }

        total_emissions = sum(s.co2e_tonnes for s in scope_sources)
        weighted_score = sum(s.data_quality_score * s.co2e_tonnes for s in scope_sources)
        avg_score = (weighted_score / total_emissions) if total_emissions > 0 else 0

        actual_count = len([s for s in scope_sources if s.data_quality_level == "actual"])
        actual_pct = (actual_count / len(scope_sources) * 100) if scope_sources else 0

        # Generate recommendations
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
            {
                "action": "Complete fuel-card audit for 100% fleet coverage",
                "impact": "Scope 1 +2 points",
            },
            {
                "action": "Install smart electricity meters",
                "impact": "Scope 2 +3 points",
            },
            {
                "action": "Engage top 10 suppliers for specific data",
                "impact": "Scope 3 +2 points",
            },
        ],
        "target_scores": {
            "scope_1_2": "≥12/16 (Planet Mark requirement)",
            "scope_3": "≥11/16 (Planet Mark requirement)",
        },
    }


# ============ Fleet Integration ============


@router.post("/years/{year_id}/fleet", response_model=dict, status_code=201)
async def add_fleet_record(
    year_id: int,
    fleet_data: FleetRecordCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Add fleet fuel consumption record"""
    result = await db.execute(
        select(CarbonReportingYear).where(
            CarbonReportingYear.id == year_id,
            CarbonReportingYear.tenant_id == current_user.tenant_id,
        )
    )
    year = result.scalar_one_or_none()
    if not year:
        raise HTTPException(status_code=404, detail="Reporting year not found")

    # Calculate emissions
    ef = EMISSION_FACTORS.get(f"{fleet_data.fuel_type.lower()}_litres", EMISSION_FACTORS["diesel_litres"])
    ef_factor = float(cast(Any, ef["factor"]))
    co2e_kg = float(fleet_data.fuel_litres) * ef_factor

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
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get fleet emissions summary with driver leaderboard"""
    result = await db.execute(
        select(FleetEmissionRecord).where(
            FleetEmissionRecord.reporting_year_id == year_id,
            FleetEmissionRecord.tenant_id == current_user.tenant_id,
        )
    )
    records = result.scalars().all()

    if not records:
        return {"year_id": year_id, "message": "No fleet data", "total_co2e": 0}

    # Aggregate by vehicle (explicit floats for mypy; JSON clients still receive numbers)
    vehicles: dict[str, dict[str, Any]] = {}
    for r in records:
        reg = r.vehicle_registration
        if reg not in vehicles:
            vehicles[reg] = {
                "registration": reg,
                "type": r.vehicle_type,
                "fuel_type": r.fuel_type,
                "total_litres": 0.0,
                "total_co2e_kg": 0.0,
                "total_mileage": 0.0,
            }
        agg = vehicles[reg]
        agg["total_litres"] = float(agg["total_litres"]) + float(r.fuel_litres)
        agg["total_co2e_kg"] = float(agg["total_co2e_kg"]) + float(r.co2e_kg)
        if r.mileage is not None:
            agg["total_mileage"] = float(agg["total_mileage"]) + float(r.mileage)

    # Calculate efficiency
    for v in vehicles.values():
        tm = float(v["total_mileage"])
        if tm > 0:
            v["litres_per_100km"] = round((float(v["total_litres"]) / tm) * 100, 2)
        else:
            v["litres_per_100km"] = None

    # Sort by emissions (worst first)
    sorted_vehicles = sorted(vehicles.values(), key=lambda x: float(x["total_co2e_kg"]), reverse=True)

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


@router.post("/years/{year_id}/utilities", response_model=dict, status_code=201)
async def add_utility_reading(
    year_id: int,
    reading_data: UtilityReadingCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Add utility meter reading"""
    result = await db.execute(
        select(CarbonReportingYear).where(
            CarbonReportingYear.id == year_id,
            CarbonReportingYear.tenant_id == current_user.tenant_id,
        )
    )
    year = result.scalar_one_or_none()
    if not year:
        raise HTTPException(status_code=404, detail="Reporting year not found")

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
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get certification status and evidence checklist"""
    year = (
        await db.execute(
            select(CarbonReportingYear).where(
                CarbonReportingYear.id == year_id,
                CarbonReportingYear.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not year:
        raise HTTPException(status_code=404, detail="Reporting year not found")

    evidence: list[CarbonEvidence] = list(
        (
            await db.execute(
                select(CarbonEvidence).where(
                    CarbonEvidence.reporting_year_id == year_id,
                    CarbonEvidence.tenant_id == current_user.tenant_id,
                )
            )
        )
        .scalars()
        .all()
    )

    actions: list[ImprovementAction] = list(
        (
            await db.execute(
                select(ImprovementAction).where(
                    ImprovementAction.reporting_year_id == year_id,
                    ImprovementAction.tenant_id == current_user.tenant_id,
                )
            )
        )
        .scalars()
        .all()
    )

    # Evidence checklist
    required_evidence = [
        {
            "type": "utility_bill",
            "category": "scope_2",
            "description": "Electricity bills (12 months)",
            "required": True,
        },
        {
            "type": "utility_bill",
            "category": "scope_1",
            "description": "Gas bills (12 months)",
            "required": True,
        },
        {
            "type": "fuel_card_report",
            "category": "scope_1",
            "description": "Fleet fuel card statements",
            "required": True,
        },
        {
            "type": "waste_manifest",
            "category": "scope_3",
            "description": "Waste transfer notes",
            "required": False,
        },
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

    # Calculate readiness
    required_complete = sum(1 for r in required_evidence if r["required"] and r["uploaded"])
    required_total = sum(1 for r in required_evidence if r["required"])
    readiness = (required_complete / required_total * 100) if required_total > 0 else 0

    return {
        "year_id": year_id,
        "year_label": year.year_label,
        "status": year.certification_status,
        "certificate_number": year.certificate_number,
        "certification_date": (year.certification_date.isoformat() if year.certification_date else None),
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
        "certifying_body": year.certifying_body,
        "assessor_name": year.assessor_name,
    }


# ============ Certification PATCH ============

VALID_CERTIFICATION_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["submitted"],
    "submitted": ["certified", "draft"],
    "certified": ["expired"],
    "expired": [],
}


class CertificationStatusPatch(BaseModel):
    status: str
    certificate_number: Optional[str] = None
    certification_date: Optional[str] = None
    expiry_date: Optional[str] = None
    certifying_body: Optional[str] = None
    assessor_name: Optional[str] = None
    assessment_notes: Optional[str] = None


@router.patch("/years/{year_id}/certification", response_model=dict)
async def patch_certification_status(
    year_id: int,
    patch: CertificationStatusPatch,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Update certification status with state-machine guard"""
    year = (
        await db.execute(
            select(CarbonReportingYear).where(
                CarbonReportingYear.id == year_id,
                CarbonReportingYear.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not year:
        raise HTTPException(status_code=404, detail="Reporting year not found")

    allowed = VALID_CERTIFICATION_TRANSITIONS.get(year.certification_status, [])
    if patch.status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot transition from '{year.certification_status}' to '{patch.status}'. "
                f"Allowed: {allowed or 'none'}"
            ),
        )

    year.certification_status = patch.status
    if patch.certificate_number is not None:
        year.certificate_number = patch.certificate_number
    if patch.certification_date is not None:
        year.certification_date = datetime.fromisoformat(patch.certification_date)
    if patch.expiry_date is not None:
        year.expiry_date = datetime.fromisoformat(patch.expiry_date)
    if patch.certifying_body is not None:
        year.certifying_body = patch.certifying_body
    if patch.assessor_name is not None:
        year.assessor_name = patch.assessor_name
    if patch.assessment_notes is not None:
        year.assessment_notes = patch.assessment_notes

    year.updated_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info(
        "Certification status updated year_id=%s status=%s tenant=%s",
        year_id,
        patch.status,
        current_user.tenant_id,
    )
    return {"message": "Certification status updated", "status": year.certification_status}


# ============ Evidence CRUD ============

PLANET_MARK_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
}
PLANET_MARK_MAX_SIZE_MB = 20


class EvidenceCreate(BaseModel):
    document_name: str
    document_type: str
    evidence_category: str
    period_covered: Optional[str] = None
    linked_source_id: Optional[int] = None
    linked_action_id: Optional[int] = None
    notes: Optional[str] = None


class EvidencePatch(BaseModel):
    is_verified: Optional[bool] = None
    verified_by: Optional[str] = None
    notes: Optional[str] = None


@router.get("/years/{year_id}/evidence", response_model=dict)
async def list_evidence(
    year_id: int,
    db: DbSession,
    current_user: CurrentUser,
    document_type: Optional[str] = Query(None),
    linked_action_id: Optional[int] = Query(None),
) -> dict[str, Any]:
    """List carbon evidence documents for a reporting year"""
    stmt = select(CarbonEvidence).where(
        CarbonEvidence.reporting_year_id == year_id,
        CarbonEvidence.tenant_id == current_user.tenant_id,
    )
    if document_type:
        stmt = stmt.where(CarbonEvidence.document_type == document_type)
    if linked_action_id:
        stmt = stmt.where(CarbonEvidence.linked_action_id == linked_action_id)

    result = await db.execute(stmt.order_by(desc(CarbonEvidence.uploaded_at)))
    docs = result.scalars().all()

    return {
        "total": len(docs),
        "evidence": [
            {
                "id": d.id,
                "document_name": d.document_name,
                "document_type": d.document_type,
                "evidence_category": d.evidence_category,
                "period_covered": d.period_covered,
                "file_size_kb": d.file_size_kb,
                "mime_type": d.mime_type,
                "is_verified": d.is_verified,
                "verified_by": d.verified_by,
                "linked_action_id": d.linked_action_id,
                "notes": d.notes,
                "uploaded_by": d.uploaded_by,
                "uploaded_at": d.uploaded_at.isoformat(),
                "storage_key": d.storage_key,
            }
            for d in docs
        ],
    }


@router.post("/years/{year_id}/evidence/upload", response_model=dict, status_code=201)
async def upload_evidence(
    year_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request: Request,
) -> dict[str, Any]:
    """Upload a carbon evidence document (multipart/form-data)"""
    import hashlib
    import os

    from fastapi import UploadFile

    year = (
        await db.execute(
            select(CarbonReportingYear).where(
                CarbonReportingYear.id == year_id,
                CarbonReportingYear.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not year:
        raise HTTPException(status_code=404, detail="Reporting year not found")

    form = await request.form()
    file_raw = form.get("file")
    file: UploadFile = cast(Any, file_raw)
    document_name: str = str(form.get("document_name", ""))
    document_type: str = str(form.get("document_type", "other"))
    evidence_category: str = str(form.get("evidence_category", "certification"))
    period_covered_raw = form.get("period_covered")
    period_covered: Optional[str] = str(period_covered_raw) if period_covered_raw is not None else None
    linked_action_id_raw = form.get("linked_action_id")
    linked_action_id = int(str(linked_action_id_raw)) if linked_action_id_raw is not None else None
    notes_raw = form.get("notes")
    notes: Optional[str] = str(notes_raw) if notes_raw is not None else None

    if not file or not hasattr(file, "read"):
        raise HTTPException(status_code=422, detail="A file must be uploaded")

    if file.content_type not in PLANET_MARK_ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: PDF, images, Excel, CSV.",
        )

    contents = await file.read()
    size_kb = len(contents) // 1024
    if size_kb > PLANET_MARK_MAX_SIZE_MB * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {PLANET_MARK_MAX_SIZE_MB} MB limit",
        )

    file_hash = hashlib.sha256(contents).hexdigest()

    # Deduplication check
    existing = (
        await db.execute(
            select(CarbonEvidence).where(
                CarbonEvidence.file_hash == file_hash,
                CarbonEvidence.reporting_year_id == year_id,
                CarbonEvidence.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return {
            "id": existing.id,
            "document_name": existing.document_name,
            "message": "Duplicate file detected — existing record returned",
            "duplicate": True,
        }

    # Store file
    storage_key: Optional[str] = None
    stored_path: Optional[str] = None
    try:
        from src.infrastructure.storage import get_storage_service

        storage = get_storage_service()
        safe_name = os.path.basename(file.filename or document_name or "upload")
        storage_key = f"planet-mark/tenant-{current_user.tenant_id}/year-{year_id}/{file_hash[:8]}-{safe_name}"
        stored_path = await storage.upload(storage_key, contents, file.content_type)
    except Exception as exc:
        logger.warning("Storage upload failed, continuing without blob URL: %s", exc)

    doc = CarbonEvidence(
        tenant_id=current_user.tenant_id,
        reporting_year_id=year_id,
        document_name=document_name or (file.filename or "upload"),
        document_type=document_type,
        evidence_category=evidence_category,
        period_covered=period_covered,
        linked_action_id=linked_action_id,
        file_path=stored_path,
        storage_key=storage_key,
        file_hash=file_hash,
        file_size_kb=size_kb,
        mime_type=file.content_type,
        is_verified=False,
        notes=notes,
        uploaded_by=getattr(current_user, "email", str(current_user.id)),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    logger.info(
        "Evidence uploaded year_id=%s doc_type=%s size_kb=%s tenant=%s",
        year_id,
        document_type,
        size_kb,
        current_user.tenant_id,
    )
    return {
        "id": doc.id,
        "document_name": doc.document_name,
        "storage_key": storage_key,
        "file_hash": file_hash,
        "message": "Evidence uploaded successfully",
        "duplicate": False,
    }


@router.patch("/years/{year_id}/evidence/{evidence_id}", response_model=dict)
async def patch_evidence(
    year_id: int,
    evidence_id: int,
    patch: EvidencePatch,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Verify or annotate an evidence document"""
    doc = (
        await db.execute(
            select(CarbonEvidence).where(
                CarbonEvidence.id == evidence_id,
                CarbonEvidence.reporting_year_id == year_id,
                CarbonEvidence.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Evidence document not found")

    if patch.is_verified is not None:
        doc.is_verified = patch.is_verified
    if patch.verified_by is not None:
        doc.verified_by = patch.verified_by
        doc.verified_date = datetime.now(timezone.utc)
    if patch.notes is not None:
        doc.notes = patch.notes

    doc.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Evidence updated", "id": doc.id}


@router.delete("/years/{year_id}/evidence/{evidence_id}", response_model=dict)
async def delete_evidence(
    year_id: int,
    evidence_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Delete an evidence document"""
    doc = (
        await db.execute(
            select(CarbonEvidence).where(
                CarbonEvidence.id == evidence_id,
                CarbonEvidence.reporting_year_id == year_id,
                CarbonEvidence.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Evidence document not found")

    if doc.storage_key:
        try:
            from src.infrastructure.storage import get_storage_service

            await get_storage_service().delete(doc.storage_key)
        except Exception as exc:
            logger.warning("Blob delete failed (continuing): %s", exc)

    await db.delete(doc)
    await db.commit()
    return {"message": "Evidence deleted", "id": evidence_id}


# ============ AI Action Plan Import ============


class ActionImportRow(BaseModel):
    action_title: str
    description: str = ""
    owner: str = ""
    deadline: Optional[str] = None
    category: str = "operational"
    expected_reduction_pct: float = 0.0
    confidence: float = 1.0
    needs_review: bool = False


class ActionImportPreview(BaseModel):
    session_id: str
    year_id: int
    source_filename: str
    extracted_count: int
    rows: list[ActionImportRow]
    extraction_method: str
    warnings: list[str]


class ActionImportConfirm(BaseModel):
    session_id: str
    selected_indices: Optional[list[int]] = None  # None = import all


@router.post("/years/{year_id}/actions/import/extract", response_model=dict, status_code=202)
async def extract_action_plan(
    year_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request: Request,
) -> dict[str, Any]:
    """Upload an action plan document and extract actions using AI"""
    import hashlib
    import json
    import uuid

    year = (
        await db.execute(
            select(CarbonReportingYear).where(
                CarbonReportingYear.id == year_id,
                CarbonReportingYear.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not year:
        raise HTTPException(status_code=404, detail="Reporting year not found")

    form = await request.form()
    file = form.get("file")
    if not file or not hasattr(file, "read"):
        raise HTTPException(status_code=422, detail="A PDF or document file is required")

    contents = await file.read()
    filename = getattr(file, "filename", "upload.pdf") or "upload.pdf"
    file_hash = hashlib.sha256(contents).hexdigest()

    # Extract text
    extracted_text = ""
    extraction_method = "unknown"
    warnings: list[str] = []

    try:
        import io

        import pdfplumber

        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            pages_text = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            extracted_text = "\n".join(pages_text)
        extraction_method = "pdfplumber"
    except Exception as exc:
        warnings.append(f"pdfplumber extraction failed: {exc}")

    if not extracted_text:
        try:
            extracted_text = contents.decode("utf-8", errors="ignore")
            extraction_method = "raw_text"
        except Exception as exc2:
            warnings.append(f"Raw text decode failed: {exc2}")

    # AI extraction
    rows: list[dict] = []
    try:
        from src.domain.services.document_ai_service import DocumentAIService

        ai = DocumentAIService()
        # Use analyze_document and parse custom schema from the summary field
        import httpx

        if ai.api_key:
            headers = {
                "x-api-key": ai.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            ai_prompt = f"""You are a sustainability data extractor. Extract every improvement action from this Planet Mark action plan document.

Return a JSON array. Each element must have exactly these keys:
- action_title (string, max 200 chars)
- description (string)
- owner (string, person or team responsible)
- deadline (string ISO date YYYY-MM-DD or empty string)
- category (one of: energy, transport, waste, water, supply_chain, operational, other)
- expected_reduction_pct (number 0-100, estimated carbon reduction %)
- confidence (number 0.0-1.0, your confidence in the extraction)
- needs_review (boolean, true if data is ambiguous or incomplete)

Document text:
---
{extracted_text[:8000]}
---

Return ONLY the JSON array, no markdown fences, no explanation."""

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{ai.base_url}/messages",
                    headers=headers,
                    json={
                        "model": ai.model,
                        "max_tokens": 4096,
                        "messages": [{"role": "user", "content": ai_prompt}],
                    },
                )
                resp.raise_for_status()
                ai_text = resp.json()["content"][0]["text"]
                rows = json.loads(ai_text)
                extraction_method += "+ai_claude"
        else:
            raise ValueError("No AI API key configured")
    except Exception as exc:
        warnings.append(f"AI extraction failed, falling back to rule-based: {exc}")
        # Rule-based fallback: look for action-like lines
        for line in extracted_text.splitlines():
            line = line.strip()
            if len(line) > 20 and any(
                kw in line.lower()
                for kw in ["reduce", "install", "implement", "switch", "upgrade", "train", "procure", "monitor"]
            ):
                rows.append(
                    {
                        "action_title": line[:200],
                        "description": "",
                        "owner": "",
                        "deadline": None,
                        "category": "operational",
                        "expected_reduction_pct": 0.0,
                        "confidence": 0.4,
                        "needs_review": True,
                    }
                )

    # Store preview in Redis (or fallback in-memory cache via app state)
    session_id = str(uuid.uuid4())
    preview_payload = {
        "session_id": session_id,
        "year_id": year_id,
        "tenant_id": current_user.tenant_id,
        "source_filename": filename,
        "file_hash": file_hash,
        "extracted_count": len(rows),
        "rows": rows,
        "extraction_method": extraction_method,
        "warnings": warnings,
    }

    try:
        import redis.asyncio as aioredis

        redis_url = "redis://localhost:6379"
        try:
            from src.config import settings

            redis_url = getattr(settings, "redis_url", redis_url)
        except Exception:
            pass

        redis = await aioredis.from_url(redis_url)
        await redis.setex(
            f"pm_import:{current_user.tenant_id}:{session_id}",
            3600,
            json.dumps(preview_payload),
        )
        await redis.aclose()
    except Exception as exc:
        warnings.append(f"Redis store failed — session may expire on restart: {exc}")
        # Fallback: store in app state dict
        app = request.app
        if not hasattr(app.state, "_pm_import_sessions"):
            app.state._pm_import_sessions = {}
        app.state._pm_import_sessions[session_id] = preview_payload

    return {
        "session_id": session_id,
        "year_id": year_id,
        "source_filename": filename,
        "extracted_count": len(rows),
        "rows": rows,
        "extraction_method": extraction_method,
        "warnings": warnings,
    }


@router.post("/years/{year_id}/actions/import/confirm", response_model=dict)
async def confirm_action_import(
    year_id: int,
    confirm: ActionImportConfirm,
    db: DbSession,
    current_user: CurrentUser,
    request: Request,
) -> dict[str, Any]:
    """Confirm and persist extracted actions from import session"""
    import json

    preview: Optional[dict] = None

    try:
        import redis.asyncio as aioredis

        redis_url = "redis://localhost:6379"
        try:
            from src.config import settings

            redis_url = getattr(settings, "redis_url", redis_url)
        except Exception:
            pass

        redis = await aioredis.from_url(redis_url)
        raw = await redis.get(f"pm_import:{current_user.tenant_id}:{confirm.session_id}")
        if raw:
            preview = json.loads(raw)
        await redis.aclose()
    except Exception:
        pass

    if not preview:
        app = request.app
        sessions = getattr(getattr(app, "state", None), "_pm_import_sessions", {})
        preview = sessions.get(confirm.session_id)

    if not preview:
        raise HTTPException(status_code=404, detail="Import session not found or expired")

    if preview.get("tenant_id") != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Session belongs to a different tenant")

    rows = preview.get("rows", [])
    if confirm.selected_indices is not None:
        rows = [rows[i] for i in confirm.selected_indices if 0 <= i < len(rows)]

    # Get current action count for sequential IDs
    count_result = await db.execute(
        select(func.count())
        .select_from(ImprovementAction)
        .where(
            ImprovementAction.reporting_year_id == year_id,
            ImprovementAction.tenant_id == current_user.tenant_id,
        )
    )
    base_count = int(count_result.scalar() or 0)

    created_ids = []
    for i, row in enumerate(rows):
        deadline_raw = row.get("deadline")
        deadline_dt = datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1)
        if deadline_raw:
            try:
                deadline_dt = datetime.fromisoformat(deadline_raw)
            except ValueError:
                pass

        action = ImprovementAction(
            tenant_id=current_user.tenant_id,
            reporting_year_id=year_id,
            action_id=f"IMP-{(base_count + i + 1):03d}",
            action_title=str(row.get("action_title", "Imported Action"))[:200],
            specific_description=str(row.get("description", "")),
            achievable_owner=str(row.get("owner", "")),
            time_bound=deadline_dt,
            target_scope=str(row.get("category", "operational")),
            expected_reduction_pct=float(row.get("expected_reduction_pct", 0.0)),
            status="planned",
            progress_percent=0,
            notes=f"Imported from {preview.get('source_filename', 'document')} (confidence: {row.get('confidence', 1.0):.0%})",
        )
        db.add(action)
        created_ids.append(action.action_id)

    await db.commit()

    # Remove session from Redis
    try:
        import redis.asyncio as aioredis

        redis_url = "redis://localhost:6379"
        try:
            from src.config import settings

            redis_url = getattr(settings, "redis_url", redis_url)
        except Exception:
            pass

        redis = await aioredis.from_url(redis_url)
        await redis.delete(f"pm_import:{current_user.tenant_id}:{confirm.session_id}")
        await redis.aclose()
    except Exception:
        pass

    logger.info(
        "Action import confirmed year_id=%s count=%s tenant=%s",
        year_id,
        len(created_ids),
        current_user.tenant_id,
    )
    return {
        "message": f"{len(created_ids)} actions imported",
        "created_count": len(created_ids),
        "action_ids": created_ids,
    }


# ============ Dashboard ============


@router.get("/dashboard", response_model=dict)
async def get_carbon_dashboard(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get Planet Mark carbon management dashboard"""
    try:
        years: list[CarbonReportingYear] = list(
            (
                await db.execute(
                    select(CarbonReportingYear)
                    .where(CarbonReportingYear.tenant_id == current_user.tenant_id)
                    .order_by(desc(CarbonReportingYear.year_number))
                    .limit(3)
                )
            )
            .scalars()
            .all()
        )
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
            message="Planet Mark query failed. Check server logs.",
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

    # Calculate year-on-year change (% vs prior reporting year)
    yoy_change: float | None = None
    if len(years) >= 2:
        prev_year = years[1]
        if prev_year.emissions_per_fte and current_year.emissions_per_fte:
            prev_ef = float(prev_year.emissions_per_fte)
            cur_ef = float(current_year.emissions_per_fte)
            yoy_change = ((cur_ef - prev_ef) / prev_ef) * 100

    # Action summary
    actions: list[ImprovementAction] = list(
        (
            await db.execute(
                select(ImprovementAction).where(
                    ImprovementAction.reporting_year_id == current_year.id,
                    ImprovementAction.tenant_id == current_user.tenant_id,
                )
            )
        )
        .scalars()
        .all()
    )

    overdue_actions = [a for a in actions if a.status != "completed" and a.time_bound < datetime.now(timezone.utc)]

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
            "scope_1": {
                "value": current_year.scope_1_total,
                "label": "Direct (Fleet, Gas)",
            },
            "scope_2": {
                "value": current_year.scope_2_market,
                "label": "Indirect (Electricity)",
            },
            "scope_3": {"value": current_year.scope_3_total, "label": "Value Chain"},
        },
        "data_quality": {
            "scope_1_2": (current_year.scope_1_data_quality or 0) + (current_year.scope_2_data_quality or 0),
            "scope_3": current_year.scope_3_data_quality or 0,
            "target": 12,
        },
        "certification": {
            "status": current_year.certification_status,
            "expiry_date": (current_year.expiry_date.isoformat() if current_year.expiry_date else None),
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
            {
                "label": y.year_label,
                "total": y.total_emissions,
                "per_fte": y.emissions_per_fte,
            }
            for y in years
        ],
    }


# ============ ISO 14001 Cross-Mapping ============


@router.get("/iso14001-mapping", response_model=dict)
async def get_iso14001_mapping(current_user: CurrentUser) -> dict[str, Any]:
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
    result = await db.execute(
        select(EmissionSource).where(
            EmissionSource.reporting_year_id == year.id,
            EmissionSource.tenant_id == year.tenant_id,
        )
    )
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
