"""Doc Graph API routes (ADR-0021 Wave 0).

Gated by ``settings.document_graph_enabled``. When closed, every route returns 404.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status

from src.api.dependencies import DbSession, require_permission
from src.api.schemas.document_graph import (
    DocumentEdgeCreate,
    DocumentEdgeListResponse,
    DocumentEdgeRejectRequest,
    DocumentEdgeResponse,
    DocumentThreadResponse,
)
from src.api.utils.tenant import require_tenant_id
from src.core.config import settings
from src.domain.models.document_graph import DocumentEdgeStatus, DocumentEdgeType
from src.domain.models.user import User
from src.domain.services.document_graph_service import DocumentGraphService

DISABLED_DETAIL = "Doc Graph is not enabled in this environment."

router = APIRouter()


async def require_document_graph_enabled() -> None:
    from fastapi import HTTPException

    if not settings.document_graph_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=DISABLED_DETAIL)


_enabled_router = APIRouter(dependencies=[Depends(require_document_graph_enabled)])


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
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = DocumentGraphService(db)
    payload = await service.get_thread(tenant_id=tenant_id, document_id=document_id)
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
    edge = await service.soft_delete(tenant_id=tenant_id, edge_id=edge_id)
    return DocumentEdgeResponse.model_validate(edge)


router.include_router(_enabled_router)
