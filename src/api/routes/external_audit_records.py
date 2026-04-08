"""External audit record registry routes -- cross-scheme specialist view API."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from src.api.dependencies import CurrentUser, DbSession
from src.domain.models.external_audit_record import ExternalAuditRecord

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
@router.get("/")
async def list_records(
    db: DbSession,
    current_user: CurrentUser,
    scheme: Optional[str] = Query(None, description="Filter by scheme code (e.g. iso, planet_mark, customer_other)"),
    status: Optional[str] = Query(None, description="Filter by record status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """List external audit records for the current tenant, optionally filtered by scheme."""
    q = select(ExternalAuditRecord).where(ExternalAuditRecord.tenant_id == current_user.tenant_id)
    count_q = (
        select(func.count())
        .select_from(ExternalAuditRecord)
        .where(ExternalAuditRecord.tenant_id == current_user.tenant_id)
    )

    if scheme:
        schemes = [s.strip() for s in scheme.split(",")]
        q = q.where(ExternalAuditRecord.scheme.in_(schemes))
        count_q = count_q.where(ExternalAuditRecord.scheme.in_(schemes))
    if status:
        q = q.where(ExternalAuditRecord.status == status)
        count_q = count_q.where(ExternalAuditRecord.status == status)

    total = (await db.execute(count_q)).scalar() or 0
    q = q.order_by(ExternalAuditRecord.report_date.desc().nullslast(), ExternalAuditRecord.id.desc())
    q = q.offset(skip).limit(limit)
    result = await db.execute(q)
    records = result.scalars().all()

    return {
        "total": total,
        "records": [_record_to_dict(r) for r in records],
    }


@router.get("/dashboard")
async def record_dashboard(
    db: DbSession,
    current_user: CurrentUser,
    scheme: Optional[str] = Query(None, description="Filter by scheme code"),
) -> dict:
    """Aggregated KPIs for external audit records."""
    base = select(ExternalAuditRecord).where(ExternalAuditRecord.tenant_id == current_user.tenant_id)
    if scheme:
        schemes = [s.strip() for s in scheme.split(",")]
        base = base.where(ExternalAuditRecord.scheme.in_(schemes))

    total_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(total_q)).scalar() or 0

    avg_score_q = select(func.avg(ExternalAuditRecord.score_percentage)).where(
        ExternalAuditRecord.tenant_id == current_user.tenant_id,
        ExternalAuditRecord.score_percentage.is_not(None),
    )
    findings_q = select(
        func.coalesce(func.sum(ExternalAuditRecord.findings_count), 0),
        func.coalesce(func.sum(ExternalAuditRecord.major_findings), 0),
        func.coalesce(func.sum(ExternalAuditRecord.minor_findings), 0),
        func.coalesce(func.sum(ExternalAuditRecord.observations), 0),
    ).where(ExternalAuditRecord.tenant_id == current_user.tenant_id)

    if scheme:
        schemes_list = [s.strip() for s in scheme.split(",")]
        avg_score_q = avg_score_q.where(ExternalAuditRecord.scheme.in_(schemes_list))
        findings_q = findings_q.where(ExternalAuditRecord.scheme.in_(schemes_list))

    avg_score = (await db.execute(avg_score_q)).scalar()
    findings_row = (await db.execute(findings_q)).one()

    return {
        "total_records": total,
        "average_score_percentage": round(avg_score, 1) if avg_score is not None else None,
        "total_findings": findings_row[0],
        "total_major": findings_row[1],
        "total_minor": findings_row[2],
        "total_observations": findings_row[3],
    }


@router.get("/{record_id}")
async def get_record(
    record_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Get a single external audit record by ID."""
    result = await db.execute(
        select(ExternalAuditRecord).where(
            ExternalAuditRecord.id == record_id,
            ExternalAuditRecord.tenant_id == current_user.tenant_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        from src.domain.errors import NotFoundError

        raise NotFoundError(f"External audit record {record_id} not found")
    return _record_to_dict(record)


def _record_to_dict(r: ExternalAuditRecord) -> dict:
    return {
        "id": r.id,
        "tenant_id": r.tenant_id,
        "scheme": r.scheme,
        "scheme_version": r.scheme_version,
        "scheme_label": r.scheme_label,
        "audit_run_id": r.audit_run_id,
        "import_job_id": r.import_job_id,
        "issuer_name": r.issuer_name,
        "company_name": r.company_name,
        "report_date": r.report_date.isoformat() if r.report_date else None,
        "overall_score": r.overall_score,
        "max_score": r.max_score,
        "score_percentage": r.score_percentage,
        "section_scores": r.section_scores,
        "outcome_status": r.outcome_status,
        "findings_count": r.findings_count,
        "major_findings": r.major_findings,
        "minor_findings": r.minor_findings,
        "observations": r.observations,
        "analysis_summary": r.analysis_summary,
        "status": r.status,
    }
