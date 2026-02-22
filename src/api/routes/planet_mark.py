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
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.domain.models.user import User
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.planet_mark import (
    ActionCreatedResponse,
    ActionListResponse,
    ActionUpdatedResponse,
    CarbonDashboardResponse,
    CertificationStatusResponse,
    DataQualityAssessmentResponse,
    EmissionSourceCreatedResponse,
    EmissionSourceListResponse,
    FleetRecordCreatedResponse,
    FleetSummaryResponse,
    ISO14001MappingResponse,
    ReportingYearCreatedResponse,
    ReportingYearDetailResponse,
    ReportingYearListResponse,
    Scope3BreakdownResponse,
    UtilityReadingCreatedResponse,
)
from src.api.schemas.setup_required import setup_required_response
from src.api.dependencies.request_context import get_request_id
from src.domain.services.planet_mark_service import PlanetMarkService

logger = logging.getLogger(__name__)

router = APIRouter()


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


@router.get("/years", response_model=ReportingYearListResponse)
async def list_reporting_years(
    request: Request,
    db: DbSession,
) -> dict[str, Any]:
    """List all carbon reporting years with comparison"""
    try:
        return await PlanetMarkService.list_reporting_years(db)
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
    except SQLAlchemyError as e:
        req_id = get_request_id(request)
        logger.exception(
            "Planet Mark years query failed [request_id=%s]: %s",
            req_id,
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorCode.INTERNAL_ERROR,
        )


@router.post("/years", response_model=ReportingYearCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_reporting_year(
    year_data: ReportingYearCreate,
    db: DbSession,
) -> dict[str, Any]:
    """Create a new carbon reporting year"""
    return await PlanetMarkService.create_reporting_year(db, year_data.model_dump())


@router.get("/years/{year_id}", response_model=ReportingYearDetailResponse)
async def get_reporting_year(
    year_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get detailed reporting year data"""
    return await PlanetMarkService.get_reporting_year_detail(db, year_id, current_user.tenant_id)


# ============ Emission Sources ============


@router.post(
    "/years/{year_id}/sources", response_model=EmissionSourceCreatedResponse, status_code=status.HTTP_201_CREATED
)
async def add_emission_source(
    year_id: int,
    source_data: EmissionSourceCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("planetmark:create"))],
) -> dict[str, Any]:
    """Add an emission source with auto-calculation"""
    return await PlanetMarkService.add_emission_source(
        db, year_id, current_user.tenant_id, source_data.model_dump()
    )


@router.get("/years/{year_id}/sources", response_model=EmissionSourceListResponse)
async def list_emission_sources(
    year_id: int,
    db: DbSession,
    scope: Optional[str] = Query(None),
) -> dict[str, Any]:
    """List emission sources for a year"""
    return await PlanetMarkService.list_emission_sources(db, year_id, scope=scope)


# ============ Scope 3 Categories ============


@router.get("/years/{year_id}/scope3", response_model=Scope3BreakdownResponse)
async def get_scope3_breakdown(
    year_id: int,
    db: DbSession,
) -> dict[str, Any]:
    """Get Scope 3 category breakdown"""
    return await PlanetMarkService.get_scope3_breakdown(db, year_id)


# ============ Improvement Actions ============


@router.get("/years/{year_id}/actions", response_model=ActionListResponse)
async def list_improvement_actions(
    year_id: int,
    db: DbSession,
    status_filter: Optional[str] = Query(None, alias="status"),
) -> dict[str, Any]:
    """List SMART improvement actions"""
    return await PlanetMarkService.list_improvement_actions(db, year_id, status_filter=status_filter)


@router.post("/years/{year_id}/actions", response_model=ActionCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_improvement_action(
    year_id: int,
    action_data: ImprovementActionCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("planetmark:create"))],
) -> dict[str, Any]:
    """Create a SMART improvement action"""
    return await PlanetMarkService.create_improvement_action(
        db, year_id, current_user.tenant_id, action_data.model_dump()
    )


@router.put("/years/{year_id}/actions/{action_id}", response_model=ActionUpdatedResponse)
async def update_action_status(
    year_id: int,
    action_id: int,
    status_data: ActionStatusUpdate,
    db: DbSession,
) -> dict[str, Any]:
    """Update improvement action status"""
    return await PlanetMarkService.update_action_status(
        db, year_id, action_id, status_data.model_dump(exclude_unset=True)
    )


# ============ Data Quality ============


@router.get("/years/{year_id}/data-quality", response_model=DataQualityAssessmentResponse)
async def get_data_quality_assessment(
    year_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get data quality assessment with recommendations"""
    return await PlanetMarkService.get_data_quality_assessment(db, year_id, current_user.tenant_id)


# ============ Fleet Integration ============


@router.post("/years/{year_id}/fleet", response_model=FleetRecordCreatedResponse, status_code=status.HTTP_201_CREATED)
async def add_fleet_record(
    year_id: int,
    fleet_data: FleetRecordCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("planetmark:create"))],
) -> dict[str, Any]:
    """Add fleet fuel consumption record"""
    return await PlanetMarkService.add_fleet_record(
        db, year_id, current_user.tenant_id, fleet_data.model_dump()
    )


@router.get("/years/{year_id}/fleet/summary", response_model=FleetSummaryResponse)
async def get_fleet_summary(
    year_id: int,
    db: DbSession,
) -> dict[str, Any]:
    """Get fleet emissions summary with driver leaderboard"""
    return await PlanetMarkService.get_fleet_summary(db, year_id)


# ============ Utility Integration ============


@router.post(
    "/years/{year_id}/utilities", response_model=UtilityReadingCreatedResponse, status_code=status.HTTP_201_CREATED
)
async def add_utility_reading(
    year_id: int,
    reading_data: UtilityReadingCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("planetmark:create"))],
) -> dict[str, Any]:
    """Add utility meter reading"""
    return await PlanetMarkService.add_utility_reading(
        db, year_id, current_user.tenant_id, reading_data.model_dump()
    )


# ============ Certification ============


@router.get("/years/{year_id}/certification", response_model=CertificationStatusResponse)
async def get_certification_status(
    year_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get certification status and evidence checklist"""
    return await PlanetMarkService.get_certification_status(db, year_id, current_user.tenant_id)


# ============ Dashboard ============


@router.get("/dashboard", response_model=CarbonDashboardResponse)
async def get_carbon_dashboard(
    request: Request,
    db: DbSession,
) -> dict[str, Any]:
    """Get Planet Mark carbon management dashboard"""
    try:
        result = await PlanetMarkService.get_carbon_dashboard(db)
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
    except SQLAlchemyError as e:
        req_id = get_request_id(request)
        logger.exception(
            "Planet Mark dashboard query failed [request_id=%s]: %s",
            req_id,
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorCode.INTERNAL_ERROR,
        )

    if result is None:
        return setup_required_response(
            module="planet-mark",
            message="No carbon reporting years configured",
            next_action="Create a reporting year via POST /api/v1/planet-mark/years",
            request_id=get_request_id(request),
        )

    return result


# ============ ISO 14001 Cross-Mapping ============


@router.get("/iso14001-mapping", response_model=ISO14001MappingResponse)
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
