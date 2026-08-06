"""Global Search API routes.

Thin controller layer — all business logic lives in SearchService / interpret service.
"""

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.api.dependencies import DbSession
from src.api.dependencies.partner import PartnerCaller, require_auth_or_partner_scope
from src.api.dependencies.request_context import get_request_id
from src.domain.services.search_interpret_service import interpret_search_query
from src.domain.services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter()
_PartnerSearchUser = Annotated[PartnerCaller, Depends(require_auth_or_partner_scope("search:read"))]


class SearchResultItem(BaseModel):
    id: str
    type: str
    title: str
    description: str
    module: str
    status: str
    date: str
    relevance: float
    highlights: List[str] = []
    entity_id: Optional[int] = None
    path: Optional[str] = None


class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    total: int
    query: str
    facets: dict[str, object] = {}


class InterpretRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=200)


class InterpretResponse(BaseModel):
    q: str
    module: Optional[str] = None
    status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    navigate: Optional[str] = None
    label: Optional[str] = None
    source: str = "keyword"


@router.get("", response_model=SearchResponse, include_in_schema=False)
@router.get("/", response_model=SearchResponse)
async def global_search(
    current_user: _PartnerSearchUser,
    db: DbSession,
    q: str = Query(..., min_length=1, max_length=200),
    module: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    request_id: str = Depends(get_request_id),
) -> SearchResponse:
    """Unified search across all modules.

    Partner bearers require ``search:read``. JWT session callers keep the
    existing authenticated-only posture.
    """
    service = SearchService(db)
    result = await service.search(
        query=q,
        tenant_id=current_user.tenant_id,
        user=current_user,
        module=module,
        status_filter=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        request_id=request_id,
    )
    return SearchResponse(**result)


@router.post("/interpret", response_model=InterpretResponse)
async def interpret_search(
    body: InterpretRequest,
    current_user: _PartnerSearchUser,
) -> InterpretResponse:
    """Interpret natural-language search into structured FTS filters (fail-closed).

    Partner bearers require ``search:read`` (same gate as ``GET /search/``).
    """
    _ = current_user
    intent = await interpret_search_query(body.q)
    return InterpretResponse(**intent)
