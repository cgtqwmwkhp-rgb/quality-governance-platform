"""Governed Knowledge Bank API routes — AI-first evidence mapping, quizzes, discussions."""

import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.utils.tenant import require_tenant_id
from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkStatus
from src.domain.models.document import Document
from src.domain.models.governed_knowledge import (
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

        row = (
            await db.execute(select(Incident).where(Incident.id == eid, Incident.tenant_id == tenant_id))
        ).scalar_one_or_none()
        if not row:
            raise NotFoundError("Incident not found")
        return f"{row.title}\n\n{row.description}", None

    if entity_type == "complaint":
        from src.domain.models.complaint import Complaint

        row = (
            await db.execute(select(Complaint).where(Complaint.id == eid, Complaint.tenant_id == tenant_id))
        ).scalar_one_or_none()
        if not row:
            raise NotFoundError("Complaint not found")
        return f"{row.title}\n\n{row.description}", None

    if entity_type == "rta":
        from src.domain.models.rta import RTA

        row = (await db.execute(select(RTA).where(RTA.id == eid, RTA.tenant_id == tenant_id))).scalar_one_or_none()
        if not row:
            raise NotFoundError("RTA not found")
        return f"{row.title}\n\n{row.description}", None

    if entity_type == "near_miss":
        from src.domain.models.near_miss import NearMiss

        row = (
            await db.execute(select(NearMiss).where(NearMiss.id == eid, NearMiss.tenant_id == tenant_id))
        ).scalar_one_or_none()
        if not row:
            raise NotFoundError("Near miss not found")
        parts = [
            row.description,
            row.potential_consequences or "",
            row.preventive_action_suggested or "",
            f"Location: {row.location}" if row.location else "",
        ]
        return "\n\n".join(p for p in parts if p), None

    if entity_type == "audit_finding":
        from src.domain.models.audit import AuditFinding

        row = (
            await db.execute(select(AuditFinding).where(AuditFinding.id == eid, AuditFinding.tenant_id == tenant_id))
        ).scalar_one_or_none()
        if not row:
            raise NotFoundError("Audit finding not found")
        return f"{row.title}\n\n{row.description}", getattr(row, "finding_type", None)

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
    link.status = EvidenceLinkStatus.CONFIRMED
    link.auto_applied = False
    await db.commit()
    return {"status": "confirmed", "link_id": link_id}


@router.post("/evidence/{link_id}/reject")
async def reject_evidence_link(
    link_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
):
    """Reject a proposed evidence link."""
    tenant_id = _tenant_id_for(current_user)
    link = await _get_evidence_link_or_404(db, link_id, tenant_id)
    link.status = EvidenceLinkStatus.REJECTED
    link.auto_applied = False
    await db.commit()
    return {"status": "rejected", "link_id": link_id}


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

    result = await db.execute(
        select(ComplianceEvidenceLink).where(*filters).order_by(ComplianceEvidenceLink.created_at.desc()).limit(200)
    )
    links = [link for link in result.scalars().all() if link.effective_status in statuses]
    return [_serialize_evidence_link(link) for link in links]


@router.post(
    "/entities/{entity_type}/{entity_id}/assess",
    response_model=AssessEntityResponse,
)
async def assess_operational_entity(
    entity_type: str,
    entity_id: str,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
    body: AssessEntityRequest = AssessEntityRequest(),
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
    """List persisted standards assessment links for a case entity."""
    tenant_id = _tenant_id_for(current_user)
    from src.domain.services.governed_knowledge_service import OPERATIONAL_ENTITY_TYPES

    if entity_type not in OPERATIONAL_ENTITY_TYPES:
        raise BadRequestError(f"Unsupported entity_type: {entity_type}")

    links = await governed_knowledge_service.list_entity_assessment_links(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        tenant_id=tenant_id,
    )
    return [_serialize_evidence_link(link) for link in links]


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
    tenant_id = _tenant_id_for(current_user)
    query = select(RegulatoryWatchImpact).where(RegulatoryWatchImpact.tenant_id == tenant_id)
    if status_filter:
        try:
            query = query.where(RegulatoryWatchImpact.status == RegulatoryImpactStatus(status_filter.lower()))
        except ValueError as exc:
            raise BadRequestError(f"Invalid status: {status_filter}") from exc

    result = await db.execute(query.order_by(RegulatoryWatchImpact.created_at.desc()).limit(100))
    impacts = result.scalars().all()
    return [
        RegulatoryImpactResponse(
            id=impact.id,
            update_id=impact.update_id,
            document_id=impact.document_id,
            confidence=impact.confidence,
            rationale=impact.rationale,
            status=impact.status.value,
            created_at=impact.created_at.isoformat(),
        )
        for impact in impacts
    ]
