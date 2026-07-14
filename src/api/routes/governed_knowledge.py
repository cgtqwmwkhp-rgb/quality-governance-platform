"""Governed Knowledge Bank API routes — AI-first evidence mapping, quizzes, discussions."""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.utils.tenant import require_tenant_id
from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkStatus, EvidenceSignalType
from src.domain.models.document import Document
from src.domain.models.governed_knowledge import (
    AiDecisionLog,
    DiscussionThreadStatus,
    DocumentDiscussionMessage,
    DocumentDiscussionThread,
    DocumentQuizDraft,
    QuizDraftStatus,
    RegulatoryImpactStatus,
    RegulatoryWatchImpact,
)
from src.domain.models.user import User
from src.domain.services.governed_knowledge_service import governed_knowledge_service

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# SCHEMAS
# =============================================================================


class EvidenceLinkDetailResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: str
    clause_id: str
    linked_by: str
    confidence: Optional[float]
    status: str
    scheme: Optional[str]
    auto_applied: bool
    rationale: Optional[str]
    title: Optional[str]
    notes: Optional[str]
    signal_type: Optional[str] = None
    created_at: str
    created_by_email: Optional[str]


class MapEvidenceResponse(BaseModel):
    document_id: int
    links_created: int
    links: list[EvidenceLinkDetailResponse]


class RejectEvidenceRequest(BaseModel):
    rationale: str = Field(..., min_length=3, description="Required reject reason for auditability")


class BulkConfirmRequest(BaseModel):
    link_ids: list[int] = Field(..., min_length=1)


class GenerateQuizRequest(BaseModel):
    question_count: int = Field(5, ge=1, le=30)
    include_open: bool = True
    include_mcq: bool = True
    pass_mark: int = Field(70, ge=0, le=100)
    auto_approve_if_quality: bool = False


class QuizDraftResponse(BaseModel):
    id: int
    document_id: int
    version: str
    questions: list
    pass_mark: int
    status: str
    created_at: str


class DiscussionThreadCreate(BaseModel):
    title: Optional[str] = None
    version: str = "1.0"


class DiscussionThreadResponse(BaseModel):
    id: int
    document_id: int
    version: str
    status: str
    title: Optional[str]
    created_by_id: int
    created_at: str


class DiscussionMessageCreate(BaseModel):
    body: str
    use_ai_draft: bool = False


class DiscussionMessageResponse(BaseModel):
    id: int
    thread_id: int
    author_id: int
    body: str
    is_ai_draft: bool
    created_at: str


class ScanKbRequest(BaseModel):
    clause_texts: Optional[list[str]] = None


class AssessEntityRequest(BaseModel):
    content: Optional[str] = Field(
        None,
        description="Optional override text; when omitted the live entity record is loaded",
    )
    finding_type: Optional[str] = None
    include_related_documents: bool = True


class RelatedDocumentResponse(BaseModel):
    document_id: int
    score: float
    title: Optional[str] = None


class AssessEntityResponse(BaseModel):
    entity_type: str
    entity_id: str
    signal_type: str
    links_created: int
    links: list[EvidenceLinkDetailResponse]
    related_documents: list[RelatedDocumentResponse]
    assessment_statement: Optional[str] = None
    stages_summary: Optional[dict[str, Any]] = None


class RegulatoryImpactResponse(BaseModel):
    id: int
    update_id: str
    document_id: Optional[int]
    confidence: Optional[float]
    rationale: Optional[str]
    status: str
    created_at: str
    action_id: Optional[int] = None
    action_key: Optional[str] = None
    action_reference: Optional[str] = None
    owner_id: Optional[int] = None
    due_date: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by_id: Optional[int] = None
    resolution_notes: Optional[str] = None


class CreateWatchActionRequest(BaseModel):
    owner_email: Optional[str] = None
    owner_id: Optional[int] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None


class ResolveWatchImpactRequest(BaseModel):
    notes: Optional[str] = None
    dismiss: bool = False
    close_action: bool = True


class WatchActionResponse(BaseModel):
    impact_id: int
    status: str
    action: Optional[dict[str, Any]] = None
    due_date: Optional[str] = None
    owner_id: Optional[int] = None


# =============================================================================
# HELPERS
# =============================================================================


def _tenant_id_for(user: CurrentUser) -> int:
    return require_tenant_id(getattr(user, "tenant_id", None))


def _serialize_evidence_link(link: ComplianceEvidenceLink) -> EvidenceLinkDetailResponse:
    return EvidenceLinkDetailResponse(
        id=link.id,
        entity_type=link.entity_type,
        entity_id=link.entity_id,
        clause_id=link.clause_id,
        linked_by=link.linked_by.value if hasattr(link.linked_by, "value") else str(link.linked_by),
        confidence=link.confidence,
        status=link.effective_status.value,
        scheme=link.scheme,
        auto_applied=link.auto_applied,
        rationale=link.rationale,
        title=link.title,
        notes=link.notes,
        signal_type=link.signal_type,
        created_at=((link.created_at or datetime.now(timezone.utc)).isoformat()),
        created_by_email=link.created_by_email,
    )


async def _get_document_or_404(db: DbSession, document_id: int, tenant_id: int) -> Document:
    result = await db.execute(select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id))
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document not found")
    return document


async def _get_evidence_link_or_404(db: DbSession, link_id: int, tenant_id: int) -> ComplianceEvidenceLink:
    result = await db.execute(
        select(ComplianceEvidenceLink).where(
            ComplianceEvidenceLink.id == link_id,
            ComplianceEvidenceLink.tenant_id == tenant_id,
            ComplianceEvidenceLink.deleted_at.is_(None),
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise NotFoundError("Evidence link not found")
    return link


async def _document_text(db: DbSession, document: Document) -> str:
    if document.ai_summary:
        parts = [document.ai_summary]
    else:
        parts = [document.title, document.description or ""]
    from src.domain.models.document import DocumentChunk

    chunk_result = await db.execute(
        select(DocumentChunk.content)
        .where(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
        .limit(20)
    )
    chunks = [row[0] for row in chunk_result.all() if row[0]]
    if chunks:
        parts.append("\n".join(chunks))
    return "\n\n".join(p for p in parts if p)


async def _load_operational_entity_text(
    db: DbSession,
    *,
    entity_type: str,
    entity_id: str,
    tenant_id: int,
) -> tuple[str, Optional[str]]:
    """Return (content, finding_type) for supported operational entities."""
    from src.domain.services.governed_knowledge_service import OPERATIONAL_ENTITY_TYPES

    if entity_type not in OPERATIONAL_ENTITY_TYPES:
        raise BadRequestError(f"Unsupported entity_type: {entity_type}")

    try:
        eid = int(entity_id)
    except ValueError as exc:
        raise BadRequestError("entity_id must be numeric") from exc

    if entity_type == "incident":
        from src.domain.models.incident import Incident

        incident = (
            await db.execute(select(Incident).where(Incident.id == eid, Incident.tenant_id == tenant_id))
        ).scalar_one_or_none()
        if not incident:
            raise NotFoundError("Incident not found")
        return f"{incident.title}\n\n{incident.description}", None

    if entity_type == "complaint":
        from src.domain.models.complaint import Complaint

        complaint = (
            await db.execute(select(Complaint).where(Complaint.id == eid, Complaint.tenant_id == tenant_id))
        ).scalar_one_or_none()
        if not complaint:
            raise NotFoundError("Complaint not found")
        return f"{complaint.title}\n\n{complaint.description}", None

    if entity_type == "rta":
        from src.domain.models.rta import RTA

        rta = (await db.execute(select(RTA).where(RTA.id == eid, RTA.tenant_id == tenant_id))).scalar_one_or_none()
        if not rta:
            raise NotFoundError("RTA not found")
        return f"{rta.title}\n\n{rta.description}", None

    if entity_type == "near_miss":
        from src.domain.models.near_miss import NearMiss

        near_miss = (
            await db.execute(select(NearMiss).where(NearMiss.id == eid, NearMiss.tenant_id == tenant_id))
        ).scalar_one_or_none()
        if not near_miss:
            raise NotFoundError("Near miss not found")
        parts = [
            near_miss.description,
            near_miss.potential_consequences or "",
            near_miss.preventive_action_suggested or "",
            f"Location: {near_miss.location}" if near_miss.location else "",
        ]
        return "\n\n".join(p for p in parts if p), None

    if entity_type == "audit_finding":
        from src.domain.models.audit import AuditFinding

        finding = (
            await db.execute(select(AuditFinding).where(AuditFinding.id == eid, AuditFinding.tenant_id == tenant_id))
        ).scalar_one_or_none()
        if not finding:
            raise NotFoundError("Audit finding not found")
        return f"{finding.title}\n\n{finding.description}", getattr(finding, "finding_type", None)
    raise BadRequestError(f"Unsupported entity_type: {entity_type}")


# =============================================================================
# EVIDENCE MAPPING
# =============================================================================


@router.post("/documents/{document_id}/map-evidence", response_model=MapEvidenceResponse)
async def map_document_evidence(
    document_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """Trigger multi-scheme AI-first evidence mapping for a document."""
    tenant_id = _tenant_id_for(current_user)
    document = await _get_document_or_404(db, document_id, tenant_id)
    content = await _document_text(db, document)
    doc_type = document.document_type.value if hasattr(document.document_type, "value") else str(document.document_type)

    links = await governed_knowledge_service.map_document_to_schemes(
        db,
        document_id,
        content,
        doc_type,
        tenant_id,
        current_user,
    )
    await db.commit()
    for link in links:
        await db.refresh(link)

    return MapEvidenceResponse(
        document_id=document_id,
        links_created=len(links),
        links=[_serialize_evidence_link(link) for link in links],
    )


@router.get("/documents/{document_id}/evidence", response_model=list[EvidenceLinkDetailResponse])
async def list_document_evidence(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """List evidence links for a document."""
    tenant_id = _tenant_id_for(current_user)
    await _get_document_or_404(db, document_id, tenant_id)

    result = await db.execute(
        select(ComplianceEvidenceLink)
        .where(
            ComplianceEvidenceLink.tenant_id == tenant_id,
            ComplianceEvidenceLink.entity_type == "document",
            ComplianceEvidenceLink.entity_id == str(document_id),
            ComplianceEvidenceLink.deleted_at.is_(None),
        )
        .order_by(ComplianceEvidenceLink.created_at.desc())
    )
    links = list(result.scalars().all())
    return [_serialize_evidence_link(link) for link in links]


@router.post("/evidence/{link_id}/confirm")
async def confirm_evidence_link(
    link_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
):
    """Manually confirm a proposed evidence link."""
    tenant_id = _tenant_id_for(current_user)
    link = await _get_evidence_link_or_404(db, link_id, tenant_id)
    prior = link.effective_status.value
    link.status = EvidenceLinkStatus.CONFIRMED
    link.auto_applied = False
    db.add(
        AiDecisionLog(
            tenant_id=tenant_id,
            action="evidence_confirm",
            entity_type=link.entity_type,
            entity_id=str(link.entity_id),
            confidence=link.confidence,
            auto_applied=False,
            payload={
                "link_id": link_id,
                "clause_id": link.clause_id,
                "prior_status": prior,
                "actor_email": getattr(current_user, "email", None),
                "actor_id": getattr(current_user, "id", None),
            },
        )
    )
    await db.commit()
    return {"status": "confirmed", "link_id": link_id}


@router.post("/evidence/{link_id}/reject")
async def reject_evidence_link(
    link_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
    body: Annotated[Optional[RejectEvidenceRequest], Body()] = None,
):
    """Reject a proposed evidence link. Prefer a rationale body for auditability."""
    tenant_id = _tenant_id_for(current_user)
    link = await _get_evidence_link_or_404(db, link_id, tenant_id)
    prior = link.effective_status.value
    link.status = EvidenceLinkStatus.REJECTED
    link.auto_applied = False
    rationale = body.rationale.strip() if body and body.rationale else ""
    if rationale:
        reject_note = f"Rejected: {rationale}"
        link.notes = f"{link.notes}\n{reject_note}".strip() if link.notes else reject_note
    else:
        # Honest marker for legacy callers (e.g. DocumentDetail) that omit body.
        legacy = "Rejected without rationale (legacy client)"
        link.notes = f"{link.notes}\n{legacy}".strip() if link.notes else legacy
        rationale = legacy
    db.add(
        AiDecisionLog(
            tenant_id=tenant_id,
            action="evidence_reject",
            entity_type=link.entity_type,
            entity_id=str(link.entity_id),
            confidence=link.confidence,
            auto_applied=False,
            payload={
                "link_id": link_id,
                "clause_id": link.clause_id,
                "prior_status": prior,
                "rationale": rationale,
                "actor_email": getattr(current_user, "email", None),
                "actor_id": getattr(current_user, "id", None),
            },
        )
    )
    await db.commit()
    return {"status": "rejected", "link_id": link_id, "rationale": rationale}


@router.post("/evidence/bulk-confirm")
async def bulk_confirm_evidence(
    request: BulkConfirmRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
):
    """Bulk-confirm multiple proposed evidence links."""
    tenant_id = _tenant_id_for(current_user)
    result = await db.execute(
        select(ComplianceEvidenceLink).where(
            ComplianceEvidenceLink.id.in_(request.link_ids),
            ComplianceEvidenceLink.tenant_id == tenant_id,
            ComplianceEvidenceLink.deleted_at.is_(None),
        )
    )
    links = list(result.scalars().all())
    for link in links:
        link.status = EvidenceLinkStatus.CONFIRMED
        link.auto_applied = False
    await db.commit()
    return {"status": "confirmed", "count": len(links)}


@router.get("/exceptions", response_model=list[EvidenceLinkDetailResponse])
async def list_exception_inbox(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Optional[str] = Query(None, alias="status"),
    entity_type: Optional[str] = Query(None, description="Filter by source entity_type"),
    clause_id: Optional[str] = Query(None, description="Filter by ISO clause_id (e.g. 7.5)"),
    scheme: Optional[str] = Query(None, description="Filter by standard/scheme code"),
    signal_type: Optional[str] = Query(None, description="Filter by EvidenceSignalType value"),
    operational_only: bool = Query(
        False,
        description="When true, only operational signals (nonconformity|gap|opportunity)",
    ),
):
    """Proposed + needs_review evidence inbox."""
    tenant_id = _tenant_id_for(current_user)
    statuses = [EvidenceLinkStatus.PROPOSED, EvidenceLinkStatus.NEEDS_REVIEW]
    if status_filter:
        try:
            statuses = [EvidenceLinkStatus(status_filter.lower())]
        except ValueError as exc:
            raise BadRequestError(f"Invalid status: {status_filter}") from exc

    filters = [
        ComplianceEvidenceLink.tenant_id == tenant_id,
        ComplianceEvidenceLink.deleted_at.is_(None),
        or_(
            ComplianceEvidenceLink.status.in_(statuses),
            ComplianceEvidenceLink.status.is_(None),
        ),
    ]
    if entity_type:
        filters.append(ComplianceEvidenceLink.entity_type == entity_type)
    if clause_id:
        filters.append(ComplianceEvidenceLink.clause_id == clause_id.strip())
    if scheme:
        filters.append(ComplianceEvidenceLink.scheme == scheme.strip())
    if signal_type:
        normalized = signal_type.strip().lower()
        try:
            EvidenceSignalType(normalized)
        except ValueError as exc:
            raise BadRequestError(f"Invalid signal_type: {signal_type}") from exc
        filters.append(ComplianceEvidenceLink.signal_type == normalized)

    result = await db.execute(
        select(ComplianceEvidenceLink).where(*filters).order_by(ComplianceEvidenceLink.created_at.desc()).limit(200)
    )
    links = [link for link in result.scalars().all() if link.effective_status in statuses]
    if operational_only:
        from src.domain.services.iso_compliance_service import OPERATIONAL_SIGNAL_TYPES

        links = [
            link for link in links if (getattr(link, "signal_type", None) or "").lower() in OPERATIONAL_SIGNAL_TYPES
        ]
    return [_serialize_evidence_link(link) for link in links]


@router.get("/exceptions/operational-counts")
async def operational_exception_counts_by_clause(
    db: DbSession,
    current_user: CurrentUser,
    scheme: Optional[str] = Query(None, description="Optional standard/scheme filter"),
):
    """Count inbound operational signals per clause for Standards/IMS map."""
    from src.domain.services.iso_compliance_service import OPERATIONAL_SIGNAL_TYPES

    tenant_id = _tenant_id_for(current_user)
    statuses = [EvidenceLinkStatus.PROPOSED, EvidenceLinkStatus.NEEDS_REVIEW]
    filters = [
        ComplianceEvidenceLink.tenant_id == tenant_id,
        ComplianceEvidenceLink.deleted_at.is_(None),
        or_(
            ComplianceEvidenceLink.status.in_(statuses),
            ComplianceEvidenceLink.status.is_(None),
        ),
    ]
    if scheme:
        filters.append(ComplianceEvidenceLink.scheme == scheme.strip())

    result = await db.execute(select(ComplianceEvidenceLink).where(*filters).limit(2000))
    counts: dict[str, int] = {}
    total = 0
    for link in result.scalars().all():
        if link.effective_status not in statuses:
            continue
        sig = (getattr(link, "signal_type", None) or "").lower()
        if sig not in OPERATIONAL_SIGNAL_TYPES:
            continue
        clause = link.clause_id or ""
        if not clause:
            continue
        counts[clause] = counts.get(clause, 0) + 1
        total += 1
    return {"scheme": scheme, "total": total, "by_clause": counts}


@router.post(
    "/entities/{entity_type}/{entity_id}/assess",
    response_model=AssessEntityResponse,
)
async def assess_operational_entity(
    entity_type: str,
    entity_id: str,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
    body: AssessEntityRequest = AssessEntityRequest(content=None),
):
    """Run Operational Standards Assessor for a case entity."""
    tenant_id = _tenant_id_for(current_user)
    finding_type = body.finding_type
    if body.content and body.content.strip():
        content = body.content
    else:
        content, loaded_finding_type = await _load_operational_entity_text(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )
        finding_type = finding_type or loaded_finding_type

    try:
        result = await governed_knowledge_service.assess_operational_entity(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            content=content,
            tenant_id=tenant_id,
            user=current_user,
            finding_type=finding_type,
            include_related_documents=body.include_related_documents,
        )
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc
    await db.commit()
    return AssessEntityResponse(
        entity_type=result.entity_type,
        entity_id=result.entity_id,
        signal_type=result.signal_type,
        links_created=len(result.links),
        links=[_serialize_evidence_link(link) for link in result.links],
        related_documents=[
            RelatedDocumentResponse(
                document_id=hit.document_id,
                score=hit.score,
                title=hit.title,
            )
            for hit in result.related_documents
        ],
        assessment_statement=result.assessment_statement,
        stages_summary=result.stages_summary,
    )


@router.get(
    "/entities/{entity_type}/{entity_id}/assessment",
    response_model=list[EvidenceLinkDetailResponse],
)
async def get_operational_entity_assessment(
    entity_type: str,
    entity_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """List persisted standards assessment links for a case entity.

    Always returns a list (possibly empty). Missing links are not a 404 —
    the Standards tab treats empty as "not assessed yet".
    """
    tenant_id = _tenant_id_for(current_user)
    from src.domain.services.governed_knowledge_service import OPERATIONAL_ENTITY_TYPES

    if entity_type not in OPERATIONAL_ENTITY_TYPES:
        raise BadRequestError(f"Unsupported entity_type: {entity_type}")

    try:
        links = await governed_knowledge_service.list_entity_assessment_links(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )
    except Exception:
        logger.exception(
            "Failed listing standards assessment for %s/%s — returning empty",
            entity_type,
            entity_id,
        )
        return []
    return [_serialize_evidence_link(link) for link in links]


@router.get("/entities/{entity_type}/{entity_id}/assessment-trail")
async def get_operational_entity_assessment_trail(
    entity_type: str,
    entity_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Audit trail for standards assess / confirm / reject on a case entity."""
    tenant_id = _tenant_id_for(current_user)
    from src.domain.services.governed_knowledge_service import OPERATIONAL_ENTITY_TYPES

    if entity_type not in OPERATIONAL_ENTITY_TYPES:
        raise BadRequestError(f"Unsupported entity_type: {entity_type}")

    trail_actions = (
        "operational_standards_assess",
        "evidence_confirm",
        "evidence_reject",
    )
    result = await db.execute(
        select(AiDecisionLog)
        .where(
            AiDecisionLog.tenant_id == tenant_id,
            AiDecisionLog.entity_type == entity_type,
            AiDecisionLog.entity_id == str(entity_id),
            AiDecisionLog.action.in_(trail_actions),
        )
        .order_by(AiDecisionLog.created_at.desc())
        .limit(100)
    )
    rows = list(result.scalars().all())
    return {
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "items": [
            {
                "id": row.id,
                "action": row.action,
                "confidence": row.confidence,
                "auto_applied": row.auto_applied,
                "payload": row.payload,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }


@router.post("/standards/{standard_id}/scan-kb")
async def scan_standard_kb(
    standard_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
    body: ScanKbRequest = ScanKbRequest(),
):
    """Reverse-scan knowledge bank for documents matching a standard."""
    tenant_id = _tenant_id_for(current_user)
    links = await governed_knowledge_service.scan_standard_against_kb(
        db,
        standard_id=standard_id,
        clause_texts=body.clause_texts,
        tenant_id=tenant_id,
        user=current_user,
    )
    await db.commit()
    return {
        "standard_id": standard_id,
        "links_created": len(links),
        "links": [_serialize_evidence_link(link) for link in links],
    }


# =============================================================================
# QUIZ
# =============================================================================


@router.post("/documents/{document_id}/generate-quiz", response_model=QuizDraftResponse)
async def generate_document_quiz(
    document_id: int,
    request: GenerateQuizRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """Generate an AI quiz draft from document content."""
    tenant_id = _tenant_id_for(current_user)
    document = await _get_document_or_404(db, document_id, tenant_id)
    content = await _document_text(db, document)

    draft = await governed_knowledge_service.generate_quiz_draft(
        db,
        document_id=document_id,
        content=content,
        version=document.version or "1.0",
        tenant_id=tenant_id,
        user=current_user,
        question_count=request.question_count,
        include_open=request.include_open,
        include_mcq=request.include_mcq,
        pass_mark=request.pass_mark,
        auto_approve_if_quality=request.auto_approve_if_quality,
    )
    await db.commit()
    await db.refresh(draft)

    return QuizDraftResponse(
        id=draft.id,
        document_id=draft.document_id,
        version=draft.version,
        questions=draft.questions,
        pass_mark=draft.pass_mark,
        status=draft.status.value,
        created_at=draft.created_at.isoformat(),
    )


@router.post("/documents/{document_id}/approve-quiz")
async def approve_document_quiz(
    document_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    draft_id: Optional[int] = Query(None),
):
    """Approve the latest or specified quiz draft."""
    tenant_id = _tenant_id_for(current_user)
    await _get_document_or_404(db, document_id, tenant_id)

    query = select(DocumentQuizDraft).where(
        DocumentQuizDraft.document_id == document_id,
        DocumentQuizDraft.tenant_id == tenant_id,
    )
    if draft_id:
        query = query.where(DocumentQuizDraft.id == draft_id)
    else:
        query = query.order_by(DocumentQuizDraft.created_at.desc())

    result = await db.execute(query.limit(1))
    draft = result.scalar_one_or_none()
    if not draft:
        raise NotFoundError("Quiz draft not found")

    draft.status = QuizDraftStatus.APPROVED
    await db.commit()
    return {"status": "approved", "draft_id": draft.id}


# =============================================================================
# DISCUSSIONS
# =============================================================================


@router.get("/documents/{document_id}/discussions", response_model=list[DiscussionThreadResponse])
async def list_discussions(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    tenant_id = _tenant_id_for(current_user)
    await _get_document_or_404(db, document_id, tenant_id)

    result = await db.execute(
        select(DocumentDiscussionThread)
        .where(
            DocumentDiscussionThread.document_id == document_id,
            DocumentDiscussionThread.tenant_id == tenant_id,
        )
        .order_by(DocumentDiscussionThread.created_at.desc())
    )
    threads = result.scalars().all()
    return [
        DiscussionThreadResponse(
            id=t.id,
            document_id=t.document_id,
            version=t.version,
            status=t.status.value,
            title=t.title,
            created_by_id=t.created_by_id,
            created_at=t.created_at.isoformat(),
        )
        for t in threads
    ]


@router.post(
    "/documents/{document_id}/discussions",
    response_model=DiscussionThreadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_discussion(
    document_id: int,
    body: DiscussionThreadCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    tenant_id = _tenant_id_for(current_user)
    document = await _get_document_or_404(db, document_id, tenant_id)

    thread = DocumentDiscussionThread(
        tenant_id=tenant_id,
        document_id=document_id,
        version=body.version or document.version or "1.0",
        title=body.title,
        created_by_id=current_user.id,
    )
    db.add(thread)
    await db.commit()
    await db.refresh(thread)

    return DiscussionThreadResponse(
        id=thread.id,
        document_id=thread.document_id,
        version=thread.version,
        status=thread.status.value,
        title=thread.title,
        created_by_id=thread.created_by_id,
        created_at=thread.created_at.isoformat(),
    )


@router.post(
    "/discussions/{thread_id}/messages",
    response_model=DiscussionMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_discussion_message(
    thread_id: int,
    body: DiscussionMessageCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    tenant_id = _tenant_id_for(current_user)
    thread_result = await db.execute(
        select(DocumentDiscussionThread).where(
            DocumentDiscussionThread.id == thread_id,
            DocumentDiscussionThread.tenant_id == tenant_id,
        )
    )
    thread = thread_result.scalar_one_or_none()
    if not thread:
        raise NotFoundError("Discussion thread not found")

    message_body = body.body
    is_ai_draft = False
    if body.use_ai_draft:
        prior_result = await db.execute(
            select(DocumentDiscussionMessage.body)
            .where(DocumentDiscussionMessage.thread_id == thread_id)
            .order_by(DocumentDiscussionMessage.created_at.desc())
            .limit(5)
        )
        context = "\n".join(row[0] for row in prior_result.all())
        message_body = await governed_knowledge_service.draft_discussion_reply(context, body.body)
        is_ai_draft = True

    message = DocumentDiscussionMessage(
        tenant_id=tenant_id,
        thread_id=thread_id,
        author_id=current_user.id,
        body=message_body,
        is_ai_draft=is_ai_draft,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    return DiscussionMessageResponse(
        id=message.id,
        thread_id=message.thread_id,
        author_id=message.author_id,
        body=message.body,
        is_ai_draft=message.is_ai_draft,
        created_at=message.created_at.isoformat(),
    )


# =============================================================================
# REGULATORY WATCH
# =============================================================================


@router.post("/regulatory-watch/run")
async def run_regulatory_watch(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
):
    """Trigger one UK curated-feed regulatory-watch poll + KB impact match."""
    from src.domain.services.regulatory_watch_service import regulatory_watch_service

    tenant_id = _tenant_id_for(current_user)
    result = await regulatory_watch_service.run_poll_cycle(
        db,
        tenant_id=tenant_id,
        triggered_by=current_user.id,
    )
    return result


@router.get("/regulatory-watch/impacts", response_model=list[RegulatoryImpactResponse])
async def list_regulatory_impacts(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Optional[str] = Query(None, alias="status"),
):
    from src.domain.models.capa import CAPAAction

    tenant_id = _tenant_id_for(current_user)
    query = select(RegulatoryWatchImpact).where(RegulatoryWatchImpact.tenant_id == tenant_id)
    if status_filter:
        try:
            query = query.where(RegulatoryWatchImpact.status == RegulatoryImpactStatus(status_filter.lower()))
        except ValueError as exc:
            raise BadRequestError(f"Invalid status: {status_filter}") from exc

    result = await db.execute(query.order_by(RegulatoryWatchImpact.created_at.desc()).limit(100))
    impacts = list(result.scalars().all())

    action_refs: dict[int, str] = {}
    action_ids = [i.action_id for i in impacts if i.action_id]
    if action_ids:
        capa_result = await db.execute(
            select(CAPAAction.id, CAPAAction.reference_number).where(CAPAAction.id.in_(action_ids))
        )
        action_refs = {row[0]: row[1] for row in capa_result.all()}

    return [
        RegulatoryImpactResponse(
            id=impact.id,
            update_id=impact.update_id,
            document_id=impact.document_id,
            confidence=impact.confidence,
            rationale=impact.rationale,
            status=impact.status.value,
            created_at=impact.created_at.isoformat(),
            action_id=impact.action_id,
            action_key=f"capa:{impact.action_id}" if impact.action_id else None,
            action_reference=action_refs.get(impact.action_id) if impact.action_id else None,
            owner_id=impact.owner_id,
            due_date=impact.due_date.isoformat() if impact.due_date else None,
            resolved_at=impact.resolved_at.isoformat() if impact.resolved_at else None,
            resolved_by_id=impact.resolved_by_id,
            resolution_notes=impact.resolution_notes,
        )
        for impact in impacts
    ]


@router.post(
    "/regulatory-watch/impacts/{impact_id}/create-action",
    response_model=WatchActionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_action_from_watch_impact(
    impact_id: int,
    body: CreateWatchActionRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("capa:create"))],
):
    """Create a real Action (CAPA) from a regulatory watch impact — owner + due."""
    from src.domain.services.regulatory_watch_actions import regulatory_watch_actions_service

    tenant_id = _tenant_id_for(current_user)
    result = await db.execute(
        select(RegulatoryWatchImpact).where(
            RegulatoryWatchImpact.id == impact_id,
            RegulatoryWatchImpact.tenant_id == tenant_id,
        )
    )
    impact = result.scalar_one_or_none()
    if impact is None:
        raise NotFoundError("Regulatory impact not found")

    try:
        capa = await regulatory_watch_actions_service.create_action_for_impact(
            db,
            impact=impact,
            created_by_id=current_user.id,
            tenant_id=tenant_id,
            owner_id=body.owner_id,
            owner_email=body.owner_email,
            due_date=body.due_date,
            priority=body.priority,
            auto_applied=False,
            commit=True,
        )
    except LookupError as exc:
        raise NotFoundError(str(exc)) from exc
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc

    return WatchActionResponse(
        impact_id=impact.id,
        status=impact.status.value,
        action=regulatory_watch_actions_service.serialize_action(capa),
        due_date=impact.due_date.isoformat() if impact.due_date else None,
        owner_id=impact.owner_id,
    )


@router.post(
    "/regulatory-watch/impacts/{impact_id}/resolve",
    response_model=WatchActionResponse,
)
async def resolve_watch_impact(
    impact_id: int,
    body: ResolveWatchImpactRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("capa:update"))],
):
    """Resolve or dismiss a watch impact; closes linked Action by default."""
    from src.domain.services.regulatory_watch_actions import regulatory_watch_actions_service

    tenant_id = _tenant_id_for(current_user)
    result = await db.execute(
        select(RegulatoryWatchImpact).where(
            RegulatoryWatchImpact.id == impact_id,
            RegulatoryWatchImpact.tenant_id == tenant_id,
        )
    )
    impact = result.scalar_one_or_none()
    if impact is None:
        raise NotFoundError("Regulatory impact not found")

    try:
        impact = await regulatory_watch_actions_service.resolve_impact(
            db,
            impact=impact,
            resolved_by_id=current_user.id,
            tenant_id=tenant_id,
            notes=body.notes,
            dismiss=body.dismiss,
            close_action=body.close_action,
        )
    except LookupError as exc:
        raise NotFoundError(str(exc)) from exc
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc

    action_payload = None
    if impact.action_id:
        from src.domain.models.capa import CAPAAction

        capa = await db.get(CAPAAction, impact.action_id)
        if capa is not None:
            action_payload = regulatory_watch_actions_service.serialize_action(capa)

    return WatchActionResponse(
        impact_id=impact.id,
        status=impact.status.value,
        action=action_payload,
        due_date=impact.due_date.isoformat() if impact.due_date else None,
        owner_id=impact.owner_id,
    )
