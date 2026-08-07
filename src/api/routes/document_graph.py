"""Doc Graph API routes (ADR-0021 Wave 0 + Wave 1 heuristic propose).

Gated by ``settings.document_graph_enabled``. When closed, every route returns 404.
Heuristic propose additionally requires ``document_graph_heuristic_propose_enabled``.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status

from src.api.dependencies import DbSession, require_permission
from src.api.schemas.document_graph import (
    CitationStalenessResponse,
    ClauseDocumentsResponse,
    DocumentEdgeCreate,
    DocumentEdgeListResponse,
    DocumentEdgeRejectRequest,
    DocumentEdgeResponse,
    DocumentThreadResponse,
    HeuristicProposeResponse,
    ImSeedDocumentItem,
    ImSeedEdgeItem,
    ImSeedResponse,
)
from src.api.utils.tenant import require_tenant_id
from src.core.config import settings
from src.domain.models.document_graph import DocumentEdgeStatus, DocumentEdgeType
from src.domain.models.user import User
from src.domain.services.document_graph_heuristic_propose import DocumentGraphHeuristicProposeService
from src.domain.services.document_graph_im_seed import DocumentGraphImSeedService
from src.domain.services.document_graph_iso_reverse import DocumentGraphIsoReverseService
from src.domain.services.document_graph_service import DocumentGraphService

DISABLED_DETAIL = "Doc Graph is not enabled in this environment."
HEURISTIC_DISABLED_DETAIL = "Doc Graph heuristic propose is not enabled in this environment."

router = APIRouter()


async def require_document_graph_enabled() -> None:
    from fastapi import HTTPException

    if not settings.document_graph_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=DISABLED_DETAIL)


async def require_document_graph_heuristic_propose_enabled() -> None:
    from fastapi import HTTPException

    if not settings.document_graph_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=DISABLED_DETAIL)
    if not settings.document_graph_heuristic_propose_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=HEURISTIC_DISABLED_DETAIL)


_enabled_router = APIRouter(dependencies=[Depends(require_document_graph_enabled)])
_heuristic_router = APIRouter(dependencies=[Depends(require_document_graph_heuristic_propose_enabled)])


@_enabled_router.get(
    "/documents/{document_id}/edges",
    response_model=DocumentEdgeListResponse,
)
async def list_document_edges(
    document_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:read"))],
    edge_type: Optional[DocumentEdgeType] = Query(None),
    status_filter: Optional[DocumentEdgeStatus] = Query(None, alias="status"),
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = DocumentGraphService(db)
    items = await service.list_edges(
        tenant_id=tenant_id,
        document_id=document_id,
        edge_type=edge_type,
        status=status_filter,
    )
    return DocumentEdgeListResponse(
        items=[DocumentEdgeResponse.model_validate(i) for i in items],
        total=len(items),
    )


@_enabled_router.get(
    "/documents/{document_id}/thread",
    response_model=DocumentThreadResponse,
)
async def get_document_thread(
    document_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:read"))],
    include_proposed: bool = Query(
        False,
        description="When true, include PROPOSED/NEEDS_REVIEW primary edges. Default ambient thread is confirmed-only.",
    ),
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = DocumentGraphService(db)
    payload = await service.get_thread(
        tenant_id=tenant_id,
        document_id=document_id,
        include_proposed=include_proposed,
    )
    return DocumentThreadResponse.model_validate(payload)


@_enabled_router.post(
    "/edges",
    response_model=DocumentEdgeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document_edge(
    body: DocumentEdgeCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = DocumentGraphService(db)
    edge = await service.create_edge(
        tenant_id=tenant_id,
        src_document_id=body.src_document_id,
        dst_document_id=body.dst_document_id,
        edge_type=body.edge_type,
        actor_id=current_user.id,
        is_primary_parent=body.is_primary_parent,
        status=body.status,
        created_method=body.created_method,
        confidence=body.confidence,
        rationale=body.rationale,
        src_pel_doc_ref=body.src_pel_doc_ref,
        dst_pel_doc_ref=body.dst_pel_doc_ref,
        cited_document_version_id=body.cited_document_version_id,
        chunk_id=body.chunk_id,
        char_start=body.char_start,
        char_end=body.char_end,
        quote_hash=body.quote_hash,
        citation_text=body.citation_text,
        cited_version=body.cited_version,
    )
    return DocumentEdgeResponse.model_validate(edge)


@_enabled_router.post(
    "/edges/{edge_id}/confirm",
    response_model=DocumentEdgeResponse,
)
async def confirm_document_edge(
    edge_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = DocumentGraphService(db)
    edge = await service.confirm(
        tenant_id=tenant_id,
        edge_id=edge_id,
        actor_id=current_user.id,
    )
    return DocumentEdgeResponse.model_validate(edge)


@_enabled_router.post(
    "/edges/{edge_id}/reject",
    response_model=DocumentEdgeResponse,
)
async def reject_document_edge(
    edge_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    body: Optional[DocumentEdgeRejectRequest] = None,
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = DocumentGraphService(db)
    edge = await service.reject(
        tenant_id=tenant_id,
        edge_id=edge_id,
        actor_id=current_user.id,
        rationale=body.rationale if body else None,
    )
    return DocumentEdgeResponse.model_validate(edge)


@_enabled_router.delete(
    "/edges/{edge_id}",
    response_model=DocumentEdgeResponse,
)
async def delete_document_edge(
    edge_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = DocumentGraphService(db)
    edge = await service.soft_delete(
        tenant_id=tenant_id,
        edge_id=edge_id,
        actor_id=current_user.id,
    )
    return DocumentEdgeResponse.model_validate(edge)


@_enabled_router.get(
    "/edges/{edge_id}/citation-staleness",
    response_model=CitationStalenessResponse,
)
async def get_citation_staleness(
    edge_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:read"))],
):
    """Evaluate quote_hash freshness for a references edge (flag-on Doc Graph)."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = DocumentGraphHeuristicProposeService(db)
    payload = await service.citation_staleness_for_edge(tenant_id=tenant_id, edge_id=edge_id)
    return CitationStalenessResponse.model_validate(payload)


@_enabled_router.get(
    "/clauses/{clause_id}/documents",
    response_model=ClauseDocumentsResponse,
)
async def list_clause_documents(
    clause_id: str,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:read"))],
):
    """ISO reverse: library documents evidencing a clause, with CEL tip freshness."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = DocumentGraphIsoReverseService(db)
    payload = await service.list_documents_for_clause(tenant_id=tenant_id, clause_id=clause_id)
    return ClauseDocumentsResponse.model_validate(payload)


@_heuristic_router.post(
    "/documents/{document_id}/propose",
    response_model=HeuristicProposeResponse,
    status_code=status.HTTP_200_OK,
)
async def propose_document_edges(
    document_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
):
    """Heuristic / regex / vector proposals. Always proposed; never auto-applied."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = DocumentGraphHeuristicProposeService(db)
    result = await service.propose_for_document(
        tenant_id=tenant_id,
        document_id=document_id,
        actor_id=current_user.id,
    )
    return HeuristicProposeResponse(
        created=[DocumentEdgeResponse.model_validate(e) for e in result.created],
        created_count=len(result.created),
        skipped_existing=result.skipped_existing,
        skipped_unresolved=result.skipped_unresolved,
        sources=result.sources,
    )


@_enabled_router.post(
    "/demo/incident-management/seed",
    response_model=ImSeedResponse,
    status_code=status.HTTP_200_OK,
)
async def seed_incident_management_vertical(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("admin:manage"))],
):
    """Admin-only: idempotently seed the Incident Management Doc Graph demo vertical.

    Finds-or-creates library documents in the caller's tenant and confirms the
    IM spine edges. Does not invent tenants. Re-runs reuse existing rows/edges.
    """
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = DocumentGraphImSeedService(db)
    result = await service.seed(tenant_id=tenant_id, actor_id=current_user.id)
    return ImSeedResponse(
        documents=[
            ImSeedDocumentItem(
                role=d.role,
                document_id=d.document_id,
                title=d.title,
                created=d.created,
            )
            for d in result.documents
        ],
        edges=[
            ImSeedEdgeItem(
                src_role=e.src_role,
                dst_role=e.dst_role,
                edge_type=e.edge_type,
                edge_id=e.edge_id,
                created=e.created,
            )
            for e in result.edges
        ],
        documents_created=result.documents_created,
        documents_reused=result.documents_reused,
        edges_created=result.edges_created,
        edges_reused=result.edges_reused,
    )


router.include_router(_enabled_router)
router.include_router(_heuristic_router)
