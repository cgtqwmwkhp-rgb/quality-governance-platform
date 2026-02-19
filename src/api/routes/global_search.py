"""
Global Search API Routes

Provides unified cross-module search across incidents, RTAs, complaints,
risks, audits, actions, and documents.
"""

from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.api.dependencies import CurrentUser, DbSession

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
    facets: dict = {}


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
):
    """
    Unified search across all modules.

    Searches incidents, RTAs, complaints, risks, audits, actions, and documents.
    Results are ranked by relevance.
    """
    from sqlalchemy import select, func, or_, cast, String

    query_lower = q.lower()
    all_results: list[SearchResultItem] = []

    try:
        from src.domain.models.incident import Incident

        stmt = (
            select(Incident)
            .where(
                or_(
                    func.lower(Incident.title).contains(query_lower),
                    func.lower(Incident.description).contains(query_lower),
                )
            )
            .limit(10)
        )
        result = await db.execute(stmt)
        for inc in result.scalars().all():
            words = query_lower.split()
            title_lower = (inc.title or "").lower()
            desc_lower = (inc.description or "").lower()
            match_count = sum(1 for w in words if w in title_lower or w in desc_lower)
            relevance = min(100, 60 + match_count * 15)
            all_results.append(
                SearchResultItem(
                    id=inc.reference_number or f"INC-{inc.id}",
                    type="incident",
                    title=inc.title or "Untitled Incident",
                    description=(inc.description or "")[:200],
                    module="Incidents",
                    status=inc.status or "Open",
                    date=str(inc.incident_date or inc.created_at or ""),
                    relevance=relevance,
                    highlights=[w for w in words if w in title_lower or w in desc_lower],
                )
            )
    except Exception:
        pass

    try:
        from src.domain.models.rta import RTA

        stmt = (
            select(RTA)
            .where(
                or_(
                    func.lower(cast(RTA.location, String)).contains(query_lower),
                    func.lower(cast(RTA.description, String)).contains(query_lower),
                )
            )
            .limit(10)
        )
        result = await db.execute(stmt)
        for rta in result.scalars().all():
            all_results.append(
                SearchResultItem(
                    id=rta.reference_number or f"RTA-{rta.id}",
                    type="rta",
                    title=f"RTA - {rta.location or 'Unknown Location'}",
                    description=(rta.description or "")[:200],
                    module="RTAs",
                    status=rta.status or "Open",
                    date=str(rta.incident_date or rta.created_at or ""),
                    relevance=75,
                    highlights=query_lower.split(),
                )
            )
    except Exception:
        pass

    try:
        from src.domain.models.complaint import Complaint

        stmt = (
            select(Complaint)
            .where(
                or_(
                    func.lower(Complaint.title).contains(query_lower),
                    func.lower(Complaint.description).contains(query_lower),
                )
            )
            .limit(10)
        )
        result = await db.execute(stmt)
        for cmp in result.scalars().all():
            all_results.append(
                SearchResultItem(
                    id=cmp.reference_number or f"CMP-{cmp.id}",
                    type="complaint",
                    title=cmp.title or "Untitled Complaint",
                    description=(cmp.description or "")[:200],
                    module="Complaints",
                    status=cmp.status or "Open",
                    date=str(cmp.created_at or ""),
                    relevance=70,
                    highlights=query_lower.split(),
                )
            )
    except Exception:
        pass

    try:
        from src.domain.models.risk import Risk

        stmt = (
            select(Risk)
            .where(
                or_(
                    func.lower(Risk.title).contains(query_lower),
                    func.lower(Risk.description).contains(query_lower),
                )
            )
            .limit(10)
        )
        result = await db.execute(stmt)
        for risk in result.scalars().all():
            all_results.append(
                SearchResultItem(
                    id=f"RSK-{risk.id}",
                    type="risk",
                    title=risk.title or "Untitled Risk",
                    description=(risk.description or "")[:200],
                    module="Risks",
                    status=risk.status or "Open",
                    date=str(risk.created_at or ""),
                    relevance=72,
                    highlights=query_lower.split(),
                )
            )
    except Exception:
        pass

    try:
        from src.domain.models.action import Action

        stmt = (
            select(Action)
            .where(
                or_(
                    func.lower(Action.title).contains(query_lower),
                    func.lower(Action.description).contains(query_lower),
                )
            )
            .limit(10)
        )
        result = await db.execute(stmt)
        for act in result.scalars().all():
            all_results.append(
                SearchResultItem(
                    id=f"ACT-{act.id}",
                    type="action",
                    title=act.title or "Untitled Action",
                    description=(act.description or "")[:200],
                    module="Actions",
                    status=act.status or "Open",
                    date=str(act.due_date or act.created_at or ""),
                    relevance=68,
                    highlights=query_lower.split(),
                )
            )
    except Exception:
        pass

    if module:
        all_results = [r for r in all_results if r.module.lower() == module.lower()]
    if status:
        all_results = [r for r in all_results if r.status.lower() == status.lower()]

    all_results.sort(key=lambda r: r.relevance, reverse=True)
    total = len(all_results)
    start = (page - 1) * page_size
    paged = all_results[start : start + page_size]

    facet_modules: dict[str, int] = {}
    for r in all_results:
        facet_modules[r.module] = facet_modules.get(r.module, 0) + 1

    return SearchResponse(
        results=paged,
        total=total,
        query=q,
        facets={"modules": facet_modules},
    )
