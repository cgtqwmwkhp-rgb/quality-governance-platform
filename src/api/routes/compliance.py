"""
ISO Compliance Evidence API Routes

Provides endpoints for:
- Auto-tagging content with ISO clauses
- Managing evidence links
- Generating compliance reports
- Gap analysis
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Annotated, Any, List, Optional

import sqlalchemy
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.compliance_evidence import (
    ComplianceEvidenceLink,
    EvidenceCoverKind,
    EvidenceLinkMethod,
    EvidenceLinkStatus,
)
from src.domain.models.ims_unification import IMSRequirement
from src.domain.models.standard import Clause, Standard
from src.domain.models.tenant import Tenant
from src.domain.models.user import User
from src.domain.services.compliance_evidence_link_writer import soft_delete_evidence_link, upsert_evidence_links
from src.domain.services.iso_compliance_service import EvidenceLink, ISOStandard, iso_compliance_service
from src.infrastructure.monitoring.azure_monitor import get_tracer

router = APIRouter()
logger = logging.getLogger(__name__)


async def _resolve_organization_name(
    db: DbSession,
    *,
    tenant_id: Optional[int],
    organization_name: Optional[str],
) -> Optional[str]:
    """Prefer an explicit query param; otherwise the tenant display name (PX-251)."""
    if organization_name and organization_name.strip() and organization_name.strip() != "Organisation":
        return organization_name.strip()
    if tenant_id is None:
        return None
    result = await db.execute(select(Tenant.name).where(Tenant.id == tenant_id))
    name = result.scalar_one_or_none()
    return name if name else None


_STANDARD_DB_MATCHERS: dict[ISOStandard, tuple[str, ...]] = {
    ISOStandard.ISO_9001: ("9001",),
    ISOStandard.ISO_14001: ("14001",),
    ISOStandard.ISO_45001: ("45001",),
    ISOStandard.ISO_27001: ("27001",),
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
    ISOStandard.ISO_27001: {
        "code": "ISO 27001:2022",
        "name": "Information Security Management System",
        "description": "Requirements for establishing, implementing, maintaining and continually improving an ISMS",
    },
}


# ============================================================================
# Request/Response Models
# ============================================================================


class AutoTagRequest(BaseModel):
    """Auto-tag content against compliance clauses.

    ``extra="forbid"`` so a misspelled or unsupported field fails loudly instead
    of tagging while the unknown key is silently dropped (B-10).
    """

    model_config = ConfigDict(extra="forbid")

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
    # D15: relationship shape. Default evidences keeps legacy create semantics.
    cover_kind: str = EvidenceCoverKind.EVIDENCES.value


class EvidenceLinkResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: str
    clause_id: str
    linked_by: str
    confidence: Optional[float]
    title: Optional[str]
    notes: Optional[str]
    document_version_id: Optional[int] = None
    standard_edition: Optional[str] = None
    cover_kind: str = EvidenceCoverKind.EVIDENCES.value
    created_at: str
    created_by_email: Optional[str]
    confirmed_by_id: Optional[int] = None
    confirmed_at: Optional[str] = None


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
    # ISO 27001: management clauses (4–10) vs Annex A — SoA uses Annex A only (PX-254).
    clause_count_breakdown: dict[str, int] = {}


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


def _confirmed_provenance(
    link: ComplianceEvidenceLink,
) -> tuple[Optional[datetime], Optional[str]]:
    """Resolve confirmed_at / confirmed_by for serializers.

    Prefer durable ``confirmed_by_id`` / ``confirmed_at`` (WI-1 / D15). Fall back
    to the pre-column heuristic only when those are still null so historical
    packs keep a best-effort actor without inventing one for AI auto-confirm.
    """
    link_status = link.effective_status if hasattr(link, "effective_status") else getattr(link, "status", None)
    status_value = None if link_status is None else getattr(link_status, "value", str(link_status))
    if status_value != EvidenceLinkStatus.CONFIRMED.value:
        return None, None

    durable_at = getattr(link, "confirmed_at", None)
    durable_by_id = getattr(link, "confirmed_by_id", None)
    if durable_at is not None or durable_by_id is not None:
        # Email is not stored on the confirmer FK; serializers that need an
        # address keep using created_by_email only when it matches the confirmer.
        confirmed_by = None
        if durable_by_id is not None and durable_by_id == getattr(link, "created_by_id", None):
            confirmed_by = link.created_by_email
        elif durable_by_id is not None:
            confirmed_by = f"user:{durable_by_id}"
        return durable_at, confirmed_by

    # Legacy heuristic (pre-WI-1 rows with no confirmer stamp).
    confirmed_at = link.updated_at or link.created_at
    if getattr(link, "auto_applied", False):
        # AI auto-confirm must not invent a human confirmer.
        return confirmed_at, None
    linked_by = link.linked_by.value if hasattr(link.linked_by, "value") else str(link.linked_by)
    if linked_by == EvidenceLinkMethod.MANUAL.value:
        return confirmed_at, link.created_by_email
    return confirmed_at, None


def _parse_cover_kind(raw: Optional[str]) -> EvidenceCoverKind:
    value = (raw or EvidenceCoverKind.EVIDENCES.value).strip().lower()
    try:
        return EvidenceCoverKind(value)
    except ValueError as exc:
        raise BadRequestError(
            f"Invalid cover_kind: {raw}. Expected one of: " f"{', '.join(m.value for m in EvidenceCoverKind)}"
        ) from exc


def _stamp_manual_confirmed(link: ComplianceEvidenceLink, user: User) -> None:
    """Human create/confirm that lands confirmed must set durable confirmer."""
    link.confirmed_by_id = getattr(user, "id", None)
    link.confirmed_at = datetime.now(timezone.utc)


def _build_evidence_link_model(link: ComplianceEvidenceLink) -> EvidenceLink:
    link_status = link.effective_status if hasattr(link, "effective_status") else getattr(link, "status", None)
    status_value = None if link_status is None else getattr(link_status, "value", str(link_status))
    confirmed_at, confirmed_by = _confirmed_provenance(link)
    return EvidenceLink(
        id=str(link.id),
        entity_type=link.entity_type,
        entity_id=link.entity_id,
        clause_id=link.clause_id,
        linked_by=link.linked_by.value if hasattr(link.linked_by, "value") else str(link.linked_by),
        confidence=link.confidence,
        created_at=link.created_at,
        created_by=link.created_by_email,
        title=link.title,
        notes=link.notes,
        signal_type=getattr(link, "signal_type", None),
        rationale=getattr(link, "rationale", None),
        scheme=getattr(link, "scheme", None),
        status=status_value,
        confirmed_at=confirmed_at,
        confirmed_by=confirmed_by,
        auto_applied=getattr(link, "auto_applied", None),
    )


def _serialize_link(link: ComplianceEvidenceLink) -> EvidenceLinkResponse:
    cover = getattr(link, "cover_kind", None)
    cover_value = cover.value if isinstance(cover, EvidenceCoverKind) else (cover or EvidenceCoverKind.EVIDENCES.value)
    confirmed_at = getattr(link, "confirmed_at", None)
    return EvidenceLinkResponse(
        id=link.id,
        entity_type=link.entity_type,
        entity_id=link.entity_id,
        clause_id=link.clause_id,
        linked_by=link.linked_by.value if hasattr(link.linked_by, "value") else str(link.linked_by),
        confidence=link.confidence,
        title=link.title,
        notes=link.notes,
        document_version_id=getattr(link, "document_version_id", None),
        standard_edition=getattr(link, "standard_edition", None),
        cover_kind=str(cover_value),
        created_at=((link.created_at or datetime.now(timezone.utc)).isoformat()),
        created_by_email=link.created_by_email,
        confirmed_by_id=getattr(link, "confirmed_by_id", None),
        confirmed_at=confirmed_at.isoformat() if confirmed_at is not None else None,
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
async def auto_tag_content(
    request: AutoTagRequest, current_user: Annotated[User, Depends(require_permission("audit:create"))]
):
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
async def link_evidence(
    request: EvidenceLinkRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
):
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

    cover_kind = _parse_cover_kind(request.cover_kind)

    # PR-C: this route no longer writes CEL rows itself. The sole writer owns D15
    # confirmer hygiene and ADR-0021 version pinning for every caller.
    result = await upsert_evidence_links(
        db,
        tenant_id=current_user.tenant_id,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        clause_ids=request.clause_ids,
        cover_kind=cover_kind,
        link_method=link_method,
        actor_id=current_user.id,
        actor_email=current_user.email,
        confidence=request.confidence,
        title=request.title,
        notes=request.notes,
    )

    return {
        "status": "success",
        "message": f"Upserted {result.total} evidence link(s)",
        "links": [item.model_dump() for item in [_serialize_link(link) for link in result.links]],
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
async def delete_evidence_link(
    link_id: int, db: DbSession, current_user: Annotated[User, Depends(require_permission("audit:update"))]
):
    """Soft-delete an evidence link for the current tenant."""
    link = await soft_delete_evidence_link(db, tenant_id=current_user.tenant_id, link_id=link_id)
    if link is None:
        raise NotFoundError("Evidence link not found")
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


@router.get("/audit-pack")
async def export_audit_pack(
    db: DbSession,
    current_user: CurrentUser,
    standard: Optional[str] = Query(None, description="Filter by ISO standard"),
    include_nonconformity: bool = Query(
        False,
        description=(
            "When false (default), nonconformity/gap/opportunity links are excluded from "
            "conformance evidence_links but still listed under operational_signals. "
            "When true, they are included in evidence_links with honest signal_label."
        ),
    ),
    include_soa: bool = Query(True, description="Include ISO 27001 SoA section"),
    organization_name: Optional[str] = Query(
        default=None,
        description="Organisation name for SoA (defaults to tenant name when omitted)",
    ),
):
    """
    Server-side ISO audit evidence pack with full CEL provenance.

    Exports attributable evidence links (created_at/by, rationale, confidence,
    signal_type, scheme/standard, clause_id, entity_type/id, status,
    confirmed_at/by when available). Operational nonconformity signals are
    excluded from conformance evidence by default and labelled honestly.
    """
    std_enum = _parse_standard_filter(standard)
    links = await _load_evidence_links(db, tenant_id=current_user.tenant_id, standard=std_enum)
    evidence_models = [_build_evidence_link_model(link) for link in links]
    resolved_org = await _resolve_organization_name(
        db, tenant_id=current_user.tenant_id, organization_name=organization_name
    )

    soa_payload: Optional[dict[str, Any]] = None
    if include_soa:
        soa_links = links
        if std_enum is not None and std_enum != ISOStandard.ISO_27001:
            soa_links = await _load_evidence_links(
                db,
                tenant_id=current_user.tenant_id,
                standard=ISOStandard.ISO_27001,
            )
        soa_payload = iso_compliance_service.generate_soa(
            [_build_evidence_link_model(link) for link in soa_links],
            organization_name=resolved_org,
            include_justification=True,
        )
        soa_payload["persisted_evidence_links"] = len(soa_links)

    pack = iso_compliance_service.build_audit_pack(
        evidence_models,
        standard=std_enum,
        include_nonconformity=include_nonconformity,
        include_soa=soa_payload,
        exported_by=getattr(current_user, "email", None),
        organization_name=resolved_org,
    )
    pack["persisted_evidence_links"] = len(links)

    date_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"iso-audit-pack-{date_stamp}.json"
    body = json.dumps(pack, indent=2, default=str).encode("utf-8")
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Audit-Pack-Version": str(pack.get("pack_version", "gkb-wl1-1.0")),
            "X-Audit-Pack-Nonconformity-Mode": pack["provenance_policy"]["nonconformity_mode"],
        },
    )


@router.post("/analyze")
async def analyze_evidence(
    request: AutoTagRequest,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
):
    """
    World-class 5-stage ISO evidence analysis powered by Genspark.ai.

    Runs a multi-stage pipeline:
      Stage 1 — Keyword pre-filter (fast, always runs)
      Stage 2 — Genspark LLM semantic mapping (requires GENSPARK_API_KEY)
      Stage 3 — Cross-standard mapping identification
      Stage 4 — Evidence quality scoring (Direct/Procedural/Documentary)
      Stage 5 — Auditor conformance statement generation

    Returns a structured evidence analysis package with conformance statements
    suitable for ISO certification audit packs.
    """
    tracer = get_tracer()
    if tracer is not None:
        with tracer.start_as_current_span("compliance.analyze_evidence") as span:
            span.set_attribute("content.length", len(request.content))
            result = await iso_compliance_service.multi_stage_analyze(request.content)
            span.set_attribute("result.stage_count", len(result.get("stages", {})))
            span.set_attribute("result.clause_count", len(result.get("clause_matches", [])))
    else:
        result = await iso_compliance_service.multi_stage_analyze(request.content)
    return result


@router.get("/soa")
async def get_statement_of_applicability(
    db: DbSession,
    current_user: CurrentUser,
    organization_name: Optional[str] = Query(
        default=None,
        description="Organisation name for SoA header (defaults to tenant name when omitted)",
    ),
    include_justification: bool = Query(default=True, description="Include implementation justification per control"),
):
    """
    Generate an evidence-derived Annex A SoA for ISO 27001:2022.

    **Distinct from** ``GET /api/v1/iso27001/soa`` which returns the persisted
    ISMS Statement of Applicability entity (a DB-backed record managed by the
    ISMS module with full lifecycle, versioning, and approval workflow).

    This endpoint dynamically derives control evidence coverage from the live
    evidence link database.  All 93 ISO 27001:2022 Annex A controls are assessed
    against persisted evidence items. Applicability decisions are not recorded
    in this path and are not invented.
    """
    links = await _load_evidence_links(
        db,
        tenant_id=current_user.tenant_id,
        standard=_parse_standard_filter("iso27001"),
    )
    resolved_org = await _resolve_organization_name(
        db, tenant_id=current_user.tenant_id, organization_name=organization_name
    )
    soa = iso_compliance_service.generate_soa(
        [_build_evidence_link_model(link) for link in links],
        organization_name=resolved_org,
        include_justification=include_justification,
    )
    soa["persisted_evidence_links"] = len(links)
    return soa


# =============================================================================
# Standards cell aggregate (Wave 1 PR-B) — live graph read-model
# =============================================================================


@router.get("/cell-aggregate")
async def get_standards_cell_aggregate(
    db: DbSession,
    current_user: CurrentUser,
    framework: str = Query(..., min_length=1, description="Matrix framework id (e.g. 9001, uvdb)"),
    clause: str = Query(..., min_length=1, description="Clause number (e.g. 4.1, 7.5)"),
):
    """Join findings, actions, risks, certs, evidence, and imported priors for one cell.

    Cover gate: open NC / open action → verdict cannot be ``covered``.
    Recurrence red-flag when an NC reappears after close on the same clause.
    Mock audits are labelled honestly and still paint gaps. LIVE-08: read-model only.

    Wave 2 PR-D: response includes ``exact_share`` preflight for EXACT peers.
    """
    from src.domain.services.standards_cell_aggregate_service import StandardsCellAggregateService
    from src.domain.services.standards_exact_share_service import ExactShareService

    tenant_id = current_user.tenant_id
    if tenant_id is None:
        raise BadRequestError("Tenant context required")
    service = StandardsCellAggregateService(db)
    result = await service.get_cell(
        tenant_id=tenant_id,
        framework=framework,
        clause_number=clause,
    )
    payload = result.to_dict()
    plan = await ExactShareService(db, aggregate=service).plan(
        tenant_id=tenant_id,
        framework=framework,
        clause_number=clause,
        source_cell=result,
    )
    payload["exact_share"] = plan.to_dict()
    return payload


@router.get("/cell-aggregate/matrix")
async def get_standards_cell_aggregate_matrix(
    db: DbSession,
    current_user: CurrentUser,
    frameworks: str = Query(..., description="Comma-separated matrix framework ids"),
    clauses: str = Query(..., description="Comma-separated clause numbers"),
):
    """Batch verdicts for Standards matrix paint (same cover gate as cell-aggregate).

    The cap exists to stop one request scanning the whole tenant, not to size the
    matrix: the imported 5064 axis is 32 rows across 12 columns, and the old 200
    ceiling rejected the **All** preset outright, so the shell fell back to a
    degraded grid on exactly the tenants that had done the import.
    """
    from src.domain.services.standards_cell_aggregate_service import (
        MATRIX_SUMMARY_MAX_CELLS,
        StandardsCellAggregateService,
    )

    tenant_id = current_user.tenant_id
    if tenant_id is None:
        raise BadRequestError("Tenant context required")
    fw_list = [part.strip() for part in frameworks.split(",") if part.strip()]
    clause_list = [part.strip() for part in clauses.split(",") if part.strip()]
    if not fw_list or not clause_list:
        raise BadRequestError("frameworks and clauses are required")
    if len(fw_list) * len(clause_list) > MATRIX_SUMMARY_MAX_CELLS:
        raise BadRequestError(f"Too many cells requested (max {MATRIX_SUMMARY_MAX_CELLS})")
    service = StandardsCellAggregateService(db)
    return await service.get_matrix_summary(
        tenant_id=tenant_id,
        frameworks=fw_list,
        clause_numbers=clause_list,
    )


class ExactShareApplyRequest(BaseModel):
    """Apply one source CEL row onto named EXACT peer frameworks."""

    model_config = ConfigDict(extra="forbid")

    source_link_id: int
    source_framework: str
    source_clause: str
    target_frameworks: list[str]
    matrix_version_id: int


class ExactShareUndoRequest(BaseModel):
    """Soft-delete links created by a prior EXACT share apply."""

    model_config = ConfigDict(extra="forbid")

    link_ids: list[int]
    applied_at: datetime


@router.post("/evidence/exact-share")
async def apply_exact_share(
    request: ExactShareApplyRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
):
    """Create-only share of one conformance evidence link onto EXACT peer cells."""
    from src.domain.services.standards_exact_share_service import ExactShareService

    tenant_id = current_user.tenant_id
    if tenant_id is None:
        raise BadRequestError("Tenant context required")
    return await ExactShareService(db).apply(
        tenant_id=tenant_id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        source_link_id=request.source_link_id,
        source_framework=request.source_framework,
        source_clause=request.source_clause,
        target_frameworks=request.target_frameworks,
        matrix_version_id=request.matrix_version_id,
    )


@router.post("/evidence/exact-share/undo")
async def undo_exact_share(
    request: ExactShareUndoRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
):
    """Undo a prior EXACT share by soft-deleting the created link ids."""
    from src.domain.services.standards_exact_share_service import ExactShareService

    tenant_id = current_user.tenant_id
    if tenant_id is None:
        raise BadRequestError("Tenant context required")
    return await ExactShareService(db).undo(
        tenant_id=tenant_id,
        link_ids=request.link_ids,
        applied_at=request.applied_at,
    )


# =============================================================================
# Standards alignment matrix (Wave 2 PR-C) — imported PEL-HSEQ-5064 verdicts
# =============================================================================


class AlignmentImportRequest(BaseModel):
    """Import request. Omitting ``payload`` uses the checked-in 5064 edition.

    ``extra="forbid"`` so an unrecognised field returns 422 instead of being
    silently dropped (PX-168).
    """

    model_config = ConfigDict(extra="forbid")

    payload: Optional[dict[str, Any]] = None
    accepted_tokens: Optional[list[str]] = None


@router.get("/alignment/catalogue")
async def get_alignment_catalogue(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:read"))],
    framework: Optional[str] = Query(None, description="Filter rows to one framework id"),
    verdict: Optional[str] = Query(None, description="Filter to EXACT|NEAR|DIFFERENT|UNIQUE"),
):
    """Alignment-aware clause rows for the Standards matrix axis.

    Replaces the hardcoded catalogue the matrix shell shipped with in PR-A. When no
    matrix edition has been imported this returns an empty ``rows`` list with
    ``matrix_loaded: false``, and the shell falls back to its static axis rather
    than rendering an empty grid.
    """
    from src.domain.services.standards_alignment_read_service import StandardsAlignmentReadService

    tenant_id = current_user.tenant_id
    if tenant_id is None:
        raise BadRequestError("Tenant context required")

    service = StandardsAlignmentReadService(db)
    return await service.catalogue(
        tenant_id=tenant_id,
        framework=framework,
        verdict=verdict,
    )


@router.post("/alignment/import/plan")
async def plan_alignment_import(
    request: AlignmentImportRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("standard:update"))],
):
    """Dry-run an alignment import: what would change, per clause pair.

    Writes nothing. Each item carries a ``token`` which is handed back to
    ``/alignment/import/apply`` to accept that specific change.
    """
    from src.domain.services.standards_alignment_import_service import (
        AlignmentImportError,
        StandardsAlignmentImportService,
        load_payload,
    )

    tenant_id = current_user.tenant_id
    if tenant_id is None:
        raise BadRequestError("Tenant context required")

    try:
        payload = request.payload or load_payload()
        service = StandardsAlignmentImportService(db)
        plan = await service.plan(tenant_id=tenant_id, payload=payload)
    except AlignmentImportError as exc:
        raise BadRequestError(str(exc)) from exc
    return plan.to_dict()


@router.post("/alignment/import/apply")
async def apply_alignment_import(
    request: AlignmentImportRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("standard:create"))],
):
    """Apply the accepted subset of an alignment import as a new active edition.

    ``accepted_tokens`` is the accept-each gate: a declined change keeps the
    verdict the active edition already holds, and a declined removal keeps the
    pair, so declining can never loosen a verdict. Applying the same payload with
    the same acceptances twice writes nothing the second time.
    """
    from src.domain.services.standards_alignment_import_service import (
        AlignmentImportError,
        StandardsAlignmentImportService,
        load_payload,
    )

    tenant_id = current_user.tenant_id
    if tenant_id is None:
        raise BadRequestError("Tenant context required")

    try:
        payload = request.payload or load_payload()
        service = StandardsAlignmentImportService(db)
        result = await service.apply(
            tenant_id=tenant_id,
            payload=payload,
            accepted_tokens=request.accepted_tokens,
            imported_by_id=current_user.id,
        )
        await db.commit()
    except AlignmentImportError as exc:
        raise BadRequestError(str(exc)) from exc
    return result.to_dict()


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
        level_2 = [c for c in iso_compliance_service.get_all_clauses(iso_standard) if c.level == 2]
        annex_a = [c for c in level_2 if c.clause_number.startswith("A.")]
        breakdown = (
            {
                "management_clauses": len(level_2) - len(annex_a),
                "annex_a_controls": len(annex_a),
            }
            if annex_a
            else {}
        )
        response.append(
            ComplianceStandardResponse(
                id=iso_standard.value,
                code=defaults["code"],
                name=defaults["name"],
                description=defaults["description"],
                clause_count=len(level_2),
                db_standard_id=canonical_row.id if canonical_row else None,
                db_standard_code=canonical_row.code if canonical_row else None,
                db_standard_name=canonical_row.name if canonical_row else None,
                db_clause_count=db_clause_counts.get(canonical_row.id, 0) if canonical_row else 0,
                ims_requirement_count=ims_counts.get(iso_standard, 0),
                covered_clauses=canonical_coverage.get("covered", 0) + canonical_coverage.get("partial_coverage", 0),
                coverage_percentage=canonical_coverage.get("percentage", 0),
                has_canonical_standard=canonical_row is not None,
                canonical_data_degraded=canonical_data_message is not None,
                canonical_data_message=canonical_data_message,
                clause_count_breakdown=breakdown,
            )
        )
    return response
