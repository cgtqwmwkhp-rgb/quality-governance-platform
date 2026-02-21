"""Global search domain service.

Extracts multi-entity search logic from the global_search route module.
"""

import logging
from typing import Any, Optional

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)


class SearchResultItem:
    """Lightweight container for a search result."""

    __slots__ = ("id", "type", "title", "description", "module", "status", "date", "relevance", "highlights")

    def __init__(
        self,
        *,
        id: str,
        type: str,
        title: str,
        description: str,
        module: str,
        status: str,
        date: str,
        relevance: float,
        highlights: list[str] | None = None,
    ):
        self.id = id
        self.type = type
        self.title = title
        self.description = description
        self.module = module
        self.status = status
        self.date = date
        self.relevance = relevance
        self.highlights = highlights or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "module": self.module,
            "status": self.status,
            "date": self.date,
            "relevance": self.relevance,
            "highlights": self.highlights,
        }


class SearchService:
    """Unified cross-module search across incidents, RTAs, complaints, and risks."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(
        self,
        *,
        query: str,
        tenant_id: int | None,
        module: Optional[str] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a cross-module search.

        Returns dict with results, total, query, and facets.
        """
        track_metric("search.query", 1, {"module": module or "all"})
        track_metric("search.executed", 1)

        query_lower = query.lower()
        all_results: list[SearchResultItem] = []

        all_results.extend(await self._search_incidents(query_lower, tenant_id, request_id))
        all_results.extend(await self._search_rtas(query_lower, tenant_id, request_id))
        all_results.extend(await self._search_complaints(query_lower, tenant_id, request_id))
        all_results.extend(await self._search_risks(query_lower, tenant_id, request_id))

        if module:
            all_results = [r for r in all_results if r.module.lower() == module.lower()]
        if status_filter:
            all_results = [r for r in all_results if r.status.lower() == status_filter.lower()]

        all_results.sort(key=lambda r: r.relevance, reverse=True)
        total = len(all_results)
        start = (page - 1) * page_size
        paged = all_results[start : start + page_size]

        facet_modules: dict[str, int] = {}
        for r in all_results:
            facet_modules[r.module] = facet_modules.get(r.module, 0) + 1

        return {
            "results": [r.to_dict() for r in paged],
            "total": total,
            "query": query,
            "facets": {"modules": facet_modules},
        }

    # ------------------------------------------------------------------
    # Per-entity search helpers
    # ------------------------------------------------------------------

    async def _search_incidents(
        self, query_lower: str, tenant_id: int | None, request_id: str | None
    ) -> list[SearchResultItem]:
        results: list[SearchResultItem] = []
        try:
            from src.domain.models.incident import Incident

            stmt = (
                select(Incident)
                .where(Incident.tenant_id == tenant_id)
                .where(
                    or_(
                        func.lower(Incident.title).contains(query_lower),
                        func.lower(Incident.description).contains(query_lower),
                    )
                )
                .limit(10)
            )
            db_result = await self.db.execute(stmt)
            for inc in db_result.scalars().all():
                words = query_lower.split()
                title_lower = (inc.title or "").lower()
                desc_lower = (inc.description or "").lower()
                match_count = sum(1 for w in words if w in title_lower or w in desc_lower)
                relevance = min(100, 60 + match_count * 15)
                results.append(
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
        except (SQLAlchemyError, ValueError) as e:
            logger.warning(
                "Search: incident query failed [request_id=%s]: %s",
                request_id,
                type(e).__name__,
                exc_info=True,
            )
        return results

    async def _search_rtas(
        self, query_lower: str, tenant_id: int | None, request_id: str | None
    ) -> list[SearchResultItem]:
        results: list[SearchResultItem] = []
        try:
            from src.domain.models.rta import RTA

            stmt = (
                select(RTA)
                .where(RTA.tenant_id == tenant_id)
                .where(
                    or_(
                        func.lower(cast(RTA.location, String)).contains(query_lower),
                        func.lower(cast(RTA.description, String)).contains(query_lower),
                    )
                )
                .limit(10)
            )
            db_result = await self.db.execute(stmt)
            for rta in db_result.scalars().all():
                results.append(
                    SearchResultItem(
                        id=rta.reference_number or f"RTA-{rta.id}",
                        type="rta",
                        title=f"RTA - {rta.location or 'Unknown Location'}",
                        description=(rta.description or "")[:200],
                        module="RTAs",
                        status=rta.status or "Open",
                        date=str(rta.collision_date or rta.created_at or ""),
                        relevance=75,
                        highlights=query_lower.split(),
                    )
                )
        except (SQLAlchemyError, ValueError) as e:
            logger.warning(
                "Search: RTA query failed [request_id=%s]: %s",
                request_id,
                type(e).__name__,
                exc_info=True,
            )
        return results

    async def _search_complaints(
        self, query_lower: str, tenant_id: int | None, request_id: str | None
    ) -> list[SearchResultItem]:
        results: list[SearchResultItem] = []
        try:
            from src.domain.models.complaint import Complaint

            stmt = (
                select(Complaint)
                .where(Complaint.tenant_id == tenant_id)
                .where(
                    or_(
                        func.lower(Complaint.title).contains(query_lower),
                        func.lower(Complaint.description).contains(query_lower),
                    )
                )
                .limit(10)
            )
            db_result = await self.db.execute(stmt)
            for cmp in db_result.scalars().all():
                results.append(
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
        except (SQLAlchemyError, ValueError) as e:
            logger.warning(
                "Search: complaint query failed [request_id=%s]: %s",
                request_id,
                type(e).__name__,
                exc_info=True,
            )
        return results

    async def _search_risks(
        self, query_lower: str, tenant_id: int | None, request_id: str | None
    ) -> list[SearchResultItem]:
        results: list[SearchResultItem] = []
        try:
            from src.domain.models.risk import Risk

            stmt = (
                select(Risk)
                .where(Risk.tenant_id == tenant_id)
                .where(
                    or_(
                        func.lower(Risk.title).contains(query_lower),
                        func.lower(Risk.description).contains(query_lower),
                    )
                )
                .limit(10)
            )
            db_result = await self.db.execute(stmt)
            for risk in db_result.scalars().all():
                results.append(
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
        except (SQLAlchemyError, ValueError) as e:
            logger.warning(
                "Search: risk query failed [request_id=%s]: %s",
                request_id,
                type(e).__name__,
                exc_info=True,
            )
        return results
