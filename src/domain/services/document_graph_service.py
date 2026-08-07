"""Doc Graph domain service (ADR-0021 Wave 0).

create / list / confirm / reject / soft_delete / primary-implements thread walk,
plus cycle detection on ``implements``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import or_, select
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

THREAD_MAX_DEPTH = 4

# Statuses that participate in cycle / thread walks (rejected edges are inert).
_ACTIVE_STATUSES = (
    DocumentEdgeStatus.PROPOSED,
    DocumentEdgeStatus.CONFIRMED,
    DocumentEdgeStatus.NEEDS_REVIEW,
)


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


def canonicalize_endpoints(
    edge_type: DocumentEdgeType,
    src_document_id: int,
    dst_document_id: int,
) -> tuple[int, int]:
    """For undirected peer types, store ``src_id < dst_id`` canonically."""
    if edge_type in CANONICAL_UNDIRECTED_TYPES and src_document_id > dst_document_id:
        return dst_document_id, src_document_id
    return src_document_id, dst_document_id


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

        if isinstance(created_method, str):
            try:
                created_method = DocumentEdgeMethod(created_method)
            except ValueError as exc:
                raise ValidationError(
                    f"Unsupported created_method '{created_method}'",
                    code="DOCUMENT_GRAPH_INVALID_METHOD",
                ) from exc

        if status is None:
            status_enum = DocumentEdgeStatus.PROPOSED
        elif isinstance(status, DocumentEdgeStatus):
            status_enum = status
        else:
            try:
                status_enum = DocumentEdgeStatus(str(status))
            except ValueError as exc:
                raise ValidationError(
                    f"Unsupported status '{status}'",
                    code="DOCUMENT_GRAPH_INVALID_STATUS",
                ) from exc

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

        src_document_id, dst_document_id = canonicalize_endpoints(edge_type_enum, src_document_id, dst_document_id)

        if src_document_id == dst_document_id:
            raise ValidationError(
                "src_document_id and dst_document_id must differ",
                code="DOCUMENT_GRAPH_SELF_LOOP",
            )

        src_doc = await self._get_document_or_404(tenant_id=tenant_id, document_id=src_document_id)
        dst_doc = await self._get_document_or_404(tenant_id=tenant_id, document_id=dst_document_id)

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
        if commit:
            await self.db.commit()
            await self.db.refresh(edge)
        else:
            await self.db.flush()
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
        edge.status = DocumentEdgeStatus.CONFIRMED
        edge.confirmed_by_id = actor_id
        edge.confirmed_at = _as_utc()
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
        edge.status = DocumentEdgeStatus.REJECTED
        if rationale:
            note = f"Rejected: {rationale.strip()}"
            edge.rationale = f"{edge.rationale}\n{note}".strip() if edge.rationale else note
        # Reject clears confirmation provenance; actor is not stamped as confirmer.
        edge.confirmed_by_id = None
        edge.confirmed_at = None
        _ = actor_id  # reserved for future audit-log wiring
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
        commit: bool = True,
    ) -> DocumentEdge:
        edge = await self._get_edge_or_404(tenant_id=tenant_id, edge_id=edge_id)
        edge.deleted_at = _as_utc()
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
    ) -> dict:
        """Walk primary ``implements`` edges up (parents) and down (children).

        ``implements`` direction: src implements dst (child → parent). Primary
        parent links use ``is_primary_parent=True``. Depth is capped at
        ``THREAD_MAX_DEPTH`` (default 4).
        """
        await self._get_document_or_404(tenant_id=tenant_id, document_id=document_id)
        depth_cap = max(0, min(max_depth, THREAD_MAX_DEPTH))

        ancestors: list[dict] = []
        current = document_id
        for depth in range(1, depth_cap + 1):
            result = await self.db.execute(
                select(DocumentEdge).where(
                    DocumentEdge.tenant_id == tenant_id,
                    DocumentEdge.src_document_id == current,
                    DocumentEdge.edge_type == DocumentEdgeType.IMPLEMENTS,
                    DocumentEdge.is_primary_parent.is_(True),
                    DocumentEdge.status.in_(_ACTIVE_STATUSES),
                    DocumentEdge.deleted_at.is_(None),
                )
            )
            parent_edge = result.scalars().first()
            if parent_edge is None:
                break
            ancestors.append(
                {
                    "document_id": parent_edge.dst_document_id,
                    "edge_id": parent_edge.id,
                    "depth": depth,
                    "direction": "parent",
                }
            )
            current = parent_edge.dst_document_id

        descendants: list[dict] = []

        async def _walk_children(parent_id: int, depth: int) -> None:
            if depth > depth_cap:
                return
            result = await self.db.execute(
                select(DocumentEdge).where(
                    DocumentEdge.tenant_id == tenant_id,
                    DocumentEdge.dst_document_id == parent_id,
                    DocumentEdge.edge_type == DocumentEdgeType.IMPLEMENTS,
                    DocumentEdge.is_primary_parent.is_(True),
                    DocumentEdge.status.in_(_ACTIVE_STATUSES),
                    DocumentEdge.deleted_at.is_(None),
                )
            )
            for child_edge in result.scalars().all():
                descendants.append(
                    {
                        "document_id": child_edge.src_document_id,
                        "edge_id": child_edge.id,
                        "depth": depth,
                        "direction": "child",
                    }
                )
                await _walk_children(child_edge.src_document_id, depth + 1)

        await _walk_children(document_id, 1)

        return {
            "document_id": document_id,
            "ancestors": ancestors,
            "descendants": descendants,
            "max_depth": depth_cap,
        }
