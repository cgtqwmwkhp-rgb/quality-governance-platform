"""Global Search API routes.

Thin controller layer — all business logic lives in SearchService.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
from src.domain.services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter()


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


class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    total: int
    query: str
    facets: dict[str, object] = {}


@router.get("/", response_model=SearchResponse)
async def global_search(
    current_user: CurrentUser,
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
    """Unified search across all modules."""
    _ = date_from, date_to  # reserved for future date filtering

    service = SearchService(db)
    result = await service.search(
        query=q,
        tenant_id=current_user.tenant_id,
        module=module,
        status_filter=status,
        page=page,
        page_size=page_size,
        request_id=request_id,
    )
    return SearchResponse(**result)
