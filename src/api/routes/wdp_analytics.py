"""Workforce Development Platform analytics endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import case, func, or_, select

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.analytics import WDPAnalyticsSummaryResponse, WDPEngineerMatrixResponse, WDPTrendsResponse
from src.api.utils.errors import api_error

router = APIRouter()


def _tenant_filter(model, tenant_id):
    """Apply tenant filter: model.tenant_id == tenant_id OR model.tenant_id IS NULL."""
    return or_(
        model.tenant_id == tenant_id,
        model.tenant_id.is_(None),
    )


def _is_workforce_manager(user: CurrentUser) -> bool:
    role_names = {r.name.lower() for r in getattr(user, "roles", []) or []}
    return bool(getattr(user, "is_superuser", False) or "admin" in role_names or "supervisor" in role_names)


def _assert_wdp_analytics_access(user: CurrentUser) -> None:
    if _is_workforce_manager(user):
        return
    raise HTTPException(
        status_code=403,
        detail=api_error(
            ErrorCode.PERMISSION_DENIED,
            "You do not have permission to access workforce analytics",
        ),
    )


def _latest_records_by_asset_type(records):
    baseline = datetime.min.replace(tzinfo=timezone.utc)

    def sort_key(record):
        return (
            getattr(record, "assessed_at", None) or getattr(record, "created_at", None) or baseline,
            getattr(record, "id", 0),
        )

    latest = {}
    for record in records:
        current = latest.get(record.asset_type_id)
        if current is None or sort_key(record) > sort_key(current):
            latest[record.asset_type_id] = record
    return latest


def _latest_records_by_engineer_asset(records):
    baseline = datetime.min.replace(tzinfo=timezone.utc)

    def sort_key(record):
        return (
            getattr(record, "assessed_at", None) or getattr(record, "created_at", None) or baseline,
            getattr(record, "id", 0),
        )

    latest = {}
    for record in records:
        key = (record.engineer_id, record.asset_type_id)
        current = latest.get(key)
        if current is None or sort_key(record) > sort_key(current):
            latest[key] = record
    return latest.values()


def _effective_competency_state(record):
    state = record.state.value if hasattr(record.state, "value") else str(record.state)
    expires_at = getattr(record, "expires_at", None)
    if expires_at is not None and expires_at <= datetime.now(timezone.utc) and state in {"active", "due"}:
        return "expired"
    return state


@router.get("/summary", response_model=WDPAnalyticsSummaryResponse)
async def get_wdp_summary(db: DbSession, user: CurrentUser):
    """Get summary KPIs for the workforce development dashboard."""
    _assert_wdp_analytics_access(user)
    from src.domain.models.assessment import AssessmentRun, AssessmentStatus
    from src.domain.models.engineer import CompetencyLifecycleState, CompetencyRecord, Engineer
    from src.domain.models.induction import InductionRun, InductionStatus

    tenant_filter_eng = _tenant_filter(Engineer, user.tenant_id)
    tenant_filter_comp = _tenant_filter(CompetencyRecord, user.tenant_id)
    tenant_filter_assess = _tenant_filter(AssessmentRun, user.tenant_id)
    tenant_filter_ind = _tenant_filter(InductionRun, user.tenant_id)

    # Engineer counts
    eng_count = (
        await db.scalar(select(func.count(Engineer.id)).where(Engineer.is_active == True).where(tenant_filter_eng)) or 0
    )

    # Competency counts by state
    competency_records = (await db.execute(select(CompetencyRecord).where(tenant_filter_comp))).scalars().all()
    latest_competency_records = _latest_records_by_engineer_asset(competency_records)
    comp_counts = {state.value: 0 for state in CompetencyLifecycleState}
    for record in latest_competency_records:
        state_value = _effective_competency_state(record)
        comp_counts[state_value] = comp_counts.get(state_value, 0) + 1

    # Assessment counts by status
    assessment_total = await db.scalar(select(func.count(AssessmentRun.id)).where(tenant_filter_assess)) or 0
    assessment_completed = (
        await db.scalar(
            select(func.count(AssessmentRun.id))
            .where(AssessmentRun.status == AssessmentStatus.COMPLETED)
            .where(tenant_filter_assess)
        )
        or 0
    )

    # Induction counts
    induction_total = await db.scalar(select(func.count(InductionRun.id)).where(tenant_filter_ind)) or 0
    induction_completed = (
        await db.scalar(
            select(func.count(InductionRun.id))
            .where(InductionRun.status == InductionStatus.COMPLETED)
            .where(tenant_filter_ind)
        )
        or 0
    )

    return {
        "engineers": {"total": eng_count},
        "competencies": comp_counts,
        "assessments": {"total": assessment_total, "completed": assessment_completed},
        "inductions": {"total": induction_total, "completed": induction_completed},
    }


@router.get("/engineer-matrix", response_model=WDPEngineerMatrixResponse)
async def get_engineer_competency_matrix(db: DbSession, user: CurrentUser):
    """Get a competency matrix: engineer x asset type with status."""
    _assert_wdp_analytics_access(user)
    from src.domain.models.asset import AssetType
    from src.domain.models.engineer import CompetencyRecord, Engineer

    tenant_filter_eng = _tenant_filter(Engineer, user.tenant_id)
    tenant_filter_at = _tenant_filter(AssetType, user.tenant_id)
    tenant_filter_comp = _tenant_filter(CompetencyRecord, user.tenant_id)

    engineers = (
        (await db.execute(select(Engineer).where(Engineer.is_active == True).where(tenant_filter_eng))).scalars().all()
    )

    asset_types = (
        (await db.execute(select(AssetType).where(AssetType.is_active == True).where(tenant_filter_at))).scalars().all()
    )

    matrix = []
    for eng in engineers:
        records = (
            (
                await db.execute(
                    select(CompetencyRecord).where(CompetencyRecord.engineer_id == eng.id).where(tenant_filter_comp)
                )
            )
            .scalars()
            .all()
        )

        latest_records = _latest_records_by_asset_type(records)
        record_map = {
            asset_type_id: _effective_competency_state(record) for asset_type_id, record in latest_records.items()
        }

        row = {
            "engineer_id": eng.id,
            "user_id": eng.user_id,
            "employee_number": eng.employee_number,
            "competencies": {at.id: record_map.get(at.id, "not_assessed") for at in asset_types},
        }
        matrix.append(row)

    return {
        "asset_types": [
            {
                "id": at.id,
                "name": at.name,
                "category": (at.category.value if hasattr(at.category, "value") else str(at.category)),
            }
            for at in asset_types
        ],
        "engineers": matrix,
    }


@router.get("/trends", response_model=WDPTrendsResponse)
async def get_competency_trends(db: DbSession, user: CurrentUser):
    """Get assessment and competency trends over time (last 12 months)."""
    _assert_wdp_analytics_access(user)
    from src.domain.models.assessment import AssessmentOutcome, AssessmentRun
    from src.domain.models.induction import InductionRun, InductionStatus

    tenant_filter_assess = _tenant_filter(AssessmentRun, user.tenant_id)
    tenant_filter_ind = _tenant_filter(InductionRun, user.tenant_id)

    month_col = func.date_trunc("month", AssessmentRun.created_at)
    assessments_by_month = (
        await db.execute(
            select(
                month_col.label("month"),
                func.count(AssessmentRun.id).label("total"),
                func.count(case((AssessmentRun.outcome == AssessmentOutcome.PASS, 1))).label("passed"),
                func.count(case((AssessmentRun.outcome == AssessmentOutcome.FAIL, 1))).label("failed"),
            )
            .where(tenant_filter_assess)
            .group_by(month_col)
            .order_by(month_col.desc())
            .limit(12)
        )
    ).all()
    assessments_by_month = list(reversed(assessments_by_month))

    ind_month_col = func.date_trunc("month", InductionRun.created_at)
    inductions_by_month = (
        await db.execute(
            select(
                ind_month_col.label("month"),
                func.count(InductionRun.id).label("total"),
                func.count(case((InductionRun.status == InductionStatus.COMPLETED, 1))).label("completed"),
            )
            .where(tenant_filter_ind)
            .group_by(ind_month_col)
            .order_by(ind_month_col.desc())
            .limit(12)
        )
    ).all()
    inductions_by_month = list(reversed(inductions_by_month))

    return {
        "assessments_by_month": [
            {
                "month": row.month.isoformat() if row.month else None,
                "total": row.total,
                "passed": row.passed,
                "failed": row.failed,
            }
            for row in assessments_by_month
        ],
        "inductions_by_month": [
            {
                "month": row.month.isoformat() if row.month else None,
                "total": row.total,
                "completed": row.completed,
            }
            for row in inductions_by_month
        ],
    }
