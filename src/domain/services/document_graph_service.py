"""Doc Graph domain service (ADR-0021 Wave 0 + X-0 / X-0b).

create / list / confirm / reject / soft_delete / primary-implements thread walk,
plus cycle detection on ``implements``, one-primary-parent enforcement (service
guard + ``ux_document_edges_one_primary_parent``), AuditLog on graph mutations,
and confirmed-only ambient thread (opt-in proposed via ``include_proposed``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import ConflictError, NotFoundError, ValidationError
from src.domain.models.document import Document
from src.domain.models.document_graph import (
    CANONICAL_UNDIRECTED_TYPES,
    DocumentEdge,
    DocumentEdgeMethod,
    DocumentEdgeStatus,
    DocumentEdgeType,
)
from src.domain.services.audit_service import record_audit_event

THREAD_MAX_DEPTH = 4
THREAD_HOP_ORIGIN = "graph"

# ADR-0021: AI/heuristic must never auto-confirm edges that drive publish impact.
IMPACT_DRIVING_EDGE_TYPES = frozenset(
    {
        DocumentEdgeType.IMPLEMENTS,
        DocumentEdgeType.REQUIRES_RECORD,
        DocumentEdgeType.CONFLICTS_WITH,
    }
)
_NO_AUTO_CONFIRM_METHODS = frozenset(
    {
        DocumentEdgeMethod.AI,
        DocumentEdgeMethod.HEURISTIC,
    }
)

# Statuses that participate in cycle detection (rejected edges are inert).
_ACTIVE_STATUSES = (
    DocumentEdgeStatus.PROPOSED,
    DocumentEdgeStatus.CONFIRMED,
    DocumentEdgeStatus.NEEDS_REVIEW,
)


def thread_walk_statuses(*, include_proposed: bool = False) -> tuple[DocumentEdgeStatus, ...]:
    """Statuses visible on ambient Doc Graph thread walks.

    Confirmed-only by default so proposed / needs_review edges cannot inflate
    the ambient spine. Pass ``include_proposed=True`` to include pending statuses.
    Rejected edges never participate.
    """
    if include_proposed:
        return (
            DocumentEdgeStatus.CONFIRMED,
            DocumentEdgeStatus.PROPOSED,
            DocumentEdgeStatus.NEEDS_REVIEW,
        )
    return (DocumentEdgeStatus.CONFIRMED,)


def document_href(document_id: int) -> str:
    """SPA deep-link for a library document (RiskUpstreamItem spirit)."""
    return f"/documents/{document_id}"


def _as_utc(value: Optional[datetime] = None) -> datetime:
    if value is None:
        value = datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _coerce_edge_type(edge_type: DocumentEdgeType | str) -> DocumentEdgeType:
    if isinstance(edge_type, DocumentEdgeType):
        return edge_type
    try:
        return DocumentEdgeType(str(edge_type))
    except ValueError as exc:
        raise ValidationError(
            f"Unsupported edge_type '{edge_type}'",
            code="DOCUMENT_GRAPH_INVALID_EDGE_TYPE",
        ) from exc


def _coerce_created_method(created_method: DocumentEdgeMethod | str) -> DocumentEdgeMethod:
    if isinstance(created_method, DocumentEdgeMethod):
        return created_method
    try:
        return DocumentEdgeMethod(str(created_method))
    except ValueError as exc:
        raise ValidationError(
            f"Unsupported created_method '{created_method}'",
            code="DOCUMENT_GRAPH_INVALID_METHOD",
        ) from exc


def _coerce_edge_status(status: DocumentEdgeStatus | str | None) -> DocumentEdgeStatus:
    if status is None:
        return DocumentEdgeStatus.PROPOSED
    if isinstance(status, DocumentEdgeStatus):
        return status
    try:
        return DocumentEdgeStatus(str(status))
    except ValueError as exc:
        raise ValidationError(
            f"Unsupported status '{status}'",
            code="DOCUMENT_GRAPH_INVALID_STATUS",
        ) from exc


def canonicalize_endpoints(
    edge_type: DocumentEdgeType,
    src_document_id: int,
    dst_document_id: int,
) -> tuple[int, int]:
    """For undirected peer types, store ``src_id < dst_id`` canonically."""
    if edge_type in CANONICAL_UNDIRECTED_TYPES and src_document_id > dst_document_id:
        return dst_document_id, src_document_id
    return src_document_id, dst_document_id


def _document_reference(doc: Optional[Any]) -> Optional[str]:
    if doc is None:
        return None
    pel = getattr(doc, "pel_doc_ref", None)
    if pel:
        return str(pel)
    ref = getattr(doc, "reference_number", None)
    return str(ref) if ref else None


class DocumentGraphService:
    """Tenant-scoped Doc Graph operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_document_or_404(self, *, tenant_id: int, document_id: int) -> Document:
        result = await self.db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.tenant_id == tenant_id,
            )
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            raise NotFoundError(
                f"Document {document_id} not found",
                code="DOCUMENT_NOT_FOUND",
                details={"document_id": document_id},
            )
        return doc

    async def _get_edge_or_404(self, *, tenant_id: int, edge_id: int) -> DocumentEdge:
        result = await self.db.execute(
            select(DocumentEdge).where(
                DocumentEdge.id == edge_id,
                DocumentEdge.tenant_id == tenant_id,
                DocumentEdge.deleted_at.is_(None),
            )
        )
        edge = result.scalar_one_or_none()
        if edge is None:
            raise NotFoundError(
                f"Document edge {edge_id} not found",
                code="DOCUMENT_EDGE_NOT_FOUND",
                details={"edge_id": edge_id},
            )
        return edge

    async def _find_live_edge_id(
        self,
        *,
        tenant_id: int,
        src_document_id: int,
        dst_document_id: int,
        edge_type: DocumentEdgeType,
    ) -> Optional[int]:
        """Id of the row already holding this pair's unique slot, if any.

        ``ux_document_edges_tenant_src_dst_type_live`` is partial on
        ``deleted_at IS NULL``, so a *rejected* edge still occupies the slot.
        Status is deliberately not filtered here.
        """
        result = await self.db.execute(
            select(DocumentEdge.id).where(
                DocumentEdge.tenant_id == tenant_id,
                DocumentEdge.src_document_id == src_document_id,
                DocumentEdge.dst_document_id == dst_document_id,
                DocumentEdge.edge_type == edge_type,
                DocumentEdge.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _find_other_primary_parent_edge_id(
        self,
        *,
        tenant_id: int,
        child_document_id: int,
        exclude_edge_id: Optional[int] = None,
    ) -> Optional[int]:
        """Live primary ``implements`` parent for this child, if any (excluding one edge).

        Status is deliberately not filtered: ``ux_document_edges_one_primary_parent``
        is partial on ``is_primary_parent AND edge_type='implements' AND deleted_at
        IS NULL`` only. A rejected primary that still carries the flag would occupy
        the unique slot; matching that predicate here refuses before IntegrityError.
        ``reject`` clears ``is_primary_parent`` so the slot frees intentionally.
        """
        query = (
            select(DocumentEdge.id)
            .where(
                DocumentEdge.tenant_id == tenant_id,
                DocumentEdge.src_document_id == child_document_id,
                DocumentEdge.edge_type == DocumentEdgeType.IMPLEMENTS,
                DocumentEdge.is_primary_parent.is_(True),
                DocumentEdge.deleted_at.is_(None),
            )
            .order_by(DocumentEdge.id.asc())
            .limit(1)
        )
        if exclude_edge_id is not None:
            query = query.where(DocumentEdge.id != exclude_edge_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _assert_no_second_primary_parent(
        self,
        *,
        tenant_id: int,
        child_document_id: int,
        exclude_edge_id: Optional[int] = None,
    ) -> None:
        existing_id = await self._find_other_primary_parent_edge_id(
            tenant_id=tenant_id,
            child_document_id=child_document_id,
            exclude_edge_id=exclude_edge_id,
        )
        if existing_id is not None:
            raise ConflictError(
                "Document already has a primary implements parent",
                code="DOCUMENT_GRAPH_SECOND_PRIMARY_PARENT",
                details={
                    "child_document_id": child_document_id,
                    "existing_edge_id": existing_id,
                },
            )

    @staticmethod
    def _duplicate_edge_error(
        *,
        edge_id: int,
        src_document_id: int,
        dst_document_id: int,
        edge_type: DocumentEdgeType,
    ) -> ConflictError:
        return ConflictError(
            "A live edge of this type already exists between these documents",
            code="DOCUMENT_GRAPH_EDGE_EXISTS",
            details={
                "edge_id": edge_id,
                "src_document_id": src_document_id,
                "dst_document_id": dst_document_id,
                "edge_type": edge_type.value,
            },
        )

    async def _documents_by_ids(
        self,
        *,
        tenant_id: int,
        document_ids: set[int],
    ) -> dict[int, Document]:
        if not document_ids:
            return {}
        result = await self.db.execute(
            select(Document).where(
                Document.tenant_id == tenant_id,
                Document.id.in_(document_ids),
            )
        )
        return {doc.id: doc for doc in result.scalars().all()}

    def _hop_payload(
        self,
        *,
        edge: DocumentEdge,
        document_id: int,
        depth: int,
        direction: str,
        doc: Optional[Any],
    ) -> dict:
        status_value = edge.status.value if isinstance(edge.status, DocumentEdgeStatus) else str(edge.status)
        return {
            "document_id": document_id,
            "edge_id": edge.id,
            "depth": depth,
            "direction": direction,
            "title": getattr(doc, "title", None) if doc is not None else None,
            "reference": _document_reference(doc),
            "href": document_href(document_id),
            "origin": THREAD_HOP_ORIGIN,
            "status": status_value,
        }

    async def _audit_edge_mutation(
        self,
        *,
        tenant_id: int,
        edge: DocumentEdge,
        action: str,
        actor_id: Optional[int],
        description: str,
        payload: Optional[dict] = None,
    ) -> None:
        await record_audit_event(
            db=self.db,
            event_type=f"document_graph.edge_{action}",
            entity_type="document_edge",
            entity_id=str(edge.id),
            entity_name=f"edge:{edge.id}",
            action=action,
            description=description,
            payload=payload
            or {
                "src_document_id": edge.src_document_id,
                "dst_document_id": edge.dst_document_id,
                "edge_type": (
                    edge.edge_type.value if isinstance(edge.edge_type, DocumentEdgeType) else str(edge.edge_type)
                ),
                "status": edge.status.value if isinstance(edge.status, DocumentEdgeStatus) else str(edge.status),
                "is_primary_parent": bool(edge.is_primary_parent),
            },
            user_id=actor_id,
            actor_user_id=actor_id,
            tenant_id=tenant_id,
        )

    async def would_create_implements_cycle(
        self,
        *,
        tenant_id: int,
        src_document_id: int,
        dst_document_id: int,
    ) -> bool:
        """True if adding implements(src→dst) would close a cycle.

        Graph direction: ``src`` implements ``dst`` (child → parent). A cycle
        exists if ``dst`` can already reach ``src`` by walking child→parent
        edges (or equivalently if ``src`` is already an ancestor of ``dst``
        via reverse: walking parent→children from ``dst`` eventually hits ``src``).
        """
        if src_document_id == dst_document_id:
            return True

        # Walk from dst toward ancestors (follow implements where src=current → dst=parent).
        # If we reach src, adding src→dst would cycle.
        frontier = [dst_document_id]
        seen: set[int] = {dst_document_id}
        while frontier:
            current = frontier.pop()
            result = await self.db.execute(
                select(DocumentEdge.dst_document_id).where(
                    DocumentEdge.tenant_id == tenant_id,
                    DocumentEdge.src_document_id == current,
                    DocumentEdge.edge_type == DocumentEdgeType.IMPLEMENTS,
                    DocumentEdge.status.in_(_ACTIVE_STATUSES),
                    DocumentEdge.deleted_at.is_(None),
                )
            )
            for parent_id in result.scalars().all():
                if parent_id == src_document_id:
                    return True
                if parent_id not in seen:
                    seen.add(parent_id)
                    frontier.append(parent_id)
        return False

    async def create_edge(
        self,
        *,
        tenant_id: int,
        src_document_id: int,
        dst_document_id: int,
        edge_type: DocumentEdgeType | str,
        actor_id: Optional[int] = None,
        is_primary_parent: bool = False,
        status: DocumentEdgeStatus | str | None = None,
        created_method: DocumentEdgeMethod | str = DocumentEdgeMethod.MANUAL,
        confidence: Optional[float] = None,
        rationale: Optional[str] = None,
        src_pel_doc_ref: Optional[str] = None,
        dst_pel_doc_ref: Optional[str] = None,
        cited_document_version_id: Optional[int] = None,
        chunk_id: Optional[int] = None,
        char_start: Optional[int] = None,
        char_end: Optional[int] = None,
        quote_hash: Optional[str] = None,
        citation_text: Optional[str] = None,
        cited_version: Optional[str] = None,
        commit: bool = True,
    ) -> DocumentEdge:
        edge_type_enum = _coerce_edge_type(edge_type)
        created_method = _coerce_created_method(created_method)
        status_enum = _coerce_edge_status(status)

        if is_primary_parent and edge_type_enum != DocumentEdgeType.IMPLEMENTS:
            raise ValidationError(
                "is_primary_parent is only valid for implements edges",
                code="DOCUMENT_GRAPH_PRIMARY_PARENT_TYPE",
            )

        if confidence is not None and not (0.0 <= confidence <= 1.0):
            raise ValidationError(
                "confidence must be between 0 and 1",
                code="DOCUMENT_GRAPH_INVALID_CONFIDENCE",
            )

        if (
            created_method in _NO_AUTO_CONFIRM_METHODS
            and edge_type_enum in IMPACT_DRIVING_EDGE_TYPES
            and status_enum == DocumentEdgeStatus.CONFIRMED
        ):
            raise ValidationError(
                "AI/heuristic must not auto-confirm impact-driving edges",
                code="DOCUMENT_GRAPH_HEURISTIC_NO_AUTO_CONFIRM",
                details={
                    "edge_type": edge_type_enum.value,
                    "created_method": created_method.value,
                },
            )

        src_document_id, dst_document_id = canonicalize_endpoints(edge_type_enum, src_document_id, dst_document_id)

        if src_document_id == dst_document_id:
            raise ValidationError(
                "src_document_id and dst_document_id must differ",
                code="DOCUMENT_GRAPH_SELF_LOOP",
            )

        src_doc = await self._get_document_or_404(tenant_id=tenant_id, document_id=src_document_id)
        dst_doc = await self._get_document_or_404(tenant_id=tenant_id, document_id=dst_document_id)

        # Refuse the duplicate here rather than letting the partial unique index
        # surface as a 500 on a route an operator can reach from the UI.
        duplicate_id = await self._find_live_edge_id(
            tenant_id=tenant_id,
            src_document_id=src_document_id,
            dst_document_id=dst_document_id,
            edge_type=edge_type_enum,
        )
        if duplicate_id is not None:
            raise self._duplicate_edge_error(
                edge_id=duplicate_id,
                src_document_id=src_document_id,
                dst_document_id=dst_document_id,
                edge_type=edge_type_enum,
            )

        if edge_type_enum == DocumentEdgeType.IMPLEMENTS:
            if await self.would_create_implements_cycle(
                tenant_id=tenant_id,
                src_document_id=src_document_id,
                dst_document_id=dst_document_id,
            ):
                raise ConflictError(
                    "implements edge would create a cycle",
                    code="DOCUMENT_GRAPH_IMPLEMENTS_CYCLE",
                    details={
                        "src_document_id": src_document_id,
                        "dst_document_id": dst_document_id,
                    },
                )
            if is_primary_parent:
                await self._assert_no_second_primary_parent(
                    tenant_id=tenant_id,
                    child_document_id=src_document_id,
                )

        confirmed_at: Optional[datetime] = None
        confirmed_by_id: Optional[int] = None
        if status_enum == DocumentEdgeStatus.CONFIRMED:
            confirmed_at = _as_utc()
            confirmed_by_id = actor_id

        edge = DocumentEdge(
            tenant_id=tenant_id,
            src_document_id=src_document_id,
            dst_document_id=dst_document_id,
            src_pel_doc_ref=src_pel_doc_ref or getattr(src_doc, "pel_doc_ref", None),
            dst_pel_doc_ref=dst_pel_doc_ref or getattr(dst_doc, "pel_doc_ref", None),
            edge_type=edge_type_enum,
            is_primary_parent=bool(is_primary_parent),
            status=status_enum,
            created_method=created_method,
            confidence=confidence,
            rationale=rationale,
            confirmed_by_id=confirmed_by_id,
            confirmed_at=confirmed_at,
            cited_document_version_id=cited_document_version_id,
            chunk_id=chunk_id,
            char_start=char_start,
            char_end=char_end,
            quote_hash=quote_hash,
            citation_text=citation_text,
            cited_version=cited_version,
        )
        self.db.add(edge)
        try:
            if commit:
                await self.db.commit()
                await self.db.refresh(edge)
            else:
                await self.db.flush()
        except IntegrityError as exc:
            # The pre-checks above close the ordinary case; a concurrent writer can
            # still win either unique slot. Roll back, then only claim a conflict if
            # one is actually there — other constraint violations must not be
            # mislabelled.
            await self.db.rollback()
            duplicate_id = await self._find_live_edge_id(
                tenant_id=tenant_id,
                src_document_id=src_document_id,
                dst_document_id=dst_document_id,
                edge_type=edge_type_enum,
            )
            if duplicate_id is not None:
                raise self._duplicate_edge_error(
                    edge_id=duplicate_id,
                    src_document_id=src_document_id,
                    dst_document_id=dst_document_id,
                    edge_type=edge_type_enum,
                ) from exc
            if is_primary_parent and edge_type_enum == DocumentEdgeType.IMPLEMENTS:
                existing_primary_id = await self._find_other_primary_parent_edge_id(
                    tenant_id=tenant_id,
                    child_document_id=src_document_id,
                )
                if existing_primary_id is not None:
                    raise ConflictError(
                        "Document already has a primary implements parent",
                        code="DOCUMENT_GRAPH_SECOND_PRIMARY_PARENT",
                        details={
                            "child_document_id": src_document_id,
                            "existing_edge_id": existing_primary_id,
                        },
                    ) from exc
            raise
        return edge

    async def list_edges(
        self,
        *,
        tenant_id: int,
        document_id: int,
        edge_type: Optional[DocumentEdgeType | str] = None,
        status: Optional[DocumentEdgeStatus | str] = None,
        include_deleted: bool = False,
    ) -> Sequence[DocumentEdge]:
        await self._get_document_or_404(tenant_id=tenant_id, document_id=document_id)

        query = select(DocumentEdge).where(
            DocumentEdge.tenant_id == tenant_id,
            or_(
                DocumentEdge.src_document_id == document_id,
                DocumentEdge.dst_document_id == document_id,
            ),
        )
        if not include_deleted:
            query = query.where(DocumentEdge.deleted_at.is_(None))
        if edge_type is not None:
            query = query.where(DocumentEdge.edge_type == _coerce_edge_type(edge_type))
        if status is not None:
            status_enum = status if isinstance(status, DocumentEdgeStatus) else DocumentEdgeStatus(str(status))
            query = query.where(DocumentEdge.status == status_enum)

        query = query.order_by(DocumentEdge.created_at.desc(), DocumentEdge.id.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def confirm(
        self,
        *,
        tenant_id: int,
        edge_id: int,
        actor_id: int,
        commit: bool = True,
    ) -> DocumentEdge:
        edge = await self._get_edge_or_404(tenant_id=tenant_id, edge_id=edge_id)
        if edge.status == DocumentEdgeStatus.REJECTED:
            raise ValidationError(
                "Cannot confirm a rejected edge",
                code="DOCUMENT_GRAPH_INVALID_TRANSITION",
            )
        if edge.is_primary_parent and edge.edge_type == DocumentEdgeType.IMPLEMENTS:
            await self._assert_no_second_primary_parent(
                tenant_id=tenant_id,
                child_document_id=edge.src_document_id,
                exclude_edge_id=edge.id,
            )
        previous_status = edge.status.value if isinstance(edge.status, DocumentEdgeStatus) else str(edge.status)
        edge.status = DocumentEdgeStatus.CONFIRMED
        edge.confirmed_by_id = actor_id
        edge.confirmed_at = _as_utc()
        await self._audit_edge_mutation(
            tenant_id=tenant_id,
            edge=edge,
            action="confirm",
            actor_id=actor_id,
            description=f"Confirmed document edge {edge.id}",
            payload={
                "previous_status": previous_status,
                "status": DocumentEdgeStatus.CONFIRMED.value,
                "src_document_id": edge.src_document_id,
                "dst_document_id": edge.dst_document_id,
                "edge_type": (
                    edge.edge_type.value if isinstance(edge.edge_type, DocumentEdgeType) else str(edge.edge_type)
                ),
                "is_primary_parent": bool(edge.is_primary_parent),
            },
        )
        if commit:
            await self.db.commit()
            await self.db.refresh(edge)
        else:
            await self.db.flush()
        return edge

    async def reject(
        self,
        *,
        tenant_id: int,
        edge_id: int,
        actor_id: Optional[int] = None,
        rationale: Optional[str] = None,
        commit: bool = True,
    ) -> DocumentEdge:
        edge = await self._get_edge_or_404(tenant_id=tenant_id, edge_id=edge_id)
        previous_status = edge.status.value if isinstance(edge.status, DocumentEdgeStatus) else str(edge.status)
        edge.status = DocumentEdgeStatus.REJECTED
        if rationale:
            note = f"Rejected: {rationale.strip()}"
            edge.rationale = f"{edge.rationale}\n{note}".strip() if edge.rationale else note
        # Reject clears confirmation provenance; actor is attributed via AuditLog.
        edge.confirmed_by_id = None
        edge.confirmed_at = None
        # Free the one-primary unique slot so a replacement primary can be created
        # without soft-deleting this rejected implements edge.
        if edge.is_primary_parent:
            edge.is_primary_parent = False
        await self._audit_edge_mutation(
            tenant_id=tenant_id,
            edge=edge,
            action="reject",
            actor_id=actor_id,
            description=f"Rejected document edge {edge.id}",
            payload={
                "previous_status": previous_status,
                "status": DocumentEdgeStatus.REJECTED.value,
                "src_document_id": edge.src_document_id,
                "dst_document_id": edge.dst_document_id,
                "edge_type": (
                    edge.edge_type.value if isinstance(edge.edge_type, DocumentEdgeType) else str(edge.edge_type)
                ),
                "rationale": rationale,
            },
        )
        if commit:
            await self.db.commit()
            await self.db.refresh(edge)
        else:
            await self.db.flush()
        return edge

    async def soft_delete(
        self,
        *,
        tenant_id: int,
        edge_id: int,
        actor_id: Optional[int] = None,
        commit: bool = True,
    ) -> DocumentEdge:
        edge = await self._get_edge_or_404(tenant_id=tenant_id, edge_id=edge_id)
        edge.deleted_at = _as_utc()
        await self._audit_edge_mutation(
            tenant_id=tenant_id,
            edge=edge,
            action="delete",
            actor_id=actor_id,
            description=f"Soft-deleted document edge {edge.id}",
            payload={
                "src_document_id": edge.src_document_id,
                "dst_document_id": edge.dst_document_id,
                "edge_type": (
                    edge.edge_type.value if isinstance(edge.edge_type, DocumentEdgeType) else str(edge.edge_type)
                ),
                "status": edge.status.value if isinstance(edge.status, DocumentEdgeStatus) else str(edge.status),
                "deleted_at": edge.deleted_at.isoformat() if edge.deleted_at else None,
            },
        )
        if commit:
            await self.db.commit()
            await self.db.refresh(edge)
        else:
            await self.db.flush()
        return edge

    async def get_thread(
        self,
        *,
        tenant_id: int,
        document_id: int,
        max_depth: int = THREAD_MAX_DEPTH,
        include_proposed: bool = False,
    ) -> dict:
        """Walk primary ``implements`` edges up (parents) and down (children).

        ``implements`` direction: src implements dst (child → parent). Primary
        parent links use ``is_primary_parent=True``. Depth is capped at
        ``THREAD_MAX_DEPTH`` (default 4).

        Ambient thread is confirmed-only unless ``include_proposed`` is true.
        Ancestor selection is deterministic (``order_by`` edge id ascending —
        never nondeterministic ``.first()``). Descendant walk is visited-set /
        cycle-safe so each node appears at most once.
        """
        await self._get_document_or_404(tenant_id=tenant_id, document_id=document_id)
        depth_cap = max(0, min(max_depth, THREAD_MAX_DEPTH))
        walk_statuses = thread_walk_statuses(include_proposed=include_proposed)

        raw_ancestors: list[tuple[DocumentEdge, int]] = []
        current = document_id
        seen_ancestors: set[int] = {document_id}
        for depth in range(1, depth_cap + 1):
            result = await self.db.execute(
                select(DocumentEdge)
                .where(
                    DocumentEdge.tenant_id == tenant_id,
                    DocumentEdge.src_document_id == current,
                    DocumentEdge.edge_type == DocumentEdgeType.IMPLEMENTS,
                    DocumentEdge.is_primary_parent.is_(True),
                    DocumentEdge.status.in_(walk_statuses),
                    DocumentEdge.deleted_at.is_(None),
                )
                .order_by(DocumentEdge.id.asc())
            )
            # Deterministic pick among legacy duplicate primaries.
            parent_edges = list(result.scalars().all())
            parent_edges.sort(key=lambda e: e.id)
            parent_edge = parent_edges[0] if parent_edges else None
            if parent_edge is None:
                break
            parent_id = parent_edge.dst_document_id
            if parent_id in seen_ancestors:
                break
            seen_ancestors.add(parent_id)
            raw_ancestors.append((parent_edge, depth))
            current = parent_id

        raw_descendants: list[tuple[DocumentEdge, int, int]] = []
        visited_descendants: set[int] = {document_id}

        async def _walk_children(parent_id: int, depth: int) -> None:
            if depth > depth_cap:
                return
            result = await self.db.execute(
                select(DocumentEdge)
                .where(
                    DocumentEdge.tenant_id == tenant_id,
                    DocumentEdge.dst_document_id == parent_id,
                    DocumentEdge.edge_type == DocumentEdgeType.IMPLEMENTS,
                    DocumentEdge.is_primary_parent.is_(True),
                    DocumentEdge.status.in_(walk_statuses),
                    DocumentEdge.deleted_at.is_(None),
                )
                .order_by(DocumentEdge.id.asc())
            )
            child_edges = list(result.scalars().all())
            child_edges.sort(key=lambda e: e.id)
            for child_edge in child_edges:
                child_id = child_edge.src_document_id
                if child_id in visited_descendants:
                    continue
                visited_descendants.add(child_id)
                raw_descendants.append((child_edge, child_id, depth))
                await _walk_children(child_id, depth + 1)

        await _walk_children(document_id, 1)

        needed_ids = {edge.dst_document_id for edge, _ in raw_ancestors} | {
            child_id for _, child_id, _ in raw_descendants
        }
        docs = await self._documents_by_ids(tenant_id=tenant_id, document_ids=needed_ids)

        ancestors = [
            self._hop_payload(
                edge=edge,
                document_id=edge.dst_document_id,
                depth=depth,
                direction="parent",
                doc=docs.get(edge.dst_document_id),
            )
            for edge, depth in raw_ancestors
        ]
        descendants = [
            self._hop_payload(
                edge=edge,
                document_id=child_id,
                depth=depth,
                direction="child",
                doc=docs.get(child_id),
            )
            for edge, child_id, depth in raw_descendants
        ]

        return {
            "document_id": document_id,
            "ancestors": ancestors,
            "descendants": descendants,
            "max_depth": depth_cap,
        }
