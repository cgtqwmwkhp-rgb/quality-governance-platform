"""
UVDB Achilles Verify B2 Audit Protocol API Routes

Provides endpoints for:
- UVDB Audit management
- Section and question management
- Audit responses and scoring
- KPI tracking (Section 15)
- ISO cross-mapping
"""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, ProgrammingError

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.setup_required import setup_required_response
from src.domain.exceptions import NotFoundError
from src.domain.models.audit import AuditRun
from src.domain.models.external_audit_import import ExternalAuditImportJob
from src.domain.models.user import User
from src.domain.models.uvdb_achilles import (
    UVDBAudit,
    UVDBAuditResponse,
    UVDBISOCrossMapping,
    UVDBKPIRecord,
    UVDBQuestion,
    UVDBSection,
)
from src.domain.services.uvdb_protocol_export_service import build_protocol_export, build_protocol_structure_payload
from src.domain.services.uvdb_service import (
    build_section_title_index,
    match_protocol_section,
    normalise_section_score,
    resolve_provenance,
    resolve_score_source,
)
from src.domain.uvdb.protocol_b2_v118 import PROTOCOL_VERSION, UVDB_B2_SECTIONS, build_content_coverage

router = APIRouter()
logger = logging.getLogger(__name__)


# UVDB B2 protocol structure lives in src/domain/uvdb/protocol_b2_v118.py (SSOT).


# ============ Pydantic Schemas ============


class AuditCreate(BaseModel):
    company_name: str = Field(..., min_length=3, max_length=255)
    company_id: Optional[str] = None
    audit_type: str = Field(default="B2")
    audit_scope: Optional[str] = None
    audit_date: Optional[datetime] = None
    lead_auditor: Optional[str] = None


class AuditUpdate(BaseModel):
    status: Optional[str] = None
    total_score: Optional[float] = None
    audit_notes: Optional[str] = None
    lead_auditor: Optional[str] = None


class ResponseCreate(BaseModel):
    question_id: int
    mse_response: Optional[int] = Field(None, ge=0, le=3)
    site_response: Optional[int] = Field(None, ge=0, le=3)
    sub_question_responses: Optional[dict] = None
    evidence_provided: Optional[str] = None
    documents_presented: Optional[list] = None
    finding_type: Optional[str] = None
    finding_description: Optional[str] = None
    auditor_notes: Optional[str] = None


class KPICreate(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    total_man_hours: Optional[int] = None
    fatalities: int = Field(default=0)
    riddor_reportable: int = Field(default=0)
    lost_time_incidents_1_7_days: int = Field(default=0)
    medical_treatment_incidents: int = Field(default=0)
    first_aid_incidents: int = Field(default=0)
    dangerous_occurrences: int = Field(default=0)
    near_misses: int = Field(default=0)
    hse_improvement_notices: int = Field(default=0)
    hse_prohibition_notices: int = Field(default=0)
    hse_prosecutions: int = Field(default=0)
    env_minor_incidents: int = Field(default=0)
    env_reportable_incidents: int = Field(default=0)
    env_enforcement_actions: int = Field(default=0)


# ============ Score Provenance ============


ImportLinks = dict[str, tuple[Optional[int], Optional[int]]]


async def _resolve_import_links(
    db: Any,
    references: list[str],
    *,
    tenant_id: Optional[int] = None,
) -> tuple[ImportLinks, bool]:
    """Map audit reference -> (audit_run_id, latest import_job_id).

    A UVDB audit carries an imported score when an external audit import job
    was promoted against its reference. Resolved in one query for the whole
    page rather than per row, and scoped to the caller's tenant so the run and
    job identifiers returned to the client cannot come from another tenant.

    Returns (links, resolved). *resolved* is False when the linkage tables are
    unreadable, which callers must surface as unknown provenance rather than
    silently reporting the score as calculated in-app.
    """
    wanted = [reference for reference in references if reference]
    if not wanted:
        return {}, True

    tenant_filter = [AuditRun.tenant_id == tenant_id] if tenant_id is not None else []

    try:
        result = await db.execute(
            select(
                AuditRun.reference_number,
                AuditRun.id,
                func.max(ExternalAuditImportJob.id),
            )
            .outerjoin(ExternalAuditImportJob, ExternalAuditImportJob.audit_run_id == AuditRun.id)
            .where(AuditRun.reference_number.in_(wanted), *tenant_filter)
            .group_by(AuditRun.reference_number, AuditRun.id)
        )
        rows = result.all()
    except (ProgrammingError, OperationalError) as e:
        logger.warning("UVDB import-link lookup failed: %s", str(e)[:200])
        return {}, False

    links: ImportLinks = {}
    for reference, run_id, job_id in rows:
        # Defensive: one reference should map to one run, but keep the row that
        # actually carries an import job if duplicates ever exist.
        existing = links.get(reference)
        if existing is None or (existing[1] is None and job_id is not None):
            links[reference] = (run_id, job_id)
    return links, True


# ============ Protocol Structure Endpoints ============


@router.get("/protocol", response_model=dict)
async def get_protocol_structure(current_user: CurrentUser) -> dict[str, Any]:
    """Get the complete UVDB B2 Audit Protocol structure"""
    return build_protocol_structure_payload(UVDB_B2_SECTIONS)


@router.get("/protocol/export")
async def export_protocol_pack(
    current_user: CurrentUser,
    export_format: str = Query(default="json", alias="format", description="Export format: json or xlsx"),
) -> Response:
    """Download the UVDB B2 protocol pack for offline review."""
    body, filename, media_type = build_protocol_export(
        UVDB_B2_SECTIONS,
        export_format=export_format,  # type: ignore[arg-type]
        exported_by=getattr(current_user, "email", None),
    )
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-UVDB-Protocol-Pack-Version": "uvdb-protocol-1.1",
        },
    )


@router.get("/sections", response_model=dict)
async def list_sections(
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """List all UVDB B2 sections"""
    # Return from static data or database
    sections = []
    coverage = build_content_coverage()
    for section in UVDB_B2_SECTIONS:
        sections.append(
            {
                "number": section["number"],
                "title": section["title"],
                "max_score": section["max_score"],
                "question_count": len(section.get("questions", [])),  # type: ignore[arg-type]
                "iso_mapping": section.get("iso_mapping", {}),
                "content_status": section.get("content_status", "loaded"),
                "title_provisional": section.get("title_provisional", False),
            }
        )

    return {
        "total_sections": len(sections),
        "content_coverage": coverage,
        "sections": sections,
    }


@router.get("/sections/{section_number}/questions", response_model=dict)
async def get_section_questions(
    section_number: str,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get questions for a specific UVDB section"""
    section_data = None
    for section in UVDB_B2_SECTIONS:
        if section["number"] == section_number:
            section_data = section
            break

    if not section_data:
        raise NotFoundError("Section not found")

    return {
        "section_number": section_data["number"],
        "section_title": section_data["title"],
        "max_score": section_data["max_score"],
        "iso_mapping": section_data.get("iso_mapping", {}),
        "content_status": section_data.get("content_status", "loaded"),
        "title_provisional": section_data.get("title_provisional", False),
        "questions": section_data.get("questions", []),
    }


# ============ Audit Management ============


@router.get("/audits", response_model=dict)
async def list_audits(
    db: DbSession,
    current_user: CurrentUser,
    status: Optional[str] = Query(None),
    company_name: Optional[str] = Query(None),
    audit_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    max_score: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    """List UVDB audits with filtering"""
    tenant_id = getattr(current_user, "tenant_id", None) if current_user else None
    filters = []
    if tenant_id is not None:
        filters.append(UVDBAudit.tenant_id == tenant_id)
    if status:
        filters.append(UVDBAudit.status == status)
    if company_name:
        filters.append(UVDBAudit.company_name.ilike(f"%{company_name}%"))
    if audit_type:
        filters.append(UVDBAudit.audit_type == audit_type)
    if date_from:
        filters.append(UVDBAudit.audit_date >= date_from)
    if date_to:
        filters.append(UVDBAudit.audit_date <= date_to)
    if min_score is not None:
        filters.append(UVDBAudit.percentage_score >= min_score)
    if max_score is not None:
        filters.append(UVDBAudit.percentage_score <= max_score)
    if search:
        search_filter = f"%{search}%"
        filters.append(
            UVDBAudit.company_name.ilike(search_filter)
            | UVDBAudit.audit_reference.ilike(search_filter)
            | UVDBAudit.lead_auditor.ilike(search_filter)
        )

    try:
        count_result = await db.execute(select(func.count()).select_from(UVDBAudit).where(*filters))
        total = count_result.scalar()

        rows_result = await db.execute(
            select(UVDBAudit).where(*filters).order_by(UVDBAudit.audit_date.desc()).offset(skip).limit(limit)
        )
        audits = rows_result.scalars().all()
    except (ProgrammingError, OperationalError) as e:
        logger.warning("UVDB audits query failed (likely missing schema): %s", str(e)[:200])
        return setup_required_response(
            module="uvdb",
            message="UVDB audit tables are not initialized in this environment.",
            next_action="Apply the latest UVDB database migrations before using live audits.",
        )

    links, links_resolved = await _resolve_import_links(db, [a.audit_reference for a in audits], tenant_id=tenant_id)

    items = []
    for a in audits:
        run_id, job_id = links.get(a.audit_reference, (None, None))
        items.append(
            {
                "id": a.id,
                "audit_reference": a.audit_reference,
                "company_name": a.company_name,
                "audit_type": a.audit_type,
                "audit_date": a.audit_date.isoformat() if a.audit_date else None,
                "status": a.status,
                "percentage_score": a.percentage_score,
                "score_source": resolve_score_source(
                    a.percentage_score,
                    import_job_id=job_id,
                    provenance_resolved=links_resolved,
                ),
                "lead_auditor": a.lead_auditor,
                "audit_run_id": run_id,
                "import_job_id": job_id,
            }
        )

    return {"total": total, "audits": items}


@router.post("/audits", response_model=dict, status_code=201)
async def create_audit(
    audit_data: AuditCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
) -> dict[str, Any]:
    """Create a new UVDB audit"""
    count_result = await db.execute(select(func.count()).select_from(UVDBAudit))
    count = count_result.scalar()
    audit_reference = f"UVDB-{datetime.now(timezone.utc).year}-{((count or 0) + 1):04d}"

    audit = UVDBAudit(
        audit_reference=audit_reference,
        status="scheduled",
        **audit_data.model_dump(),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    return {
        "id": audit.id,
        "audit_reference": audit_reference,
        "message": "UVDB audit created",
    }


@router.get("/audits/{audit_id}", response_model=dict)
async def get_audit(
    audit_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get audit details including linked source PDF and score breakdown."""
    result = await db.execute(select(UVDBAudit).where(UVDBAudit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit:
        raise NotFoundError("Audit not found")

    source_asset_id: int | None = None
    source_filename: str | None = None
    audit_run_id: int | None = None
    import_job_id: int | None = None
    provenance_resolved = True

    tenant_id = getattr(current_user, "tenant_id", None) if current_user else None
    run_tenant_filter = [AuditRun.tenant_id == tenant_id] if tenant_id is not None else []

    try:
        run_result = await db.execute(
            select(AuditRun).where(AuditRun.reference_number == audit.audit_reference, *run_tenant_filter)
        )
        run = run_result.scalar_one_or_none()
        if run:
            audit_run_id = run.id
            job_result = await db.execute(
                select(ExternalAuditImportJob)
                .where(ExternalAuditImportJob.audit_run_id == run.id)
                .order_by(ExternalAuditImportJob.id.desc())
                .limit(1)
            )
            job = job_result.scalar_one_or_none()
            if job:
                import_job_id = job.id
                source_asset_id = job.source_document_asset_id
                source_filename = job.source_filename
            elif run.source_document_asset_id:
                source_asset_id = run.source_document_asset_id
                source_filename = run.source_document_label
    except (ProgrammingError, OperationalError):
        logger.debug("Could not resolve source document for audit %s", audit_id)
        provenance_resolved = False

    score_source = resolve_score_source(
        audit.percentage_score,
        import_job_id=import_job_id,
        provenance_resolved=provenance_resolved,
    )
    entry_source = resolve_provenance(import_job_id=import_job_id, provenance_resolved=provenance_resolved)

    scores = audit.section_scores or {}
    raw_breakdown = scores.get("sections", []) if isinstance(scores, dict) else []
    score_breakdown = [
        normalise_section_score(entry, audit_reference=audit.audit_reference, score_source=entry_source)
        for entry in raw_breakdown
        if isinstance(entry, dict)
    ]

    return {
        "id": audit.id,
        "audit_reference": audit.audit_reference,
        "company_name": audit.company_name,
        "company_id": audit.company_id,
        "audit_type": audit.audit_type,
        "audit_scope": audit.audit_scope,
        "audit_date": audit.audit_date.isoformat() if audit.audit_date else None,
        "status": audit.status,
        "lead_auditor": audit.lead_auditor,
        "total_score": audit.total_score,
        "max_possible_score": audit.max_possible_score,
        "percentage_score": audit.percentage_score,
        "score_source": score_source,
        "section_scores": audit.section_scores,
        "score_breakdown": score_breakdown,
        "source_document_asset_id": source_asset_id,
        "source_filename": source_filename,
        "audit_run_id": audit_run_id,
        "import_job_id": import_job_id,
        "findings_count": audit.findings_count,
        "major_findings": audit.major_findings,
        "minor_findings": audit.minor_findings,
        "observations": audit.observations,
        "certifications": {
            "iso_9001": audit.iso_9001_verified,
            "iso_14001": audit.iso_14001_verified,
            "iso_45001": audit.iso_45001_verified,
            "iso_27001": audit.iso_27001_verified,
            "ukas_accredited": audit.ukas_accredited,
        },
        "cdm_compliant": audit.cdm_compliant,
        "fors_accredited": audit.fors_accredited,
        "fors_level": audit.fors_level,
        "audit_notes": audit.audit_notes,
    }


@router.put("/audits/{audit_id}", response_model=dict)
async def update_audit(
    audit_id: int,
    audit_data: AuditUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> dict[str, Any]:
    """Update audit"""
    result = await db.execute(select(UVDBAudit).where(UVDBAudit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit:
        raise NotFoundError("Audit not found")

    update_data = audit_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(audit, key, value)

    audit.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Audit updated", "id": audit.id}


# ============ Audit Responses ============


@router.post("/audits/{audit_id}/responses", response_model=dict, status_code=201)
async def create_response(
    audit_id: int,
    response_data: ResponseCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
) -> dict[str, Any]:
    """Record an audit response"""
    result = await db.execute(select(UVDBAudit).where(UVDBAudit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit:
        raise NotFoundError("Audit not found")

    response = UVDBAuditResponse(
        audit_id=audit_id,
        **response_data.model_dump(),
    )
    db.add(response)
    await db.commit()
    await db.refresh(response)

    return {"id": response.id, "message": "Response recorded"}


@router.get("/audits/{audit_id}/responses", response_model=dict)
async def get_audit_responses(
    audit_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get all responses for an audit"""
    result = await db.execute(select(UVDBAudit).where(UVDBAudit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit:
        raise NotFoundError("Audit not found")

    resp_result = await db.execute(select(UVDBAuditResponse).where(UVDBAuditResponse.audit_id == audit_id))
    responses = resp_result.scalars().all()

    return {
        "audit_id": audit_id,
        "total_responses": len(responses),
        "responses": [
            {
                "id": r.id,
                "question_id": r.question_id,
                "mse_response": r.mse_response,
                "site_response": r.site_response,
                "finding_type": r.finding_type,
                "finding_description": r.finding_description,
            }
            for r in responses
        ],
    }


# ============ KPI Management ============


@router.post("/audits/{audit_id}/kpis", response_model=dict, status_code=201)
async def add_kpi_record(
    audit_id: int,
    kpi_data: KPICreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
) -> dict[str, Any]:
    """Add KPI record for an audit year"""
    result = await db.execute(select(UVDBAudit).where(UVDBAudit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit:
        raise NotFoundError("Audit not found")

    # Calculate rates if man hours provided
    ltifr = None
    if kpi_data.total_man_hours and kpi_data.total_man_hours > 0:
        lost_time = kpi_data.lost_time_incidents_1_7_days + kpi_data.riddor_reportable
        ltifr = (lost_time / kpi_data.total_man_hours) * 1000000

    kpi = UVDBKPIRecord(
        audit_id=audit_id,
        ltifr=ltifr,
        **kpi_data.model_dump(),
    )
    db.add(kpi)
    await db.commit()
    await db.refresh(kpi)

    return {"id": kpi.id, "message": "KPI record added", "ltifr": ltifr}


@router.get("/audits/{audit_id}/kpis", response_model=dict)
async def get_audit_kpis(
    audit_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get KPI records for an audit"""
    kpi_result = await db.execute(
        select(UVDBKPIRecord).where(UVDBKPIRecord.audit_id == audit_id).order_by(UVDBKPIRecord.year.desc())
    )
    kpis = kpi_result.scalars().all()

    return {
        "audit_id": audit_id,
        "kpi_records": [
            {
                "year": k.year,
                "total_man_hours": k.total_man_hours,
                "fatalities": k.fatalities,
                "riddor_reportable": k.riddor_reportable,
                "lost_time_incidents": k.lost_time_incidents_1_7_days,
                "medical_treatment_incidents": k.medical_treatment_incidents,
                "first_aid_incidents": k.first_aid_incidents,
                "dangerous_occurrences": k.dangerous_occurrences,
                "near_misses": k.near_misses,
                "hse_notices": k.hse_improvement_notices + k.hse_prohibition_notices,
                "hse_prosecutions": k.hse_prosecutions,
                "env_incidents": k.env_minor_incidents + k.env_reportable_incidents,
                "ltifr": k.ltifr,
            }
            for k in kpis
        ],
    }


# ============ ISO Cross-Mapping ============


@router.get("/iso-mapping", response_model=dict)
async def get_iso_cross_mapping(current_user: CurrentUser) -> dict[str, Any]:
    """Get cross-mapping between UVDB sections and ISO standards"""
    mappings = []

    for section in UVDB_B2_SECTIONS:
        for question in section.get("questions", []):  # type: ignore[attr-defined]
            if "iso_mapping" in question and question["iso_mapping"]:
                mappings.append(
                    {
                        "uvdb_section": section["number"],
                        "uvdb_question": question["number"],
                        "uvdb_text": (
                            question["text"][:100] + "..." if len(question["text"]) > 100 else question["text"]
                        ),
                        "iso_9001": question["iso_mapping"].get("9001", []),
                        "iso_14001": question["iso_mapping"].get("14001", []),
                        "iso_45001": question["iso_mapping"].get("45001", []),
                        "iso_27001": question["iso_mapping"].get("27001", []),
                    }
                )

    return {
        "description": "Cross-mapping between UVDB B2 questions and ISO standard clauses",
        "total_mappings": len(mappings),
        "mappings": mappings,
        "summary": {
            "iso_9001_aligned": "Section 1.1 (QMS), Section 2 (Quality Control), Sections 12-13 (Supplier Management)",
            "iso_14001_aligned": "Section 1.3 (EMS), Sections 8-11 (Environmental — pending v11.8 PDF), Section 15 (KPIs)",
            "iso_45001_aligned": "Section 1.2 (OH&S), Sections 3-7 (H&S — pending v11.8 PDF), Section 14 (Equipment), Section 15 (KPIs)",
            "iso_27001_aligned": "Section 2.3 (Information Security)",
        },
        "content_coverage": build_content_coverage(),
    }


# ============ Section Scores ============


def _empty_section_scores() -> dict[str, Any]:
    return {
        "sections": {},
        "unmapped_sections": [],
        "audit_reference": None,
        "score_source": None,
    }


@router.get("/sections/scores", response_model=dict)
async def get_section_scores(
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Return per-section scores from the most recent completed UVDB audit.

    Section scores on an imported audit are lifted from the source report, not
    computed from protocol responses, so every entry is tagged with its
    provenance. Entries whose label cannot be matched to a protocol section
    with certainty are returned under ``unmapped_sections`` so the score stays
    visible instead of being dropped or pinned to the wrong section.
    """
    tenant_id = getattr(current_user, "tenant_id", None) if current_user else None
    tenant_filter = [UVDBAudit.tenant_id == tenant_id] if tenant_id is not None else []

    try:
        result = await db.execute(
            select(UVDBAudit)
            .where(
                UVDBAudit.status == "completed",
                UVDBAudit.section_scores.isnot(None),
                *tenant_filter,
            )
            .order_by(UVDBAudit.audit_date.desc().nulls_last(), UVDBAudit.id.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()
    except (ProgrammingError, OperationalError):
        return _empty_section_scores()

    if not latest or not latest.section_scores:
        return _empty_section_scores()

    raw = latest.section_scores
    entries = raw.get("sections", []) if isinstance(raw, dict) else []
    if not isinstance(entries, list):
        entries = []

    links, links_resolved = await _resolve_import_links(db, [latest.audit_reference], tenant_id=tenant_id)
    _, import_job_id = links.get(latest.audit_reference, (None, None))
    score_source = resolve_provenance(import_job_id=import_job_id, provenance_resolved=links_resolved)

    valid_section_numbers = [str(section["number"]) for section in UVDB_B2_SECTIONS]
    title_index = build_section_title_index(UVDB_B2_SECTIONS)

    sections_map: dict[str, dict[str, Any]] = {}
    unmapped: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        normalised = normalise_section_score(
            entry,
            audit_reference=latest.audit_reference,
            score_source=score_source,
        )
        number = match_protocol_section(
            normalised["label"],
            valid_section_numbers=valid_section_numbers,
            title_index=title_index,
        )
        if number is None or number in sections_map:
            unmapped.append(normalised)
            continue
        sections_map[number] = normalised

    return {
        "sections": sections_map,
        "unmapped_sections": unmapped,
        "audit_reference": latest.audit_reference,
        "score_source": score_source,
    }


# ============ Dashboard ============


@router.get("/dashboard", response_model=dict)
async def get_uvdb_dashboard(
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get UVDB audit dashboard summary"""
    tenant_id = getattr(current_user, "tenant_id", None) if current_user else None
    tenant_filter = [UVDBAudit.tenant_id == tenant_id] if tenant_id is not None else []

    total_result = await db.execute(select(func.count()).select_from(UVDBAudit).where(*tenant_filter))
    total_audits = total_result.scalar()

    active_result = await db.execute(
        select(func.count())
        .select_from(UVDBAudit)
        .where(UVDBAudit.status.in_(["scheduled", "in_progress"]), *tenant_filter)
    )
    active_audits = active_result.scalar()

    completed_result = await db.execute(
        select(func.count()).select_from(UVDBAudit).where(UVDBAudit.status == "completed", *tenant_filter)
    )
    completed_audits = completed_result.scalar()

    score_filters = [
        UVDBAudit.status == "completed",
        UVDBAudit.percentage_score.isnot(None),
        *tenant_filter,
    ]
    avg_result = await db.execute(select(func.avg(UVDBAudit.percentage_score)).where(*score_filters))
    avg_score = avg_result.scalar()

    scored_result = await db.execute(select(func.count()).select_from(UVDBAudit).where(*score_filters))
    scored_audits = scored_result.scalar() or 0

    coverage = build_content_coverage()

    return {
        "summary": {
            "total_audits": total_audits,
            "active_audits": active_audits,
            "completed_audits": completed_audits,
            # None, not 0.0 — completed audits with no recorded score are not
            # an average of zero, and an empty population is not 100%.
            "average_score": round(float(avg_score), 1) if avg_score is not None else None,
            "scored_audits": scored_audits,
        },
        "protocol": {
            "name": "UVDB Verify B2",
            "version": PROTOCOL_VERSION,
            "sections": len(UVDB_B2_SECTIONS),
            "content_coverage": coverage,
        },
        "certification_alignment": {
            "iso_9001": "Quality Management - Section 1.1, 2.1-2.5, 12-13",
            "iso_14001": "Environmental Management - Section 1.3; Sections 8-11 pending v11.8 PDF",
            "iso_45001": "OH&S Management - Section 1.2; Sections 3-7 pending v11.8 PDF; Section 14",
            "iso_27001": "Information Security - Section 2.3",
        },
    }
