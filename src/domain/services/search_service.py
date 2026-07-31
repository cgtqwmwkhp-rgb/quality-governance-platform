"""Global search domain service.

Extracts multi-entity search logic from the global_search route module.
"""

import logging
from typing import Any, Optional

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.services.document_library_rbac import (
    PERM_ADMIN_MANAGE,
    PERM_DOCUMENT_READ,
    PERM_DOCUMENT_UPDATE,
    RESTRICTED_TAXONOMY_PERMISSIONS,
    user_can_read_library_document,
)
from src.domain.services.search_paths import build_search_path
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)

_SHORT_QUERY_THRESHOLD = 3
_CONTENT_SNIPPET_MAX_CHARS = 280
_SNIPPET_SUPPRESSED_SENSITIVITY = frozenset({"confidential", "restricted"})
_CONTENT_SEARCH_LIMIT = 10


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
        "entity_id",
        "path",
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
        entity_id: int | None = None,
        path: str | None = None,
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
        self.entity_id = entity_id
        self.path = path or build_search_path(type, entity_id)

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
            "entity_id": self.entity_id,
            "path": self.path,
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
        user: Any | None = None,
        module: Optional[str] = None,
        status_filter: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
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
        all_results.extend(await self._search_near_misses(query, tenant_id, request_id))
        all_results.extend(await self._search_rtas(query, tenant_id, request_id))
        all_results.extend(await self._search_complaints(query, tenant_id, request_id))
        all_results.extend(await self._search_risks(query, tenant_id, request_id))
        all_results.extend(await self._search_audits(query, tenant_id, request_id))
        all_results.extend(await self._search_actions(query, tenant_id, request_id))
        all_results.extend(await self._search_documents(query, tenant_id, request_id, user=user))
        all_results.extend(await self._search_document_content(query, user, request_id))

        if module:
            all_results = [r for r in all_results if r.module.lower() == module.lower()]
        if status_filter:
            statuses = {s.strip().lower().replace(" ", "_") for s in status_filter.split(",") if s.strip()}
            if statuses:
                all_results = [r for r in all_results if str(r.status).lower().replace(" ", "_") in statuses]
        if date_from or date_to:
            all_results = [r for r in all_results if self._within_date_range(r.date, date_from, date_to)]

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
    def _within_date_range(value: str, date_from: Optional[str], date_to: Optional[str]) -> bool:
        if not value:
            return False
        day = value[:10]
        if date_from and day < date_from[:10]:
            return False
        if date_to and day > date_to[:10]:
            return False
        return True

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

    @staticmethod
    def _user_has(user: Any, permission: str) -> bool:
        if getattr(user, "is_superuser", False):
            return True
        checker = getattr(user, "has_permission", None)
        if callable(checker):
            return bool(checker(permission))
        return False

    def _dialect_name(self) -> str | None:
        """Best-effort dialect name; None when unknown (treat as non-Postgres)."""
        candidates = []
        get_bind = getattr(self.db, "get_bind", None)
        if callable(get_bind):
            try:
                candidates.append(get_bind())
            except Exception:
                pass
        candidates.append(getattr(self.db, "bind", None))
        sync = getattr(self.db, "sync_session", None)
        if sync is not None:
            sync_get_bind = getattr(sync, "get_bind", None)
            if callable(sync_get_bind):
                try:
                    candidates.append(sync_get_bind())
                except Exception:
                    pass
            candidates.append(getattr(sync, "bind", None))
        for bind in candidates:
            name = getattr(getattr(bind, "dialect", None), "name", None)
            if name:
                return str(name)
        return None

    def _supports_chunk_fts(self) -> bool:
        return self._dialect_name() == "postgresql"

    @staticmethod
    def _sensitivity_value(document: Any) -> str | None:
        sens = getattr(document, "sensitivity", None)
        if sens is None:
            return None
        return str(sens.value if hasattr(sens, "value") else sens).lower()

    @staticmethod
    def _snippet_suppressed_for(document: Any) -> bool:
        return SearchService._sensitivity_value(document) in _SNIPPET_SUPPRESSED_SENSITIVITY

    @classmethod
    def _library_acl_sql_predicate(cls, user: Any, Document: Any, DocumentCategory: Any):
        """SQL-side ACL prefilter mirroring library read rules (fail-closed)."""
        if getattr(user, "is_superuser", False):
            return True

        staff_ok = or_(
            Document.access_level.is_(None),
            Document.access_level == "all_staff",
            Document.access_level == "",
        )
        clauses = [staff_ok]

        can_managers = cls._user_has(user, PERM_DOCUMENT_UPDATE) or cls._user_has(user, PERM_ADMIN_MANAGE)
        if can_managers:
            clauses.append(Document.access_level == "managers")

        if cls._user_has(user, PERM_ADMIN_MANAGE):
            clauses.append(Document.access_level == "restricted")
        else:
            allowed_taxes = [
                tax_id for tax_id, perm in RESTRICTED_TAXONOMY_PERMISSIONS.items() if cls._user_has(user, perm)
            ]
            if allowed_taxes:
                clauses.append(
                    and_(
                        Document.access_level == "restricted",
                        DocumentCategory.taxonomy_id.in_(allowed_taxes),
                    )
                )

        return or_(*clauses)

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
                .where(Incident.deleted_at.is_(None))
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
                        entity_id=inc.id,
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

    async def _search_near_misses(
        self, query: str, tenant_id: int | None, request_id: str | None
    ) -> list[SearchResultItem]:
        results: list[SearchResultItem] = []
        try:
            from src.domain.models.near_miss import NearMiss

            inline_vector = func.to_tsvector(
                "english",
                func.coalesce(cast(NearMiss.reference_number, String), "")
                + " "
                + func.coalesce(cast(NearMiss.description, String), "")
                + " "
                + func.coalesce(cast(NearMiss.location, String), ""),
            )
            tsquery = self._ts_query(query)
            rank = func.ts_rank(inline_vector, tsquery)

            if self._is_short_query(query):
                filter_clause = or_(
                    inline_vector.op("@@")(tsquery),
                    self._trgm_filter(cast(NearMiss.description, String), query),
                    NearMiss.reference_number.ilike(f"%{query}%"),
                )
                score = func.greatest(rank, self._trgm_score(cast(NearMiss.description, String), query))
            else:
                filter_clause = inline_vector.op("@@")(tsquery)
                score = rank

            stmt = (
                select(NearMiss, score.label("score"))
                .where(NearMiss.tenant_id == tenant_id)
                .where(filter_clause)
                .order_by(score.desc())
                .limit(10)
            )
            db_result = await self.db.execute(stmt)
            for nm, sc in db_result.all():
                relevance = min(100.0, 60 + float(sc) * 40)
                desc = (nm.description or "")[:200]
                results.append(
                    SearchResultItem(
                        id=nm.reference_number or f"NM-{nm.id}",
                        type="near_miss",
                        title=f"Near miss — {(nm.location or 'Unknown location')[:80]}",
                        description=desc,
                        module="Near Misses",
                        status=nm.status or "Open",
                        date=str(nm.event_date or nm.created_at or ""),
                        relevance=relevance,
                        highlights=query.lower().split(),
                        entity_id=nm.id,
                    )
                )
        except (AttributeError, SQLAlchemyError, ValueError) as e:
            logger.warning(
                "Search: near miss query failed [request_id=%s]: %s",
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
                        entity_id=rta.id,
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
                .where(Complaint.deleted_at.is_(None))
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
                        entity_id=cmp.id,
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
                        entity_id=risk.id,
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
                        entity_id=finding.id,
                        path=build_search_path("audit", finding.id, audit_run_id=finding.run_id),
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

            # storage_kind must match unified action_key kinds (capa, not capa_action).
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
                    "capa",
                    lambda action: action.reference_number or f"CAPA-{action.id}",
                    lambda action: action.created_at,
                ),
            ]

            for model, storage_kind, id_builder, date_builder in action_sources:
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
                            highlights=self._highlight_words(query, action.title, action.description) + [storage_kind],
                            entity_id=action.id,
                            path=build_search_path(
                                "action",
                                action.id,
                                action_key_kind=storage_kind,
                            ),
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
        self,
        query: str,
        tenant_id: int | None,
        request_id: str | None,
        *,
        user: Any | None = None,
    ) -> list[SearchResultItem]:
        results: list[SearchResultItem] = []
        if user is None or tenant_id is None:
            return results
        try:
            from src.domain.models.document import Document
            from src.domain.models.document_library import DocumentCategory

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
            documents = list(db_result.scalars().all())

            restricted_cat_ids = {
                d.category_id
                for d in documents
                if d.category_id is not None and (getattr(d, "access_level", None) or "") == "restricted"
            }
            taxonomy_by_cat: dict[int, str] = {}
            if restricted_cat_ids:
                cat_rows = await self.db.execute(
                    select(DocumentCategory.id, DocumentCategory.taxonomy_id).where(
                        DocumentCategory.id.in_(restricted_cat_ids)
                    )
                )
                taxonomy_by_cat = {row[0]: row[1] for row in cat_rows.all()}

            for document in documents:
                tax = taxonomy_by_cat.get(document.category_id) if document.category_id else None
                if not user_can_read_library_document(document, user, taxonomy_id=tax):
                    continue
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
                        entity_id=document.id,
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

    async def _search_document_content(
        self,
        query: str,
        user: Any | None,
        request_id: str | None,
    ) -> list[SearchResultItem]:
        """FTS over document_chunks with fail-closed library RBAC."""
        results: list[SearchResultItem] = []
        if user is None:
            return results
        if not self._user_has(user, PERM_DOCUMENT_READ):
            return results
        tenant_id = getattr(user, "tenant_id", None)
        if tenant_id is None:
            return results
        if not self._supports_chunk_fts():
            return results

        try:
            from src.domain.models.document import Document, DocumentChunk
            from src.domain.models.document_library import DocumentCategory

            tsquery = self._ts_query(query)
            rank = self._ts_rank(DocumentChunk.search_vector, query)
            headline = func.ts_headline(
                "english",
                DocumentChunk.content,
                tsquery,
                "MaxWords=35, MinWords=12, MaxFragments=1",
            ).label("snippet")

            stmt = (
                select(
                    DocumentChunk,
                    Document,
                    DocumentCategory.taxonomy_id,
                    headline,
                    rank.label("score"),
                )
                .join(Document, DocumentChunk.document_id == Document.id)
                .outerjoin(DocumentCategory, Document.category_id == DocumentCategory.id)
                .where(DocumentChunk.tenant_id == tenant_id)
                .where(Document.tenant_id == tenant_id)
                .where(Document.is_active.is_(True))
                .where(DocumentChunk.search_vector.op("@@")(tsquery))
                .where(self._library_acl_sql_predicate(user, Document, DocumentCategory))
                .order_by(rank.desc())
                .limit(_CONTENT_SEARCH_LIMIT)
            )

            db_result = await self.db.execute(stmt)
            rows = db_result.all()
            for chunk, document, taxonomy_id, snippet, score in rows:
                if not user_can_read_library_document(document, user, taxonomy_id=taxonomy_id):
                    logger.warning(
                        "Search: document_content ACL drop after SQL prefilter " "[request_id=%s doc_id=%s]",
                        request_id,
                        getattr(document, "id", None),
                    )
                    track_metric("search.document_content.acl_drop", 1)
                    continue

                suppress = self._snippet_suppressed_for(document)
                if suppress:
                    description = ""
                    highlights = ["snippet_suppressed"]
                else:
                    raw_snippet = (snippet or "")[:_CONTENT_SNIPPET_MAX_CHARS]
                    description = raw_snippet
                    highlights = self._highlight_words(query, raw_snippet, chunk.content)

                relevance = min(100.0, 60 + float(score or 0) * 40)
                results.append(
                    SearchResultItem(
                        id=document.reference_number or f"DOC-{document.id}",
                        type="document_content",
                        title=document.title or "Untitled Document",
                        description=description,
                        module="Document Content",
                        status=str(
                            document.status.value
                            if hasattr(document.status, "value")
                            else document.status or "Available"
                        ),
                        date=str(document.created_at or ""),
                        relevance=relevance,
                        highlights=highlights,
                        entity_id=document.id,
                        path=build_search_path(
                            "document_content",
                            document.id,
                            chunk_id=chunk.id,
                            page_number=chunk.page_number,
                        ),
                    )
                )
        except (AttributeError, SQLAlchemyError, ValueError, TypeError) as e:
            logger.warning(
                "Search: document content query failed [request_id=%s]: %s",
                request_id,
                type(e).__name__,
                exc_info=True,
            )
        return results
