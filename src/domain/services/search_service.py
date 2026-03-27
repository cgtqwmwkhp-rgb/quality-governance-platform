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

_SHORT_QUERY_THRESHOLD = 3


class SearchResultItem:
    """Lightweight container for a search result."""

    __slots__ = (
        "id",
        "type",
        "title",
        "description",
        "module",
        "status",
        "date",
        "relevance",
        "highlights",
    )

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

        all_results: list[SearchResultItem] = []

        all_results.extend(await self._search_incidents(query, tenant_id, request_id))
        all_results.extend(await self._search_rtas(query, tenant_id, request_id))
        all_results.extend(await self._search_complaints(query, tenant_id, request_id))
        all_results.extend(await self._search_risks(query, tenant_id, request_id))
        all_results.extend(await self._search_audits(query, tenant_id, request_id))
        all_results.extend(await self._search_actions(query, tenant_id, request_id))
        all_results.extend(await self._search_documents(query, tenant_id, request_id))

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
    # Full-text search helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_short_query(query: str) -> bool:
        return len(query.strip()) <= _SHORT_QUERY_THRESHOLD

    @staticmethod
    def _ts_query(query: str):
        """Build a tsquery, falling back to plainto_tsquery for safety."""
        return func.plainto_tsquery("english", query)

    @staticmethod
    def _ts_rank(search_vector_col, query: str):
        return func.ts_rank(search_vector_col, SearchService._ts_query(query))

    @staticmethod
    def _trgm_filter(col, query: str, threshold: float = 0.3):
        """pg_trgm similarity filter for fuzzy matching on short queries."""
        return func.similarity(col, query) > threshold

    @staticmethod
    def _trgm_score(col, query: str):
        return func.similarity(col, query)

    @staticmethod
    def _highlight_words(query: str, *values: str | None) -> list[str]:
        words = query.lower().split()
        haystack = " ".join(value or "" for value in values).lower()
        return [word for word in words if word in haystack]

    @staticmethod
    def _simple_relevance(query: str, *values: str | None) -> float:
        normalized_query = query.lower()
        lowered_values = [value.lower() for value in values if value]
        bonus = 0
        if any(normalized_query in value for value in lowered_values):
            bonus += 20
        bonus += min(20, sum(value.count(normalized_query) for value in lowered_values) * 5)
        bonus += min(15, len(SearchService._highlight_words(query, *values)) * 5)
        return min(95.0, 55.0 + bonus)

    # ------------------------------------------------------------------
    # Per-entity search helpers
    # ------------------------------------------------------------------

    async def _search_incidents(
        self, query: str, tenant_id: int | None, request_id: str | None
    ) -> list[SearchResultItem]:
        results: list[SearchResultItem] = []
        try:
            from src.domain.models.incident import Incident

            tsquery = self._ts_query(query)
            rank = self._ts_rank(Incident.search_vector, query)

            if self._is_short_query(query):
                filter_clause = or_(
                    Incident.search_vector.op("@@")(tsquery),
                    self._trgm_filter(Incident.title, query),
                )
                score = func.greatest(rank, self._trgm_score(Incident.title, query))
            else:
                filter_clause = Incident.search_vector.op("@@")(tsquery)
                score = rank

            stmt = (
                select(Incident, score.label("score"))
                .where(Incident.tenant_id == tenant_id)
                .where(filter_clause)
                .order_by(score.desc())
                .limit(10)
            )
            db_result = await self.db.execute(stmt)
            for inc, sc in db_result.all():
                relevance = min(100.0, 60 + float(sc) * 40)
                words = query.lower().split()
                title_lower = (inc.title or "").lower()
                desc_lower = (inc.description or "").lower()
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
        except (AttributeError, SQLAlchemyError, ValueError) as e:
            logger.warning(
                "Search: incident query failed [request_id=%s]: %s",
                request_id,
                type(e).__name__,
                exc_info=True,
            )
        return results

    async def _search_rtas(self, query: str, tenant_id: int | None, request_id: str | None) -> list[SearchResultItem]:
        results: list[SearchResultItem] = []
        try:
            from src.domain.models.rta import RTA

            inline_vector = func.to_tsvector(
                "english",
                func.coalesce(cast(RTA.location, String), "") + " " + func.coalesce(cast(RTA.description, String), ""),
            )
            tsquery = self._ts_query(query)
            rank = func.ts_rank(inline_vector, tsquery)

            if self._is_short_query(query):
                filter_clause = or_(
                    inline_vector.op("@@")(tsquery),
                    self._trgm_filter(cast(RTA.location, String), query),
                )
                score = func.greatest(rank, self._trgm_score(cast(RTA.location, String), query))
            else:
                filter_clause = inline_vector.op("@@")(tsquery)
                score = rank

            stmt = (
                select(RTA, score.label("score"))
                .where(RTA.tenant_id == tenant_id)
                .where(filter_clause)
                .order_by(score.desc())
                .limit(10)
            )
            db_result = await self.db.execute(stmt)
            for rta, sc in db_result.all():
                relevance = min(100.0, 60 + float(sc) * 40)
                results.append(
                    SearchResultItem(
                        id=rta.reference_number or f"RTA-{rta.id}",
                        type="rta",
                        title=f"RTA - {rta.location or 'Unknown Location'}",
                        description=(rta.description or "")[:200],
                        module="RTAs",
                        status=rta.status or "Open",
                        date=str(rta.collision_date or rta.created_at or ""),
                        relevance=relevance,
                        highlights=query.lower().split(),
                    )
                )
        except (AttributeError, SQLAlchemyError, ValueError) as e:
            logger.warning(
                "Search: RTA query failed [request_id=%s]: %s",
                request_id,
                type(e).__name__,
                exc_info=True,
            )
        return results

    async def _search_complaints(
        self, query: str, tenant_id: int | None, request_id: str | None
    ) -> list[SearchResultItem]:
        results: list[SearchResultItem] = []
        try:
            from src.domain.models.complaint import Complaint

            tsquery = self._ts_query(query)
            rank = self._ts_rank(Complaint.search_vector, query)

            if self._is_short_query(query):
                filter_clause = or_(
                    Complaint.search_vector.op("@@")(tsquery),
                    self._trgm_filter(Complaint.title, query),
                )
                score = func.greatest(rank, self._trgm_score(Complaint.title, query))
            else:
                filter_clause = Complaint.search_vector.op("@@")(tsquery)
                score = rank

            stmt = (
                select(Complaint, score.label("score"))
                .where(Complaint.tenant_id == tenant_id)
                .where(filter_clause)
                .order_by(score.desc())
                .limit(10)
            )
            db_result = await self.db.execute(stmt)
            for cmp, sc in db_result.all():
                relevance = min(100.0, 60 + float(sc) * 40)
                words = query.lower().split()
                title_lower = (cmp.title or "").lower()
                desc_lower = (cmp.description or "").lower()
                results.append(
                    SearchResultItem(
                        id=cmp.reference_number or f"CMP-{cmp.id}",
                        type="complaint",
                        title=cmp.title or "Untitled Complaint",
                        description=(cmp.description or "")[:200],
                        module="Complaints",
                        status=cmp.status or "Open",
                        date=str(cmp.created_at or ""),
                        relevance=relevance,
                        highlights=[w for w in words if w in title_lower or w in desc_lower],
                    )
                )
        except (AttributeError, SQLAlchemyError, ValueError) as e:
            logger.warning(
                "Search: complaint query failed [request_id=%s]: %s",
                request_id,
                type(e).__name__,
                exc_info=True,
            )
        return results

    async def _search_risks(self, query: str, tenant_id: int | None, request_id: str | None) -> list[SearchResultItem]:
        results: list[SearchResultItem] = []
        try:
            from src.domain.models.risk import Risk

            tsquery = self._ts_query(query)
            rank = self._ts_rank(Risk.search_vector, query)

            if self._is_short_query(query):
                filter_clause = or_(
                    Risk.search_vector.op("@@")(tsquery),
                    self._trgm_filter(Risk.title, query),
                )
                score = func.greatest(rank, self._trgm_score(Risk.title, query))
            else:
                filter_clause = Risk.search_vector.op("@@")(tsquery)
                score = rank

            stmt = (
                select(Risk, score.label("score"))
                .where(Risk.tenant_id == tenant_id)
                .where(filter_clause)
                .order_by(score.desc())
                .limit(10)
            )
            db_result = await self.db.execute(stmt)
            for risk, sc in db_result.all():
                relevance = min(100.0, 60 + float(sc) * 40)
                words = query.lower().split()
                title_lower = (risk.title or "").lower()
                desc_lower = (risk.description or "").lower()
                results.append(
                    SearchResultItem(
                        id=f"RSK-{risk.id}",
                        type="risk",
                        title=risk.title or "Untitled Risk",
                        description=(risk.description or "")[:200],
                        module="Risks",
                        status=risk.status or "Open",
                        date=str(risk.created_at or ""),
                        relevance=relevance,
                        highlights=[w for w in words if w in title_lower or w in desc_lower],
                    )
                )
        except (AttributeError, SQLAlchemyError, ValueError) as e:
            logger.warning(
                "Search: risk query failed [request_id=%s]: %s",
                request_id,
                type(e).__name__,
                exc_info=True,
            )
        return results

    async def _search_audits(self, query: str, tenant_id: int | None, request_id: str | None) -> list[SearchResultItem]:
        results: list[SearchResultItem] = []
        try:
            from src.domain.models.audit import AuditFinding

            search_filter = f"%{query}%"
            stmt = (
                select(AuditFinding)
                .where(AuditFinding.tenant_id == tenant_id)
                .where(or_(AuditFinding.title.ilike(search_filter), AuditFinding.description.ilike(search_filter)))
                .order_by(AuditFinding.created_at.desc())
                .limit(10)
            )
            db_result = await self.db.execute(stmt)
            for finding in db_result.scalars().all():
                results.append(
                    SearchResultItem(
                        id=finding.reference_number or f"AUD-{finding.id}",
                        type="audit",
                        title=finding.title or "Untitled Audit Finding",
                        description=(finding.description or "")[:200],
                        module="Audits",
                        status=str(
                            finding.status.value if hasattr(finding.status, "value") else finding.status or "Open"
                        ),
                        date=str(finding.created_at or ""),
                        relevance=self._simple_relevance(query, finding.title, finding.description),
                        highlights=self._highlight_words(query, finding.title, finding.description),
                    )
                )
        except (AttributeError, SQLAlchemyError, ValueError) as e:
            logger.warning(
                "Search: audit query failed [request_id=%s]: %s",
                request_id,
                type(e).__name__,
                exc_info=True,
            )
        return results

    async def _search_actions(
        self, query: str, tenant_id: int | None, request_id: str | None
    ) -> list[SearchResultItem]:
        results: list[SearchResultItem] = []
        search_filter = f"%{query}%"

        try:
            from src.domain.models.capa import CAPAAction
            from src.domain.models.complaint import ComplaintAction
            from src.domain.models.incident import IncidentAction
            from src.domain.models.investigation import InvestigationAction
            from src.domain.models.rta import RTAAction

            action_sources = [
                (
                    IncidentAction,
                    "incident_action",
                    lambda action: action.reference_number or f"ACT-{action.id}",
                    lambda action: action.created_at,
                ),
                (
                    RTAAction,
                    "rta_action",
                    lambda action: action.reference_number or f"ACT-{action.id}",
                    lambda action: action.created_at,
                ),
                (
                    ComplaintAction,
                    "complaint_action",
                    lambda action: action.reference_number or f"ACT-{action.id}",
                    lambda action: action.created_at,
                ),
                (
                    InvestigationAction,
                    "investigation_action",
                    lambda action: action.reference_number or f"ACT-{action.id}",
                    lambda action: action.created_at,
                ),
                (
                    CAPAAction,
                    "capa_action",
                    lambda action: action.reference_number or f"CAPA-{action.id}",
                    lambda action: action.created_at,
                ),
            ]

            for model, action_type, id_builder, date_builder in action_sources:
                stmt = (
                    select(model)
                    .where(model.tenant_id == tenant_id)
                    .where(or_(model.title.ilike(search_filter), model.description.ilike(search_filter)))
                    .order_by(model.created_at.desc())
                    .limit(5)
                )
                db_result = await self.db.execute(stmt)
                for action in db_result.scalars().all():
                    results.append(
                        SearchResultItem(
                            id=id_builder(action),
                            type="action",
                            title=action.title or "Untitled Action",
                            description=(action.description or "")[:200],
                            module="Actions",
                            status=str(
                                action.status.value if hasattr(action.status, "value") else action.status or "Open"
                            ),
                            date=str(date_builder(action) or ""),
                            relevance=self._simple_relevance(query, action.title, action.description),
                            highlights=self._highlight_words(query, action.title, action.description) + [action_type],
                        )
                    )
        except (AttributeError, SQLAlchemyError, ValueError) as e:
            logger.warning(
                "Search: action query failed [request_id=%s]: %s",
                request_id,
                type(e).__name__,
                exc_info=True,
            )
        return results

    async def _search_documents(
        self, query: str, tenant_id: int | None, request_id: str | None
    ) -> list[SearchResultItem]:
        results: list[SearchResultItem] = []
        try:
            from src.domain.models.document import Document

            search_filter = f"%{query}%"
            stmt = (
                select(Document)
                .where(Document.tenant_id == tenant_id)
                .where(
                    or_(
                        Document.title.ilike(search_filter),
                        Document.description.ilike(search_filter),
                        Document.ai_summary.ilike(search_filter),
                    )
                )
                .order_by(Document.created_at.desc())
                .limit(10)
            )
            db_result = await self.db.execute(stmt)
            for document in db_result.scalars().all():
                results.append(
                    SearchResultItem(
                        id=document.reference_number or f"DOC-{document.id}",
                        type="document",
                        title=document.title or "Untitled Document",
                        description=((document.ai_summary or document.description or "")[:200]),
                        module="Documents",
                        status=str(
                            document.status.value
                            if hasattr(document.status, "value")
                            else document.status or "Available"
                        ),
                        date=str(document.created_at or ""),
                        relevance=self._simple_relevance(
                            query,
                            document.title,
                            document.description,
                            document.ai_summary,
                        ),
                        highlights=self._highlight_words(
                            query,
                            document.title,
                            document.description,
                            document.ai_summary,
                        ),
                    )
                )
        except (AttributeError, SQLAlchemyError, ValueError) as e:
            logger.warning(
                "Search: document query failed [request_id=%s]: %s",
                request_id,
                type(e).__name__,
                exc_info=True,
            )
        return results
