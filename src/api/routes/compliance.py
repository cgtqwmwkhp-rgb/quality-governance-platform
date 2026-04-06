"""
ISO Compliance Evidence API Routes

Provides endpoints for:
- Auto-tagging content with ISO clauses
- Managing evidence links
- Generating compliance reports
- Gap analysis
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, List, Optional

import sqlalchemy
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from src.api.dependencies import CurrentUser, DbSession
from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkMethod
from src.domain.models.ims_unification import IMSRequirement
from src.domain.models.standard import Clause, Standard
from src.domain.services.iso_compliance_service import EvidenceLink, ISOStandard, iso_compliance_service

router = APIRouter()
logger = logging.getLogger(__name__)

_STANDARD_DB_MATCHERS: dict[ISOStandard, tuple[str, ...]] = {
    ISOStandard.ISO_9001: ("9001",),
    ISOStandard.ISO_14001: ("14001",),
    ISOStandard.ISO_45001: ("45001",),
}

_STANDARD_DEFAULTS: dict[ISOStandard, dict[str, str]] = {
    ISOStandard.ISO_9001: {
        "code": "ISO 9001:2015",
        "name": "Quality Management System",
        "description": "Requirements for a quality management system",
    },
    ISOStandard.ISO_14001: {
        "code": "ISO 14001:2015",
        "name": "Environmental Management System",
        "description": "Requirements for an environmental management system",
    },
    ISOStandard.ISO_45001: {
        "code": "ISO 45001:2018",
        "name": "Occupational Health and Safety Management System",
        "description": "Requirements for an OH&S management system",
    },
}


# ============================================================================
# Request/Response Models
# ============================================================================


class AutoTagRequest(BaseModel):
    content: str
    min_confidence: float = 30.0
    use_ai: bool = False


class AutoTagResponse(BaseModel):
    clause_id: str
    clause_number: str
    title: str
    standard: str
    confidence: float
    linked_by: str


class ClauseResponse(BaseModel):
    id: str
    standard: str
    clause_number: str
    title: str
    description: str
    keywords: List[str]
    parent_clause: Optional[str]
    level: int


class EvidenceLinkRequest(BaseModel):
    entity_type: str  # 'document', 'audit', 'incident', 'policy', 'action', 'risk'
    entity_id: str
    clause_ids: List[str]
    linked_by: str = "manual"
    confidence: Optional[float] = None
    title: Optional[str] = None
    notes: Optional[str] = None


class EvidenceLinkResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: str
    clause_id: str
    linked_by: str
    confidence: Optional[float]
    title: Optional[str]
    notes: Optional[str]
    created_at: str
    created_by_email: Optional[str]


class ComplianceStandardResponse(BaseModel):
    id: str
    code: str
    name: str
    description: str
    clause_count: int
    db_standard_id: Optional[int] = None
    db_standard_code: Optional[str] = None
    db_standard_name: Optional[str] = None
    db_clause_count: int = 0
    ims_requirement_count: int = 0
    covered_clauses: int = 0
    coverage_percentage: float = 0
    has_canonical_standard: bool = False
    canonical_data_degraded: bool = False
    canonical_data_message: Optional[str] = None


class ComplianceSummary(BaseModel):
    total_clauses: int
    full_coverage: int
    partial_coverage: int
    gaps: int
    coverage_percentage: float


class GapClause(BaseModel):
    clause_id: str
    clause_number: str
    title: str
    standard: str


def _normalize_standard_record(*values: Optional[str]) -> str:
    return " ".join(value or "" for value in values).lower()


def _parse_standard_filter(standard: Optional[str]) -> Optional[ISOStandard]:
    if not standard:
        return None

    normalized = standard.strip().lower()
    try:
        return ISOStandard(normalized)
    except ValueError:
        for iso_standard, matchers in _STANDARD_DB_MATCHERS.items():
            if any(token in normalized for token in matchers):
                return iso_standard
        raise BadRequestError(f"Invalid standard: {standard}")


def _match_standard_record(record: Standard) -> Optional[ISOStandard]:
    normalized = _normalize_standard_record(record.code, record.name, record.full_name)
    for iso_standard, matchers in _STANDARD_DB_MATCHERS.items():
        if any(token in normalized for token in matchers):
            return iso_standard
    return None


def _match_ims_standard(value: Optional[str]) -> Optional[ISOStandard]:
    normalized = (value or "").lower()
    for iso_standard, matchers in _STANDARD_DB_MATCHERS.items():
        if any(token in normalized for token in matchers):
            return iso_standard
    return None


def _build_evidence_link_model(link: ComplianceEvidenceLink) -> EvidenceLink:
    return EvidenceLink(
        id=str(link.id),
        entity_type=link.entity_type,
        entity_id=link.entity_id,
        clause_id=link.clause_id,
        linked_by=link.linked_by.value if hasattr(link.linked_by, "value") else str(link.linked_by),
        confidence=link.confidence,
        created_at=link.created_at,
        created_by=link.created_by_email,
    )


def _serialize_link(link: ComplianceEvidenceLink) -> EvidenceLinkResponse:
    return EvidenceLinkResponse(
        id=link.id,
        entity_type=link.entity_type,
        entity_id=link.entity_id,
        clause_id=link.clause_id,
        linked_by=link.linked_by.value if hasattr(link.linked_by, "value") else str(link.linked_by),
        confidence=link.confidence,
        title=link.title,
        notes=link.notes,
        created_at=((link.created_at or datetime.now(timezone.utc)).isoformat()),
        created_by_email=link.created_by_email,
    )


async def _load_evidence_links(
    db: DbSession,
    *,
    tenant_id: Optional[int],
    standard: Optional[ISOStandard] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    clause_id: Optional[str] = None,
) -> list[ComplianceEvidenceLink]:
    query = select(ComplianceEvidenceLink).where(ComplianceEvidenceLink.deleted_at.is_(None))

    if tenant_id is None:
        query = query.where(sqlalchemy.false())
    else:
        query = query.where(ComplianceEvidenceLink.tenant_id == tenant_id)

    if standard is not None:
        clause_ids = {clause.id for clause in iso_compliance_service.get_all_clauses(standard) if clause.level == 2}
        query = query.where(ComplianceEvidenceLink.clause_id.in_(clause_ids))

    if entity_type:
        query = query.where(ComplianceEvidenceLink.entity_type == entity_type)
    if entity_id:
        query = query.where(ComplianceEvidenceLink.entity_id == entity_id)
    if clause_id:
        query = query.where(ComplianceEvidenceLink.clause_id == clause_id)

    query = query.order_by(ComplianceEvidenceLink.created_at.desc(), ComplianceEvidenceLink.id.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def _load_canonical_standard_rows(
    db: DbSession,
    *,
    tenant_id: Optional[int],
) -> tuple[dict[ISOStandard, Standard], dict[int, int], dict[ISOStandard, int], Optional[str]]:
    try:
        std_tenant_filter = (
            or_(Standard.tenant_id == tenant_id, Standard.tenant_id.is_(None))
            if tenant_id is not None
            else Standard.tenant_id.is_(None)
        )
        standard_result = await db.execute(select(Standard).where(Standard.is_active == True, std_tenant_filter))
        canonical_rows: dict[ISOStandard, Standard] = {}
        for record in standard_result.scalars().all():
            matched_standard = _match_standard_record(record)
            if matched_standard and matched_standard not in canonical_rows:
                canonical_rows[matched_standard] = record

        clause_count_rows = await db.execute(
            select(Clause.standard_id, func.count(Clause.id))
            .select_from(Clause)
            .join(Standard, Clause.standard_id == Standard.id)
            .where(
                Clause.is_active == True,  # noqa: E712
                Standard.is_active == True,  # noqa: E712
                std_tenant_filter,
            )
            .group_by(Clause.standard_id)
        )
        db_clause_counts = {standard_id: count for standard_id, count in clause_count_rows.all()}

        ims_tenant_filter = (
            or_(IMSRequirement.tenant_id == tenant_id, IMSRequirement.tenant_id.is_(None))
            if tenant_id is not None
            else IMSRequirement.tenant_id.is_(None)
        )
        ims_requirement_rows = await db.execute(
            select(IMSRequirement.standard, func.count(IMSRequirement.id))
            .where(ims_tenant_filter)
            .group_by(IMSRequirement.standard)
        )
        ims_counts: dict[ISOStandard, int] = defaultdict(int)
        for standard_name, count in ims_requirement_rows.all():
            matched_standard = _match_ims_standard(standard_name)
            if matched_standard:
                ims_counts[matched_standard] += count

        return canonical_rows, db_clause_counts, dict(ims_counts), None
    except SQLAlchemyError as exc:
        logger.exception("Compliance standards canonical enrichment unavailable; falling back to static ISO defaults")
        return (
            {},
            {},
            {},
            f"Canonical compliance enrichment is temporarily unavailable ({type(exc).__name__}). "
            "Static ISO defaults and persisted evidence coverage are still available.",
        )


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/clauses", response_model=List[ClauseResponse])
async def list_clauses(
    current_user: CurrentUser,
    standard: Optional[str] = Query(None, description="Filter by ISO standard (iso9001, iso14001, iso45001)"),
    level: Optional[int] = Query(None, description="Filter by clause level (1=main, 2=sub)"),
    search: Optional[str] = Query(None, description="Search by keyword or clause number"),
):
    """List all ISO clauses with optional filtering."""

    std_enum = _parse_standard_filter(standard)

    if search:
        clauses = iso_compliance_service.search_clauses(search)
    else:
        clauses = iso_compliance_service.get_all_clauses(std_enum)

    if level:
        clauses = [c for c in clauses if c.level == level]

    return [
        ClauseResponse(
            id=c.id,
            standard=c.standard.value,
            clause_number=c.clause_number,
            title=c.title,
            description=c.description,
            keywords=c.keywords,
            parent_clause=c.parent_clause,
            level=c.level,
        )
        for c in clauses
    ]


@router.get("/clauses/{clause_id}", response_model=ClauseResponse)
async def get_clause(clause_id: str, current_user: CurrentUser):
    """Get a specific ISO clause by ID."""
    clause = iso_compliance_service.get_clause(clause_id)
    if not clause:
        raise NotFoundError(f"Clause not found: {clause_id}")

    return ClauseResponse(
        id=clause.id,
        standard=clause.standard.value,
        clause_number=clause.clause_number,
        title=clause.title,
        description=clause.description,
        keywords=clause.keywords,
        parent_clause=clause.parent_clause,
        level=clause.level,
    )


@router.post("/auto-tag", response_model=List[AutoTagResponse])
async def auto_tag_content(request: AutoTagRequest, current_user: CurrentUser):
    """
    Automatically detect ISO clauses that relate to the given content.

    Uses keyword matching and pattern recognition. Optionally can use AI
    for enhanced tagging when use_ai=True.
    """
    min_conf = request.min_confidence / 100.0  # Convert percentage to decimal

    if request.use_ai:
        # AI-enhanced tagging (async)
        results = await iso_compliance_service.ai_enhanced_tagging(request.content)
    else:
        # Keyword-based tagging (sync)
        results = iso_compliance_service.auto_tag_content(request.content, min_conf)

    return [AutoTagResponse(**result) for result in results]


@router.post("/evidence/link")
async def link_evidence(request: EvidenceLinkRequest, db: DbSession, current_user: CurrentUser):
    """
    Link an entity (document, audit, incident, etc.) to ISO clauses.

    This creates the evidence mapping that shows which items satisfy
    which ISO requirements.
    """
    # Validate clause IDs exist
    for clause_id in request.clause_ids:
        if not iso_compliance_service.get_clause(clause_id):
            raise BadRequestError(f"Invalid clause ID: {clause_id}")

    try:
        link_method = EvidenceLinkMethod(request.linked_by.lower())
    except ValueError as exc:
        raise BadRequestError(f"Invalid linked_by value: {request.linked_by}") from exc

    existing_result = await db.execute(
        select(ComplianceEvidenceLink).where(
            ComplianceEvidenceLink.deleted_at.is_(None),
            ComplianceEvidenceLink.tenant_id == current_user.tenant_id,
            ComplianceEvidenceLink.entity_type == request.entity_type,
            ComplianceEvidenceLink.entity_id == request.entity_id,
            ComplianceEvidenceLink.clause_id.in_(request.clause_ids),
        )
    )
    existing_by_clause = {link.clause_id: link for link in existing_result.scalars().all()}

    links_created: list[ComplianceEvidenceLink] = []
    for clause_id in request.clause_ids:
        link = existing_by_clause.get(clause_id)
        if link is None:
            link = ComplianceEvidenceLink(
                tenant_id=current_user.tenant_id,
                entity_type=request.entity_type,
                entity_id=request.entity_id,
                clause_id=clause_id,
                created_by_id=current_user.id,
                created_by_email=current_user.email,
            )
            db.add(link)

        link.linked_by = link_method
        link.confidence = request.confidence
        link.title = request.title
        link.notes = request.notes
        links_created.append(link)

    await db.commit()
    for link in links_created:
        await db.refresh(link)

    return {
        "status": "success",
        "message": f"Upserted {len(links_created)} evidence link(s)",
        "links": [item.model_dump() for item in [_serialize_link(link) for link in links_created]],
    }


@router.get("/evidence/links", response_model=list[EvidenceLinkResponse])
async def list_evidence_links(
    db: DbSession,
    current_user: CurrentUser,
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    clause_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=500),
):
    """List persisted evidence links for the current tenant."""
    links = await _load_evidence_links(
        db,
        tenant_id=current_user.tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        clause_id=clause_id,
    )
    start = (page - 1) * size
    return [_serialize_link(link) for link in links[start : start + size]]


@router.delete("/evidence/link/{link_id}")
async def delete_evidence_link(link_id: int, db: DbSession, current_user: CurrentUser):
    """Soft-delete an evidence link for the current tenant."""
    result = await db.execute(
        select(ComplianceEvidenceLink).where(
            ComplianceEvidenceLink.id == link_id,
            ComplianceEvidenceLink.deleted_at.is_(None),
            ComplianceEvidenceLink.tenant_id == current_user.tenant_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise NotFoundError("Evidence link not found")

    link.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "deleted"}


@router.get("/coverage")
async def get_compliance_coverage(
    db: DbSession,
    current_user: CurrentUser,
    standard: Optional[str] = Query(None, description="Filter by ISO standard"),
):
    """
    Get compliance coverage statistics showing how many clauses
    have evidence linked to them.
    """
    std_enum = _parse_standard_filter(standard)
    links = await _load_evidence_links(db, tenant_id=current_user.tenant_id, standard=std_enum)
    evidence_links = [_build_evidence_link_model(link) for link in links]
    return iso_compliance_service.calculate_compliance_coverage(evidence_links, std_enum)


@router.get("/gaps")
async def get_compliance_gaps(
    db: DbSession,
    current_user: CurrentUser,
    standard: Optional[str] = Query(None, description="Filter by ISO standard"),
):
    """
    Get list of ISO clauses that have no evidence linked to them.
    These represent compliance gaps that need attention.
    """
    std_enum = _parse_standard_filter(standard)
    links = await _load_evidence_links(db, tenant_id=current_user.tenant_id, standard=std_enum)
    coverage = iso_compliance_service.calculate_compliance_coverage(
        [_build_evidence_link_model(link) for link in links],
        std_enum,
    )

    return {"total_gaps": coverage["gaps"], "gap_clauses": coverage["gap_clauses"]}


@router.get("/report")
async def generate_compliance_report(
    db: DbSession,
    current_user: CurrentUser,
    standard: Optional[str] = Query(None, description="Filter by ISO standard"),
    include_evidence: bool = Query(True, description="Include evidence details in report"),
):
    """
    Generate a comprehensive compliance report suitable for certification audits.

    Shows all clauses with their linked evidence and coverage status.
    """
    std_enum = _parse_standard_filter(standard)
    links = await _load_evidence_links(db, tenant_id=current_user.tenant_id, standard=std_enum)
    report = iso_compliance_service.generate_audit_report(
        [_build_evidence_link_model(link) for link in links],
        std_enum,
        include_evidence,
    )
    report["persisted_evidence_links"] = len(links)
    return report


@router.get("/standards", response_model=list[ComplianceStandardResponse])
async def list_standards(db: DbSession, current_user: CurrentUser):
    """List supported standards and bridge them to canonical DB-backed records."""
    links = await _load_evidence_links(db, tenant_id=current_user.tenant_id)
    coverage_by_standard = iso_compliance_service.calculate_compliance_coverage(
        [_build_evidence_link_model(link) for link in links],
        None,
    )["by_standard"]
    canonical_rows, db_clause_counts, ims_counts, canonical_data_message = await _load_canonical_standard_rows(
        db,
        tenant_id=current_user.tenant_id,
    )

    response: list[ComplianceStandardResponse] = []
    for iso_standard in ISOStandard:
        defaults = _STANDARD_DEFAULTS[iso_standard]
        canonical_row = canonical_rows.get(iso_standard)
        canonical_coverage = coverage_by_standard.get(iso_standard.value, {})
        response.append(
            ComplianceStandardResponse(
                id=iso_standard.value,
                code=defaults["code"],
                name=defaults["name"],
                description=defaults["description"],
                clause_count=len([c for c in iso_compliance_service.get_all_clauses(iso_standard) if c.level == 2]),
                db_standard_id=canonical_row.id if canonical_row else None,
                db_standard_code=canonical_row.code if canonical_row else None,
                db_standard_name=canonical_row.name if canonical_row else None,
                db_clause_count=db_clause_counts.get(canonical_row.id, 0) if canonical_row else 0,
                ims_requirement_count=ims_counts.get(iso_standard, 0),
                covered_clauses=canonical_coverage.get("covered", 0),
                coverage_percentage=canonical_coverage.get("percentage", 0),
                has_canonical_standard=canonical_row is not None,
                canonical_data_degraded=canonical_data_message is not None,
                canonical_data_message=canonical_data_message,
            )
        )
    return response
