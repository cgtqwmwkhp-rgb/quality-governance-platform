"""
ISO Compliance Evidence API Routes

Provides endpoints for:
- Auto-tagging content with ISO clauses
- Managing evidence links (persistent)
- Generating compliance reports from real data
- Gap analysis from real data
"""

from datetime import datetime, timezone
from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession, require_permission
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.pagination import DataListResponse
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkMethod
from src.domain.models.user import User
from src.domain.services.iso_compliance_service import EvidenceLink, ISOStandard, iso_compliance_service
from src.infrastructure.monitoring.azure_monitor import track_metric

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter()


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
    entity_type: str
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

    class Config:
        from_attributes = True


class EvidenceLinkDeleteRequest(BaseModel):
    link_ids: List[int]


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


class EvidenceLinkCreateItem(BaseModel):
    id: int
    entity_type: str
    entity_id: str
    clause_id: str
    linked_by: str
    confidence: Optional[float] = None
    created_at: str


class EvidenceLinkCreateResponse(BaseModel):
    status: str
    message: str
    links: List[EvidenceLinkCreateItem]


class EvidenceLinkListResponse(BaseModel):
    items: List[EvidenceLinkResponse]
    total: int
    page: int
    page_size: int
    pages: int


class EvidenceLinkDeleteResponse(BaseModel):
    status: str
    message: str


class ComplianceCoverageResponse(BaseModel):
    model_config = {"extra": "allow"}

    total_clauses: int = 0
    coverage_percentage: float = 0.0
    gaps: int = 0


class ComplianceReportResponse(BaseModel):
    model_config = {"extra": "allow"}


class ComplianceGapsResponse(BaseModel):
    total_gaps: int
    gap_clauses: List[Any]


class StandardInfo(BaseModel):
    id: str
    code: str
    name: str
    description: str
    clause_count: int


# ============================================================================
# Helper: load real evidence links from DB
# ============================================================================


async def _load_evidence_links(
    db, tenant_id: int | None = None, standard: Optional[ISOStandard] = None
) -> list[EvidenceLink]:
    """Query all active evidence links from the database and convert to
    the EvidenceLink dataclass used by the ISOComplianceService."""
    query = select(ComplianceEvidenceLink).where(
        ComplianceEvidenceLink.deleted_at.is_(None),
        ComplianceEvidenceLink.tenant_id == tenant_id,
    )
    result = await db.execute(query)
    rows = result.scalars().all()

    links: list[EvidenceLink] = []
    for row in rows:
        if standard:
            clause = iso_compliance_service.get_clause(row.clause_id)
            if clause and clause.standard != standard:
                continue
        links.append(
            EvidenceLink(
                id=str(row.id),
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                clause_id=row.clause_id,
                linked_by=row.linked_by.value if isinstance(row.linked_by, EvidenceLinkMethod) else row.linked_by,
                confidence=row.confidence,
                created_at=row.created_at,
                created_by=row.created_by_email,
            )
        )
    return links


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/clauses", response_model=DataListResponse)
async def list_clauses(
    standard: Optional[str] = Query(None, description="Filter by ISO standard (iso9001, iso14001, iso45001)"),
    level: Optional[int] = Query(None, description="Filter by clause level (1=main, 2=sub)"),
    search: Optional[str] = Query(None, description="Search by keyword or clause number"),
):
    """List all ISO clauses with optional filtering."""
    std_enum = None
    if standard:
        try:
            std_enum = ISOStandard(standard)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.VALIDATION_ERROR)

    if search:
        clauses = iso_compliance_service.search_clauses(search)
    else:
        clauses = iso_compliance_service.get_all_clauses(std_enum)

    if level:
        clauses = [c for c in clauses if c.level == level]

    return {
        "data": [
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
    }


@router.get("/clauses/{clause_id}", response_model=ClauseResponse)
async def get_clause(clause_id: str):
    """Get a specific ISO clause by ID."""
    clause = iso_compliance_service.get_clause(clause_id)
    if not clause:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)
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
async def auto_tag_content(request: AutoTagRequest):
    """Automatically detect ISO clauses that relate to the given content."""
    track_metric("compliance.check")
    min_conf = request.min_confidence / 100.0
    if request.use_ai:
        results = await iso_compliance_service.ai_enhanced_tagging(request.content)
    else:
        results = iso_compliance_service.auto_tag_content(request.content, min_conf)
    return [AutoTagResponse(**result) for result in results]


@router.post("/evidence/link", response_model=EvidenceLinkCreateResponse)
async def link_evidence(
    request: EvidenceLinkRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance:create"))],
):
    """Link an entity to one or more ISO clauses. Persisted to database."""
    _span = tracer.start_span("link_evidence") if tracer else None
    for clause_id in request.clause_ids:
        if not iso_compliance_service.get_clause(clause_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.VALIDATION_ERROR)

    method = EvidenceLinkMethod.MANUAL
    if request.linked_by == "auto":
        method = EvidenceLinkMethod.AUTO
    elif request.linked_by == "ai":
        method = EvidenceLinkMethod.AI

    created: list[dict] = []
    for clause_id in request.clause_ids:
        existing = await db.execute(
            select(ComplianceEvidenceLink).where(
                ComplianceEvidenceLink.tenant_id == current_user.tenant_id,
                ComplianceEvidenceLink.entity_type == request.entity_type,
                ComplianceEvidenceLink.entity_id == request.entity_id,
                ComplianceEvidenceLink.clause_id == clause_id,
                ComplianceEvidenceLink.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            continue

        link = ComplianceEvidenceLink(
            tenant_id=current_user.tenant_id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            clause_id=clause_id,
            linked_by=method,
            confidence=request.confidence,
            title=request.title,
            notes=request.notes,
            created_by_id=current_user.id,
            created_by_email=current_user.email,
        )
        db.add(link)
        await db.flush()

        created.append(
            {
                "id": link.id,
                "entity_type": link.entity_type,
                "entity_id": link.entity_id,
                "clause_id": link.clause_id,
                "linked_by": method.value,
                "confidence": link.confidence,
                "created_at": (
                    link.created_at.isoformat() if link.created_at else datetime.now(timezone.utc).isoformat()
                ),
            }
        )

    track_metric("compliance.score_checked", 1)
    if _span:
        _span.end()
    return {
        "status": "success",
        "message": f"Created {len(created)} evidence link(s)",
        "links": created,
    }


@router.get("/evidence/links", response_model=EvidenceLinkListResponse)
async def list_evidence_links(
    db: DbSession,
    current_user: CurrentUser,
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    clause_id: Optional[str] = Query(None),
    params: PaginationParams = Depends(),
):
    """List evidence links with optional filtering."""
    query = select(ComplianceEvidenceLink).where(
        ComplianceEvidenceLink.deleted_at.is_(None),
        ComplianceEvidenceLink.tenant_id == current_user.tenant_id,
    )
    if entity_type:
        query = query.where(ComplianceEvidenceLink.entity_type == entity_type)
    if entity_id:
        query = query.where(ComplianceEvidenceLink.entity_id == entity_id)
    if clause_id:
        query = query.where(ComplianceEvidenceLink.clause_id == clause_id)

    query = query.order_by(ComplianceEvidenceLink.created_at.desc())

    paginated = await paginate(db, query, params)

    return {
        "items": [
            EvidenceLinkResponse(
                id=r.id,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                clause_id=r.clause_id,
                linked_by=r.linked_by.value if isinstance(r.linked_by, EvidenceLinkMethod) else r.linked_by,
                confidence=r.confidence,
                title=r.title,
                notes=r.notes,
                created_at=r.created_at.isoformat() if r.created_at else "",
                created_by_email=r.created_by_email,
            )
            for r in paginated.items
        ],
        "total": paginated.total,
        "page": paginated.page,
        "page_size": paginated.page_size,
        "pages": paginated.pages,
    }


@router.delete("/evidence/link/{link_id}", response_model=EvidenceLinkDeleteResponse)
async def delete_evidence_link(
    link_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
):
    """Soft-delete an evidence link."""
    link = await get_or_404(db, ComplianceEvidenceLink, link_id, tenant_id=current_user.tenant_id)
    link.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return {"status": "success", "message": "Evidence link deleted"}


@router.get("/coverage", response_model=ComplianceCoverageResponse)
async def get_compliance_coverage(
    db: DbSession,
    current_user: CurrentUser,
    standard: Optional[str] = Query(None, description="Filter by ISO standard"),
):
    """Get compliance coverage statistics from real evidence links."""
    std_enum = None
    if standard:
        try:
            std_enum = ISOStandard(standard)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.VALIDATION_ERROR)

    links = await _load_evidence_links(db, current_user.tenant_id, std_enum)
    return iso_compliance_service.calculate_compliance_coverage(links, std_enum)


@router.get("/gaps", response_model=ComplianceGapsResponse)
async def get_compliance_gaps(
    db: DbSession,
    current_user: CurrentUser,
    standard: Optional[str] = Query(None, description="Filter by ISO standard"),
):
    """Get list of ISO clauses with no evidence linked."""
    std_enum = None
    if standard:
        try:
            std_enum = ISOStandard(standard)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.VALIDATION_ERROR)

    links = await _load_evidence_links(db, current_user.tenant_id, std_enum)
    coverage = iso_compliance_service.calculate_compliance_coverage(links, std_enum)
    return {"total_gaps": coverage["gaps"], "gap_clauses": coverage["gap_clauses"]}


@router.get("/report", response_model=ComplianceReportResponse)
async def generate_compliance_report(
    db: DbSession,
    current_user: CurrentUser,
    standard: Optional[str] = Query(None, description="Filter by ISO standard"),
    include_evidence: bool = Query(True, description="Include evidence details"),
):
    """Generate a comprehensive compliance report from real data."""
    std_enum = None
    if standard:
        try:
            std_enum = ISOStandard(standard)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.VALIDATION_ERROR)

    links = await _load_evidence_links(db, current_user.tenant_id, std_enum)
    return iso_compliance_service.generate_audit_report(links, std_enum, include_evidence)


@router.get("/standards", response_model=DataListResponse)
async def list_standards():
    """List all supported ISO standards."""
    return {
        "data": [
            {
                "id": "iso9001",
                "code": "ISO 9001:2015",
                "name": "Quality Management System",
                "description": "Requirements for a quality management system",
                "clause_count": len(
                    [c for c in iso_compliance_service.get_all_clauses(ISOStandard.ISO_9001) if c.level == 2]
                ),
            },
            {
                "id": "iso14001",
                "code": "ISO 14001:2015",
                "name": "Environmental Management System",
                "description": "Requirements for an environmental management system",
                "clause_count": len(
                    [c for c in iso_compliance_service.get_all_clauses(ISOStandard.ISO_14001) if c.level == 2]
                ),
            },
            {
                "id": "iso45001",
                "code": "ISO 45001:2018",
                "name": "Occupational Health and Safety Management System",
                "description": "Requirements for an OH&S management system",
                "clause_count": len(
                    [c for c in iso_compliance_service.get_all_clauses(ISOStandard.ISO_45001) if c.level == 2]
                ),
            },
        ]
    }
