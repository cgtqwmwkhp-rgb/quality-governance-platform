"""Document Graph Entity360 producer — bidirectional on day one."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select

from src.domain.models.document import Document
from src.domain.models.document_graph import DocumentEdge, DocumentEdgeStatus, DocumentEdgeType
from src.domain.services.entity_360.types import HopDirection, ProducerResult, make_hop
from src.domain.services.href_registry import document_href


def _document_reference(doc: Optional[Document]) -> Optional[str]:
    if doc is None:
        return None
    pel = getattr(doc, "pel_doc_ref", None)
    if pel:
        return str(pel)
    ref = getattr(doc, "reference_number", None)
    return str(ref) if ref else None


class DocumentGraphProducer:
    """Emits upstream + downstream hops from live Doc Graph edges.

    Bidirectional registration contract: both lists are always present
    (may be empty). Origin is always ``graph``.
    """

    origin = "graph"

    def supports(self, entity_type: str) -> bool:
        return entity_type.strip().lower() == "document"

    async def produce(
        self,
        *,
        db: Any,
        tenant_id: int,
        entity_type: str,
        entity_id: int,
        user: Any,
    ) -> ProducerResult:
        _ = (entity_type, user)
        try:
            result = await db.execute(
                select(DocumentEdge).where(
                    DocumentEdge.tenant_id == tenant_id,
                    DocumentEdge.deleted_at.is_(None),
                    DocumentEdge.status != DocumentEdgeStatus.REJECTED,
                    (DocumentEdge.src_document_id == entity_id) | (DocumentEdge.dst_document_id == entity_id),
                )
            )
            edges: list[DocumentEdge] = list(result.scalars().all())
        except Exception as exc:  # noqa: BLE001 — producer isolation
            return ProducerResult(
                origin=self.origin,
                status="error",
                reason=f"document_graph: {exc}",
            )

        counterpart_ids = set()
        for edge in edges:
            if edge.src_document_id == entity_id:
                counterpart_ids.add(edge.dst_document_id)
            else:
                counterpart_ids.add(edge.src_document_id)

        docs: dict[int, Document] = {}
        if counterpart_ids:
            try:
                doc_result = await db.execute(
                    select(Document).where(
                        Document.tenant_id == tenant_id,
                        Document.id.in_(counterpart_ids),
                    )
                )
                docs = {d.id: d for d in doc_result.scalars().all()}
            except Exception as exc:  # noqa: BLE001
                return ProducerResult(
                    origin=self.origin,
                    status="error",
                    reason=f"document_graph docs: {exc}",
                )

        upstream: list[dict[str, Any]] = []
        downstream: list[dict[str, Any]] = []

        for edge in edges:
            edge_type = edge.edge_type.value if isinstance(edge.edge_type, DocumentEdgeType) else str(edge.edge_type)
            status_value = edge.status.value if isinstance(edge.status, DocumentEdgeStatus) else str(edge.status)
            confidence = getattr(edge, "confidence", None)
            version_pin = getattr(edge, "cited_document_version_id", None)

            if edge.src_document_id == entity_id:
                # src → dst: for implements, dst is parent (upstream); peers go upstream by convention
                other_id = edge.dst_document_id
                direction: HopDirection = "upstream"
                if edge_type == DocumentEdgeType.IMPLEMENTS.value or edge_type == "implements":
                    direction = "upstream"
                bucket = upstream
            else:
                # other → me: for implements, other is child (downstream)
                other_id = edge.src_document_id
                direction = "downstream"
                bucket = downstream

            doc = docs.get(other_id)
            hop = make_hop(
                source_type="document",
                source_id=other_id,
                title=getattr(doc, "title", None) if doc is not None else None,
                reference=_document_reference(doc),
                href=document_href(other_id),
                direction=direction,
                relation=edge_type,
                depth=1,
                origin="graph",
                status=status_value,
                confidence=float(confidence) if confidence is not None else None,
                edge_id=edge.id,
                version_pin=int(version_pin) if version_pin is not None else None,
            )
            bucket.append(hop)

        # Stable ordering for contract tests / UI
        upstream.sort(key=lambda h: (h.get("relation") or "", h.get("source_id") or 0))
        downstream.sort(key=lambda h: (h.get("relation") or "", h.get("source_id") or 0))

        return ProducerResult(
            origin=self.origin,
            status="ok",
            upstream=upstream,
            downstream=downstream,
        )


__all__ = ["DocumentGraphProducer"]
