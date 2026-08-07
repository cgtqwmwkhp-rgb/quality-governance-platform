"""Doc Graph Wave 1 — heuristic / regex / vector edge proposals (ADR-0021).

Gated by ``document_graph_heuristic_propose_enabled``. Proposals only:
``auto_applied=False`` on ``AiDecisionLog``; never auto-confirm impact-driving
edges (``implements``, ``requires_record``, ``conflicts_with``). Heuristics in
this wave emit ``related_to`` and ``references`` only — never ``conflicts_with``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkStatus
from src.domain.models.document import Document, DocumentChunk, DocumentVersion
from src.domain.models.document_graph import DocumentEdge, DocumentEdgeMethod, DocumentEdgeStatus, DocumentEdgeType
from src.domain.models.governed_knowledge import AiDecisionLog
from src.domain.services.document_graph_citation import (
    CitationStaleness,
    compute_quote_hash,
    evaluate_citation_staleness,
    extract_citation_matches,
)
from src.domain.services.document_graph_service import DocumentGraphService, canonicalize_endpoints

logger = logging.getLogger(__name__)

IMPACT_DRIVING_EDGE_TYPES = frozenset(
    {
        DocumentEdgeType.IMPLEMENTS,
        DocumentEdgeType.REQUIRES_RECORD,
        DocumentEdgeType.CONFLICTS_WITH,
    }
)

DEFAULT_MAX_PROPOSALS = 25
RELATED_CONFIDENCE_CATEGORY = 0.55
RELATED_CONFIDENCE_PEL = 0.60
RELATED_CONFIDENCE_CEL = 0.65
RELATED_CONFIDENCE_VECTOR_FLOOR = 0.50
RELATED_CONFIDENCE_ILIKE = 0.52
REFERENCES_CONFIDENCE = 0.90


@dataclass
class HeuristicProposeResult:
    created: list[DocumentEdge] = field(default_factory=list)
    skipped_existing: int = 0
    skipped_unresolved: int = 0
    sources: dict[str, int] = field(default_factory=dict)


class DocumentGraphHeuristicProposeService:
    """Non-LLM relationship proposals for a library document."""

    def __init__(self, db: AsyncSession, graph: Optional[DocumentGraphService] = None):
        self.db = db
        self.graph = graph or DocumentGraphService(db)

    async def propose_for_document(
        self,
        *,
        tenant_id: int,
        document_id: int,
        actor_id: Optional[int] = None,
        max_proposals: int = DEFAULT_MAX_PROPOSALS,
        commit: bool = True,
    ) -> HeuristicProposeResult:
        source = await self.graph._get_document_or_404(tenant_id=tenant_id, document_id=document_id)
        result = HeuristicProposeResult()
        seen_pairs: set[tuple[int, int, DocumentEdgeType]] = set()

        async def _try_create(
            *,
            dst_id: int,
            edge_type: DocumentEdgeType,
            method: DocumentEdgeMethod,
            confidence: float,
            rationale: str,
            source_key: str,
            citation_kwargs: Optional[dict[str, Any]] = None,
        ) -> None:
            if len(result.created) >= max_proposals:
                return
            if dst_id == document_id:
                return
            src_id, canon_dst = canonicalize_endpoints(edge_type, document_id, dst_id)
            # For directed types we keep src = this document (outbound citation /
            # relatedness from the document being proposed for). Undirected types
            # are canonicalized above.
            if edge_type not in (
                DocumentEdgeType.RELATED_TO,
                DocumentEdgeType.CONFLICTS_WITH,
            ):
                src_id, canon_dst = document_id, dst_id

            key = (src_id, canon_dst, edge_type)
            if key in seen_pairs:
                return
            seen_pairs.add(key)

            if edge_type in IMPACT_DRIVING_EDGE_TYPES:
                # Wave 1 heuristics must not invent impact-driving edges.
                return

            live_id = await self.graph._find_live_edge_id(
                tenant_id=tenant_id,
                src_document_id=src_id,
                dst_document_id=canon_dst,
                edge_type=edge_type,
            )
            if live_id is not None:
                result.skipped_existing += 1
                return

            citation_kwargs = citation_kwargs or {}
            try:
                edge = await self.graph.create_edge(
                    tenant_id=tenant_id,
                    src_document_id=src_id,
                    dst_document_id=canon_dst,
                    edge_type=edge_type,
                    actor_id=actor_id,
                    status=DocumentEdgeStatus.PROPOSED,
                    created_method=method,
                    confidence=confidence,
                    rationale=rationale,
                    commit=False,
                    **citation_kwargs,
                )
            except Exception:
                logger.exception(
                    "doc_graph.heuristic_propose create failed src=%s dst=%s type=%s",
                    src_id,
                    canon_dst,
                    edge_type.value,
                )
                return

            # Integrity: never leave a heuristic/AI impact edge confirmed.
            if (
                edge.created_method
                in (DocumentEdgeMethod.HEURISTIC, DocumentEdgeMethod.AI, DocumentEdgeMethod.EXTRACTED)
                and edge.edge_type in IMPACT_DRIVING_EDGE_TYPES
                and edge.status == DocumentEdgeStatus.CONFIRMED
            ):
                edge.status = DocumentEdgeStatus.PROPOSED
                edge.confirmed_at = None
                edge.confirmed_by_id = None

            result.created.append(edge)
            result.sources[source_key] = result.sources.get(source_key, 0) + 1

        # --- 1) Category / PEL siblings → related_to ---
        for sibling_id, conf, why in await self._category_and_pel_siblings(source, tenant_id=tenant_id):
            await _try_create(
                dst_id=sibling_id,
                edge_type=DocumentEdgeType.RELATED_TO,
                method=DocumentEdgeMethod.HEURISTIC,
                confidence=conf,
                rationale=why,
                source_key="category_pel_siblings",
            )

        # --- 2) Shared confirmed CEL clause_id → related_to ---
        for peer_id, conf, why in await self._shared_cel_peers(document_id, tenant_id=tenant_id):
            await _try_create(
                dst_id=peer_id,
                edge_type=DocumentEdgeType.RELATED_TO,
                method=DocumentEdgeMethod.HEURISTIC,
                confidence=conf,
                rationale=why,
                source_key="shared_cel",
            )

        # --- 3) Vector / ILIKE related_to ---
        for peer_id, conf, why in await self._vector_or_ilike_peers(source, tenant_id=tenant_id):
            await _try_create(
                dst_id=peer_id,
                edge_type=DocumentEdgeType.RELATED_TO,
                method=DocumentEdgeMethod.HEURISTIC,
                confidence=conf,
                rationale=why,
                source_key="vector_ilike",
            )

        # --- 4) Regex citations from chunks → references + quote_hash ---
        for proposal in await self._regex_citation_proposals(source, tenant_id=tenant_id):
            await _try_create(
                dst_id=proposal["dst_document_id"],
                edge_type=DocumentEdgeType.REFERENCES,
                method=DocumentEdgeMethod.EXTRACTED,
                confidence=REFERENCES_CONFIDENCE,
                rationale=proposal["rationale"],
                source_key="regex_citations",
                citation_kwargs={
                    "cited_document_version_id": proposal.get("cited_document_version_id"),
                    "chunk_id": proposal.get("chunk_id"),
                    "char_start": proposal.get("char_start"),
                    "char_end": proposal.get("char_end"),
                    "quote_hash": proposal.get("quote_hash"),
                    "citation_text": proposal.get("citation_text"),
                    "cited_version": proposal.get("cited_version"),
                },
            )

        # Flush so created edges have ids before the decision log payload.
        await self.db.flush()
        await self._log_decision(
            tenant_id=tenant_id,
            document_id=document_id,
            result=result,
        )

        if commit:
            await self.db.commit()
            for edge in result.created:
                await self.db.refresh(edge)
        else:
            await self.db.flush()

        return result

    async def citation_staleness_for_edge(
        self,
        *,
        tenant_id: int,
        edge_id: int,
    ) -> dict[str, Any]:
        edge = await self.graph._get_edge_or_404(tenant_id=tenant_id, edge_id=edge_id)
        chunk_content: Optional[str] = None
        if edge.chunk_id is not None:
            result = await self.db.execute(
                select(DocumentChunk.content).where(
                    DocumentChunk.id == edge.chunk_id,
                    DocumentChunk.tenant_id == tenant_id,
                )
            )
            chunk_content = result.scalar_one_or_none()

        status = evaluate_citation_staleness(
            quote_hash=edge.quote_hash,
            citation_text=edge.citation_text,
            char_start=edge.char_start,
            char_end=edge.char_end,
            chunk_content=chunk_content,
        )
        return {
            "edge_id": edge.id,
            "status": status.value,
            "quote_hash": edge.quote_hash,
            "chunk_id": edge.chunk_id,
            "char_start": edge.char_start,
            "char_end": edge.char_end,
        }

    async def _category_and_pel_siblings(
        self,
        source: Document,
        *,
        tenant_id: int,
    ) -> list[tuple[int, float, str]]:
        out: list[tuple[int, float, str]] = []
        clauses = []
        if source.category_id is not None:
            clauses.append(Document.category_id == source.category_id)
        elif source.category:
            clauses.append(Document.category == source.category)

        if clauses:
            result = await self.db.execute(
                select(Document.id)
                .where(
                    Document.tenant_id == tenant_id,
                    Document.id != source.id,
                    or_(*clauses),
                )
                .limit(10)
            )
            for doc_id in result.scalars().all():
                out.append(
                    (
                        int(doc_id),
                        RELATED_CONFIDENCE_CATEGORY,
                        "Same library category as source document",
                    )
                )

        if source.pel_doc_ref:
            prefix = _pel_family_prefix(source.pel_doc_ref)
            if prefix:
                pattern = f"{prefix}-%"
                result = await self.db.execute(
                    select(Document.id)
                    .where(
                        Document.tenant_id == tenant_id,
                        Document.id != source.id,
                        Document.pel_doc_ref.ilike(pattern),
                    )
                    .limit(10)
                )
                for doc_id in result.scalars().all():
                    out.append(
                        (
                            int(doc_id),
                            RELATED_CONFIDENCE_PEL,
                            f"PEL sibling under {prefix}",
                        )
                    )
        return out

    async def _shared_cel_peers(
        self,
        document_id: int,
        *,
        tenant_id: int,
    ) -> list[tuple[int, float, str]]:
        clause_result = await self.db.execute(
            select(ComplianceEvidenceLink.clause_id).where(
                ComplianceEvidenceLink.tenant_id == tenant_id,
                ComplianceEvidenceLink.entity_type == "document",
                ComplianceEvidenceLink.entity_id == str(document_id),
                ComplianceEvidenceLink.deleted_at.is_(None),
                or_(
                    ComplianceEvidenceLink.status == EvidenceLinkStatus.CONFIRMED,
                    ComplianceEvidenceLink.status.is_(None),
                ),
            )
        )
        clause_ids = {c for c in clause_result.scalars().all() if c}
        if not clause_ids:
            return []

        peer_result = await self.db.execute(
            select(ComplianceEvidenceLink.entity_id, ComplianceEvidenceLink.clause_id).where(
                ComplianceEvidenceLink.tenant_id == tenant_id,
                ComplianceEvidenceLink.entity_type == "document",
                ComplianceEvidenceLink.entity_id != str(document_id),
                ComplianceEvidenceLink.clause_id.in_(clause_ids),
                ComplianceEvidenceLink.deleted_at.is_(None),
                or_(
                    ComplianceEvidenceLink.status == EvidenceLinkStatus.CONFIRMED,
                    ComplianceEvidenceLink.status.is_(None),
                ),
            )
        )
        out: list[tuple[int, float, str]] = []
        seen: set[int] = set()
        for entity_id, clause_id in peer_result.all():
            try:
                peer_id = int(entity_id)
            except (TypeError, ValueError):
                continue
            if peer_id in seen:
                continue
            seen.add(peer_id)
            out.append(
                (
                    peer_id,
                    RELATED_CONFIDENCE_CEL,
                    f"Shares confirmed CEL clause {clause_id}",
                )
            )
            if len(out) >= 10:
                break
        return out

    async def _vector_or_ilike_peers(
        self,
        source: Document,
        *,
        tenant_id: int,
    ) -> list[tuple[int, float, str]]:
        query_text = (source.title or "").strip()
        if source.ai_summary:
            query_text = f"{query_text} {(source.ai_summary or '')[:200]}".strip()
        if not query_text:
            return []

        matches: list[tuple[int, float, str]] = []

        try:
            from src.domain.services.document_ai_service import VectorSearchService

            vector_service = VectorSearchService()
            vector_results = await vector_service.search(
                query_text[:500],
                top_k=5,
                filter_dict={"tenant_id": tenant_id},
            )
        except Exception:
            logger.exception("doc_graph.heuristic_propose vector search failed; falling back to ILIKE")
            vector_results = []

        if vector_results:
            raw: list[tuple[int, float]] = []
            for hit in vector_results:
                metadata = hit.get("metadata") or {}
                doc_id = metadata.get("document_id")
                if doc_id is None:
                    continue
                score = float(hit.get("score", 0.0))
                # Pinecone scores are typically 0..1; clamp into confidence band.
                confidence = max(RELATED_CONFIDENCE_VECTOR_FLOOR, min(0.85, score))
                raw.append((int(doc_id), confidence))
            live = await self._drop_orphaned(raw, tenant_id=tenant_id)
            for doc_id, conf in live:
                if doc_id == source.id:
                    continue
                matches.append((doc_id, conf, "Vector similarity to title/summary"))
            if matches:
                return matches[:5]

        # ILIKE fallback on title tokens
        token = (source.title or "")[:40].strip()
        if len(token) < 3:
            return []
        pattern = f"%{token}%"
        result = await self.db.execute(
            select(Document.id)
            .where(
                Document.tenant_id == tenant_id,
                Document.id != source.id,
                or_(
                    Document.title.ilike(pattern),
                    Document.description.ilike(pattern),
                    Document.ai_summary.ilike(pattern),
                ),
            )
            .limit(5)
        )
        for doc_id in result.scalars().all():
            matches.append(
                (
                    int(doc_id),
                    RELATED_CONFIDENCE_ILIKE,
                    "Title/description ILIKE overlap with source",
                )
            )
        return matches

    async def _regex_citation_proposals(
        self,
        source: Document,
        *,
        tenant_id: int,
    ) -> list[dict[str, Any]]:
        chunk_result = await self.db.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.document_id == source.id,
            )
            .order_by(DocumentChunk.chunk_index)
            .limit(50)
        )
        chunks: Sequence[DocumentChunk] = list(chunk_result.scalars().all())
        if not chunks:
            return []

        # Resolve DOC / PEL refs in one pass.
        doc_refs: set[str] = set()
        pel_refs: set[str] = set()
        path_ids: set[int] = set()
        staged: list[tuple[DocumentChunk, Any]] = []
        for chunk in chunks:
            for match in extract_citation_matches(chunk.content or ""):
                staged.append((chunk, match))
                if match.kind == "doc_ref" and match.resolved_reference:
                    doc_refs.add(match.resolved_reference.upper())
                elif match.kind == "pel_ref" and match.resolved_reference:
                    pel_refs.add(match.resolved_reference.upper())
                elif match.kind == "document_path" and match.resolved_document_id:
                    path_ids.add(match.resolved_document_id)

        ref_to_id: dict[str, int] = {}
        if doc_refs:
            result = await self.db.execute(
                select(Document.id, Document.reference_number).where(
                    Document.tenant_id == tenant_id,
                    Document.reference_number.in_(list(doc_refs)),
                )
            )
            for doc_id, ref in result.all():
                if ref:
                    ref_to_id[str(ref).upper()] = int(doc_id)

        pel_to_id: dict[str, int] = {}
        if pel_refs:
            result = await self.db.execute(
                select(Document.id, Document.pel_doc_ref).where(
                    Document.tenant_id == tenant_id,
                    Document.pel_doc_ref.in_(list(pel_refs)),
                )
            )
            for doc_id, pel in result.all():
                if pel:
                    pel_to_id[str(pel).upper()] = int(doc_id)

        live_path_ids: set[int] = set()
        if path_ids:
            result = await self.db.execute(
                select(Document.id).where(
                    Document.tenant_id == tenant_id,
                    Document.id.in_(path_ids),
                )
            )
            live_path_ids = set(int(i) for i in result.scalars().all())

        # Tip version numbers for cited targets (best-effort).
        target_ids = set(ref_to_id.values()) | set(pel_to_id.values()) | live_path_ids
        tip_version: dict[int, tuple[int, str]] = {}
        if target_ids:
            result = await self.db.execute(
                select(DocumentVersion.id, DocumentVersion.document_id, DocumentVersion.version_number)
                .where(
                    DocumentVersion.tenant_id == tenant_id,
                    DocumentVersion.document_id.in_(target_ids),
                )
                .order_by(DocumentVersion.id.desc())
            )
            for version_id, doc_id, version_number in result.all():
                if int(doc_id) not in tip_version:
                    tip_version[int(doc_id)] = (int(version_id), str(version_number))

        proposals: list[dict[str, Any]] = []
        seen_dst: set[int] = set()
        for chunk, match in staged:
            dst_id: Optional[int] = None
            if match.kind == "doc_ref" and match.resolved_reference:
                dst_id = ref_to_id.get(match.resolved_reference.upper())
            elif match.kind == "pel_ref" and match.resolved_reference:
                dst_id = pel_to_id.get(match.resolved_reference.upper())
            elif match.kind == "document_path" and match.resolved_document_id:
                if match.resolved_document_id in live_path_ids:
                    dst_id = match.resolved_document_id

            if dst_id is None or dst_id == source.id or dst_id in seen_dst:
                continue
            seen_dst.add(dst_id)

            span = (chunk.content or "")[match.char_start : match.char_end]
            tip = tip_version.get(dst_id)
            proposals.append(
                {
                    "dst_document_id": dst_id,
                    "rationale": f"Extracted citation {match.raw!r} from document chunk",
                    "chunk_id": chunk.id,
                    "char_start": match.char_start,
                    "char_end": match.char_end,
                    "quote_hash": compute_quote_hash(span),
                    "citation_text": span,
                    "cited_document_version_id": tip[0] if tip else None,
                    "cited_version": tip[1] if tip else None,
                }
            )
            if len(proposals) >= 15:
                break
        return proposals

    async def _drop_orphaned(
        self,
        matches: list[tuple[int, float]],
        *,
        tenant_id: int,
    ) -> list[tuple[int, float]]:
        if not matches:
            return matches
        result = await self.db.execute(
            select(Document.id).where(
                Document.id.in_({doc_id for doc_id, _ in matches}),
                Document.tenant_id == tenant_id,
            )
        )
        live = set(result.scalars().all())
        return [(doc_id, score) for doc_id, score in matches if doc_id in live]

    async def _log_decision(
        self,
        *,
        tenant_id: int,
        document_id: int,
        result: HeuristicProposeResult,
    ) -> None:
        max_conf = None
        if result.created:
            confidences = [e.confidence for e in result.created if e.confidence is not None]
            if confidences:
                max_conf = max(confidences)

        self.db.add(
            AiDecisionLog(
                tenant_id=tenant_id,
                action="document_graph_heuristic_propose",
                entity_type="document",
                entity_id=str(document_id),
                confidence=max_conf,
                auto_applied=False,
                payload={
                    "created_edge_ids": [e.id for e in result.created if e.id is not None],
                    "created_count": len(result.created),
                    "skipped_existing": result.skipped_existing,
                    "skipped_unresolved": result.skipped_unresolved,
                    "sources": result.sources,
                    "edge_types": sorted({e.edge_type.value for e in result.created}),
                },
            )
        )


def _pel_family_prefix(pel_doc_ref: str) -> Optional[str]:
    """``PEL-IMS-POL-0001`` → ``PEL-IMS-POL`` (drop terminal sequence)."""
    parts = [p for p in (pel_doc_ref or "").split("-") if p]
    if len(parts) < 3:
        return None
    return "-".join(parts[:-1]).upper()


def assert_heuristic_not_auto_confirmed(edge: DocumentEdge) -> None:
    """Test/helper guard: impact-driving heuristic edges must stay proposed."""
    if (
        edge.created_method in (DocumentEdgeMethod.HEURISTIC, DocumentEdgeMethod.AI)
        and edge.edge_type in IMPACT_DRIVING_EDGE_TYPES
        and edge.status == DocumentEdgeStatus.CONFIRMED
    ):
        raise AssertionError("heuristic/AI must not auto-confirm impact-driving edges")


__all__ = [
    "CitationStaleness",
    "DEFAULT_MAX_PROPOSALS",
    "DocumentGraphHeuristicProposeService",
    "HeuristicProposeResult",
    "IMPACT_DRIVING_EDGE_TYPES",
    "assert_heuristic_not_auto_confirmed",
]
