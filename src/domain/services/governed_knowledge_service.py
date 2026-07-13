"""AI-first Governed Knowledge Bank service.

Maps documents to multi-scheme compliance evidence, reverse-scans standards
against the knowledge base, and logs all AI decisions for audit.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.compliance_evidence import (
    ComplianceEvidenceLink,
    EvidenceLinkMethod,
    EvidenceLinkStatus,
    EvidenceSignalType,
)
from src.domain.models.document import Document
from src.domain.models.governed_knowledge import AiDecisionLog, DocumentQuizDraft, QuizDraftStatus
from src.domain.models.standard import Clause, Standard
from src.domain.models.uvdb_achilles import UVDBQuestion, UVDBSection
from src.domain.services.document_ai_service import DocumentAIService, VectorSearchService
from src.domain.services.iso_compliance_service import iso_compliance_service

logger = logging.getLogger(__name__)

AUTO_CONFIRM_THRESHOLD = 0.85
STRICT_DOC_TYPES = frozenset({"rams", "coshh", "msds", "sds", "ram", "method_statement"})

# Operational cases must never auto-confirm as conformance evidence.
OPERATIONAL_ENTITY_TYPES = frozenset(
    {
        "incident",
        "complaint",
        "near_miss",
        "rta",
        "audit_finding",
    }
)

DEFAULT_SIGNAL_BY_ENTITY: dict[str, EvidenceSignalType] = {
    "incident": EvidenceSignalType.NONCONFORMITY,
    "complaint": EvidenceSignalType.NONCONFORMITY,
    "near_miss": EvidenceSignalType.GAP,
    "rta": EvidenceSignalType.NONCONFORMITY,
    "audit_finding": EvidenceSignalType.NONCONFORMITY,
    "document": EvidenceSignalType.EVIDENCE,
}

PLANET_MARK_THEMES: dict[str, list[str]] = {
    "pm:scope1": [
        "scope 1",
        "direct emissions",
        "fleet fuel",
        "gas combustion",
        "refrigerant",
        "company vehicles",
        "on-site fuel",
    ],
    "pm:scope2": [
        "scope 2",
        "purchased electricity",
        "grid electricity",
        "renewable tariff",
        "energy consumption",
    ],
    "pm:scope3": [
        "scope 3",
        "supply chain",
        "business travel",
        "employee commuting",
        "upstream",
        "downstream",
        "procurement emissions",
    ],
    "pm:reduction": [
        "carbon reduction",
        "emission reduction",
        "net zero",
        "decarbonisation",
        "decarbonization",
        "improvement target",
        "reduction plan",
        "carbon footprint reduction",
    ],
}


@dataclass
class SchemeMapping:
    clause_id: str
    scheme: str
    confidence: float
    rationale: str
    title: Optional[str] = None


@dataclass
class RelatedDocumentHit:
    document_id: int
    score: float
    title: Optional[str] = None


@dataclass
class OperationalAssessmentResult:
    entity_type: str
    entity_id: str
    signal_type: str
    links: list[ComplianceEvidenceLink]
    related_documents: list[RelatedDocumentHit]
    assessment_statement: Optional[str] = None
    stages_summary: Optional[dict[str, Any]] = None


def _normalize_confidence(confidence: Optional[float]) -> float:
    if confidence is None:
        return 0.0
    if confidence > 1.0:
        return confidence / 100.0
    return confidence


def resolve_link_status(
    confidence: Optional[float],
    doc_type: Optional[str],
    *,
    force_proposed: bool = False,
) -> tuple[EvidenceLinkStatus, bool]:
    """Return (status, auto_applied) using AI-first threshold rules."""
    if force_proposed:
        return EvidenceLinkStatus.PROPOSED, False
    norm = _normalize_confidence(confidence)
    doc_normalized = (doc_type or "").lower().replace("-", "_").replace(" ", "_")
    if doc_normalized in STRICT_DOC_TYPES or norm < AUTO_CONFIRM_THRESHOLD:
        return EvidenceLinkStatus.PROPOSED, False
    return EvidenceLinkStatus.CONFIRMED, True


def classify_operational_signal(
    entity_type: str,
    *,
    finding_type: Optional[str] = None,
    content: Optional[str] = None,
) -> EvidenceSignalType:
    """Classify how an operational record should treat matched clauses."""
    ft = (finding_type or "").lower().replace("-", "_").replace(" ", "_")
    if ft in {"opportunity", "ofi", "observation_positive", "good_practice"}:
        return EvidenceSignalType.OPPORTUNITY
    if ft in {"observation", "obs"}:
        return EvidenceSignalType.GAP
    if ft in {"conformity", "conformance", "positive", "evidence"}:
        return EvidenceSignalType.EVIDENCE
    if ft in {"nonconformity", "nc", "major_nc", "minor_nc"}:
        return EvidenceSignalType.NONCONFORMITY

    text = (content or "").lower()
    if any(token in text for token in ("opportunity for improvement", "ofi:", "best practice")):
        return EvidenceSignalType.OPPORTUNITY
    if any(token in text for token in ("gap in", "missing procedure", "no evidence of")):
        return EvidenceSignalType.GAP

    return DEFAULT_SIGNAL_BY_ENTITY.get(entity_type, EvidenceSignalType.NONCONFORMITY)


class GovernedKnowledgeService:
    """Orchestrates multi-scheme evidence mapping with AI-first defaults."""

    def __init__(self) -> None:
        self._ai_service = DocumentAIService()
        self._vector_service = VectorSearchService()

    async def _log_ai_decision(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        action: str,
        entity_type: str,
        entity_id: str,
        confidence: Optional[float],
        auto_applied: bool,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        db.add(
            AiDecisionLog(
                tenant_id=tenant_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                confidence=confidence,
                auto_applied=auto_applied,
                payload=payload,
            )
        )

    async def _persist_mapping(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        entity_type: str,
        entity_id: str,
        mapping: SchemeMapping,
        doc_type: Optional[str],
        user: Any,
        force_proposed: bool = False,
        signal_type: Optional[EvidenceSignalType] = None,
    ) -> ComplianceEvidenceLink:
        status, auto_applied = resolve_link_status(
            mapping.confidence,
            doc_type,
            force_proposed=force_proposed or entity_type in OPERATIONAL_ENTITY_TYPES,
        )

        existing_result = await db.execute(
            select(ComplianceEvidenceLink).where(
                ComplianceEvidenceLink.deleted_at.is_(None),
                ComplianceEvidenceLink.tenant_id == tenant_id,
                ComplianceEvidenceLink.entity_type == entity_type,
                ComplianceEvidenceLink.entity_id == entity_id,
                ComplianceEvidenceLink.clause_id == mapping.clause_id,
            )
        )
        link = existing_result.scalar_one_or_none()
        if link is None:
            link = ComplianceEvidenceLink(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                clause_id=mapping.clause_id,
                created_by_id=getattr(user, "id", None),
                created_by_email=getattr(user, "email", None),
            )
            db.add(link)

        link.scheme = mapping.scheme
        link.confidence = mapping.confidence
        link.rationale = mapping.rationale
        link.title = mapping.title
        link.status = status
        link.auto_applied = auto_applied
        link.linked_by = EvidenceLinkMethod.AI
        if signal_type is not None:
            link.signal_type = signal_type.value
        elif entity_type == "document" and not link.signal_type:
            link.signal_type = EvidenceSignalType.EVIDENCE.value

        await self._log_ai_decision(
            db,
            tenant_id=tenant_id,
            action="evidence_map",
            entity_type="compliance_evidence_link",
            entity_id=f"{entity_type}:{entity_id}:{mapping.clause_id}",
            confidence=mapping.confidence,
            auto_applied=auto_applied,
            payload={
                "scheme": mapping.scheme,
                "status": status.value,
                "rationale": mapping.rationale,
                "doc_type": doc_type,
                "signal_type": link.signal_type,
                "source_entity_type": entity_type,
            },
        )
        return link

    async def _map_iso_schemes(self, content: str) -> list[SchemeMapping]:
        mappings: list[SchemeMapping] = []
        try:
            results = await iso_compliance_service.ai_enhanced_tagging(content)
        except Exception:
            logger.exception("AI ISO tagging failed; falling back to keyword match")
            results = iso_compliance_service.auto_tag_content(content, min_confidence=0.3)

        for result in results:
            clause_id = result.get("clause_id")
            if not clause_id:
                continue
            standard = result.get("standard", "iso9001")
            mappings.append(
                SchemeMapping(
                    clause_id=clause_id,
                    scheme=standard,
                    confidence=float(result.get("confidence", 0)),
                    rationale=result.get("evidence_snippet") or result.get("title") or "ISO auto-tag match",
                    title=result.get("title"),
                )
            )
        return mappings

    async def _map_uvdb_schemes(
        self,
        db: AsyncSession,
        content: str,
        tenant_id: int,
    ) -> list[SchemeMapping]:
        mappings: list[SchemeMapping] = []
        content_lower = content.lower()

        query = (
            select(UVDBQuestion, UVDBSection)
            .join(UVDBSection, UVDBQuestion.section_id == UVDBSection.id)
            .where(
                or_(
                    UVDBQuestion.tenant_id.is_(None),
                    UVDBQuestion.tenant_id == tenant_id,
                )
            )
        )
        result = await db.execute(query)
        rows = result.all()

        for question, section in rows:
            score = 0.0
            hits: list[str] = []
            text_blob = f"{question.question_text} {section.section_title}".lower()
            keywords = re.findall(r"\b[a-z]{4,}\b", text_blob)
            unique_keywords = list(dict.fromkeys(keywords))[:12]

            for keyword in unique_keywords:
                if keyword in content_lower:
                    score += 0.08
                    hits.append(keyword)

            for indicator in question.positive_indicators or []:
                ind_lower = str(indicator).lower()
                if len(ind_lower) > 3 and ind_lower in content_lower:
                    score += 0.15
                    hits.append(ind_lower)

            if score >= 0.25:
                clause_id = f"uvdb:{question.question_number}"
                confidence = min(95.0, round(score * 100, 1))
                mappings.append(
                    SchemeMapping(
                        clause_id=clause_id,
                        scheme="uvdb",
                        confidence=confidence,
                        rationale=f"UVDB keyword match ({', '.join(hits[:5])})",
                        title=question.question_text[:300],
                    )
                )

        return mappings[:15]

    def _map_planet_mark_schemes(self, content: str) -> list[SchemeMapping]:
        mappings: list[SchemeMapping] = []
        content_lower = content.lower()

        for clause_id, keywords in PLANET_MARK_THEMES.items():
            hits = [kw for kw in keywords if kw in content_lower]
            if hits:
                confidence = min(92.0, 55.0 + len(hits) * 12.0)
                mappings.append(
                    SchemeMapping(
                        clause_id=clause_id,
                        scheme="planet_mark",
                        confidence=confidence,
                        rationale=f"Planet Mark theme match: {', '.join(hits[:4])}",
                        title=clause_id.replace("pm:", "Planet Mark ").replace("_", " ").title(),
                    )
                )
        return mappings

    async def map_document_to_schemes(
        self,
        db: AsyncSession,
        document_id: int,
        content: str,
        doc_type: Optional[str],
        tenant_id: int,
        user: Any,
    ) -> list[ComplianceEvidenceLink]:
        """Run ISO + UVDB + Planet Mark mapping and persist evidence links."""
        if not content or not content.strip():
            return []

        all_mappings: list[SchemeMapping] = []
        all_mappings.extend(await self._map_iso_schemes(content))
        all_mappings.extend(await self._map_uvdb_schemes(db, content, tenant_id))
        all_mappings.extend(self._map_planet_mark_schemes(content))

        links: list[ComplianceEvidenceLink] = []
        seen_clauses: set[str] = set()
        for mapping in all_mappings:
            if mapping.clause_id in seen_clauses:
                continue
            seen_clauses.add(mapping.clause_id)
            link = await self._persist_mapping(
                db,
                tenant_id=tenant_id,
                entity_type="document",
                entity_id=str(document_id),
                mapping=mapping,
                doc_type=doc_type,
                user=user,
                signal_type=EvidenceSignalType.EVIDENCE,
            )
            links.append(link)

        logger.info(
            "governed_kb.map_document document_id=%s tenant=%s links=%s",
            document_id,
            tenant_id,
            len(links),
        )
        return links

    async def scan_standard_against_kb(
        self,
        db: AsyncSession,
        *,
        standard_id: Optional[int] = None,
        clause_texts: Optional[list[str]] = None,
        tenant_id: int,
        user: Any,
    ) -> list[ComplianceEvidenceLink]:
        """Reverse-scan: find KB documents matching standard clauses."""
        queries: list[str] = []
        scheme = "custom"

        if standard_id is not None:
            std_result = await db.execute(select(Standard).where(Standard.id == standard_id))
            standard = std_result.scalar_one_or_none()
            if standard is None:
                return []

            clause_result = await db.execute(
                select(Clause).where(Clause.standard_id == standard_id, Clause.is_active.is_(True))
            )
            clauses = list(clause_result.scalars().all())
            for clause in clauses:
                queries.append(f"{clause.title} {clause.description or ''}".strip())

            code_lower = (standard.code or "").lower()
            if "9001" in code_lower:
                scheme = "iso9001"
            elif "14001" in code_lower:
                scheme = "iso14001"
            elif "45001" in code_lower:
                scheme = "iso45001"
            elif "27001" in code_lower:
                scheme = "iso27001"

        if clause_texts:
            queries.extend(clause_texts)

        if not queries:
            return []

        links: list[ComplianceEvidenceLink] = []
        for query_text in queries[:20]:
            doc_matches = await self._find_documents_for_query(db, query_text, tenant_id)
            for doc_id, score in doc_matches:
                mapping = SchemeMapping(
                    clause_id=f"scan:{standard_id or 'custom'}:{doc_id}",
                    scheme=scheme,
                    confidence=score,
                    rationale=f"KB reverse-scan match for: {query_text[:120]}",
                    title=query_text[:300],
                )
                link = await self._persist_mapping(
                    db,
                    tenant_id=tenant_id,
                    entity_type="document",
                    entity_id=str(doc_id),
                    mapping=mapping,
                    doc_type=None,
                    user=user,
                    signal_type=EvidenceSignalType.EVIDENCE,
                )
                links.append(link)

        return links

    async def assess_operational_entity(
        self,
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: str,
        content: str,
        tenant_id: int,
        user: Any,
        finding_type: Optional[str] = None,
        include_related_documents: bool = True,
    ) -> OperationalAssessmentResult:
        """Assess an operational case against standards with signal typing.

        Unlike document mapping, operational assessments:
        - Never auto-confirm (always proposed → Exceptions inbox)
        - Classify signal_type (nonconformity / gap / opportunity / evidence)
        - Optionally attach related Knowledge Bank documents
        - Capture a multi-stage assessment statement when AI is available
        """
        if entity_type not in OPERATIONAL_ENTITY_TYPES:
            raise ValueError(f"Unsupported operational entity_type: {entity_type}")
        if not content or not content.strip():
            return OperationalAssessmentResult(
                entity_type=entity_type,
                entity_id=entity_id,
                signal_type=DEFAULT_SIGNAL_BY_ENTITY[entity_type].value,
                links=[],
                related_documents=[],
            )

        signal = classify_operational_signal(
            entity_type,
            finding_type=finding_type,
            content=content,
        )

        assessment_statement: Optional[str] = None
        stages_summary: Optional[dict[str, Any]] = None
        try:
            analysis = await iso_compliance_service.multi_stage_analyze(content)
            stages = analysis.get("stages") or {}
            stages_summary = {
                "clause_count": len(analysis.get("clause_matches") or []),
                "cross_standard": (stages.get("stage_3_cross_standard") or {}).get("cross_standard_matches", [])[:5],
            }
            stage5 = stages.get("stage_5_conformance") or {}
            assessment_statement = stage5.get("conformance_statement")
            if assessment_statement and signal != EvidenceSignalType.EVIDENCE:
                # Re-frame auditor language for operational signals.
                assessment_statement = (
                    f"[{signal.value.upper()}] Assessment of {entity_type} {entity_id}: " f"{assessment_statement}"
                )
        except Exception:
            logger.exception(
                "multi_stage_analyze failed for %s:%s; continuing with tagging",
                entity_type,
                entity_id,
            )

        all_mappings: list[SchemeMapping] = []
        all_mappings.extend(await self._map_iso_schemes(content))
        # UVDB / Planet Mark are scheme-specific; keep ISO primary for ops cases.
        if entity_type == "complaint":
            all_mappings.extend(await self._map_uvdb_schemes(db, content, tenant_id))

        links: list[ComplianceEvidenceLink] = []
        seen_clauses: set[str] = set()
        for mapping in all_mappings:
            if mapping.clause_id in seen_clauses:
                continue
            seen_clauses.add(mapping.clause_id)
            if assessment_statement and not mapping.rationale:
                mapping.rationale = assessment_statement[:500]
            link = await self._persist_mapping(
                db,
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=str(entity_id),
                mapping=mapping,
                doc_type=None,
                user=user,
                force_proposed=True,
                signal_type=signal,
            )
            if assessment_statement:
                link.notes = assessment_statement[:2000]
            links.append(link)

        related_documents: list[RelatedDocumentHit] = []
        if include_related_documents:
            doc_matches = await self._find_documents_for_query(db, content[:500], tenant_id)
            doc_ids = [doc_id for doc_id, _ in doc_matches[:5]]
            titles: dict[int, str] = {}
            if doc_ids:
                title_result = await db.execute(select(Document.id, Document.title).where(Document.id.in_(doc_ids)))
                titles = {row[0]: row[1] for row in title_result.all()}
            for doc_id, score in doc_matches[:5]:
                related_documents.append(
                    RelatedDocumentHit(
                        document_id=doc_id,
                        score=score,
                        title=titles.get(doc_id),
                    )
                )

        await self._log_ai_decision(
            db,
            tenant_id=tenant_id,
            action="operational_standards_assess",
            entity_type=entity_type,
            entity_id=str(entity_id),
            confidence=max((link.confidence or 0.0) for link in links) if links else None,
            auto_applied=False,
            payload={
                "signal_type": signal.value,
                "links": len(links),
                "related_documents": [hit.document_id for hit in related_documents],
                "has_assessment_statement": bool(assessment_statement),
            },
        )

        logger.info(
            "governed_kb.assess_operational entity=%s:%s tenant=%s signal=%s links=%s related=%s",
            entity_type,
            entity_id,
            tenant_id,
            signal.value,
            len(links),
            len(related_documents),
        )
        return OperationalAssessmentResult(
            entity_type=entity_type,
            entity_id=str(entity_id),
            signal_type=signal.value,
            links=links,
            related_documents=related_documents,
            assessment_statement=assessment_statement,
            stages_summary=stages_summary,
        )

    async def list_entity_assessment_links(
        self,
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: str,
        tenant_id: int,
    ) -> list[ComplianceEvidenceLink]:
        result = await db.execute(
            select(ComplianceEvidenceLink)
            .where(
                ComplianceEvidenceLink.deleted_at.is_(None),
                ComplianceEvidenceLink.tenant_id == tenant_id,
                ComplianceEvidenceLink.entity_type == entity_type,
                ComplianceEvidenceLink.entity_id == str(entity_id),
            )
            .order_by(ComplianceEvidenceLink.created_at.desc())
        )
        return list(result.scalars().all())

    async def _find_documents_for_query(
        self,
        db: AsyncSession,
        query_text: str,
        tenant_id: int,
    ) -> list[tuple[int, float]]:
        """Semantic search via Pinecone when available, else ILIKE on Document."""
        matches: list[tuple[int, float]] = []

        vector_results = await self._vector_service.search(
            query_text,
            top_k=5,
            filter_dict={"tenant_id": tenant_id},
        )
        if vector_results:
            for hit in vector_results:
                metadata = hit.get("metadata") or {}
                doc_id = metadata.get("document_id")
                if doc_id is not None:
                    score = float(hit.get("score", 0)) * 100
                    matches.append((int(doc_id), score))
            return matches

        pattern = f"%{query_text[:80]}%"
        result = await db.execute(
            select(Document.id)
            .where(
                Document.tenant_id == tenant_id,
                or_(
                    Document.title.ilike(pattern),
                    Document.description.ilike(pattern),
                    Document.ai_summary.ilike(pattern),
                ),
            )
            .limit(5)
        )
        for doc_id in result.scalars().all():
            matches.append((doc_id, 60.0))
        return matches

    async def rematch_evidence_on_version(
        self,
        db: AsyncSession,
        document_id: int,
        content: str,
        doc_type: Optional[str],
        tenant_id: int,
        user: Any,
    ) -> list[ComplianceEvidenceLink]:
        """Flag prior confirmed links as needs_review when confidence drops; re-map."""
        entity_id = str(document_id)
        existing_result = await db.execute(
            select(ComplianceEvidenceLink).where(
                ComplianceEvidenceLink.deleted_at.is_(None),
                ComplianceEvidenceLink.tenant_id == tenant_id,
                ComplianceEvidenceLink.entity_type == "document",
                ComplianceEvidenceLink.entity_id == entity_id,
            )
        )
        existing_links = list(existing_result.scalars().all())

        fresh_mappings = await self.map_document_to_schemes(db, document_id, content, doc_type, tenant_id, user)
        fresh_by_clause = {link.clause_id: link for link in fresh_mappings}

        for old_link in existing_links:
            if old_link.effective_status != EvidenceLinkStatus.CONFIRMED:
                continue
            fresh = fresh_by_clause.get(old_link.clause_id)
            if fresh is None:
                old_link.status = EvidenceLinkStatus.NEEDS_REVIEW
                old_link.rationale = (old_link.rationale or "") + " | No longer matched on re-version"
                await self._log_ai_decision(
                    db,
                    tenant_id=tenant_id,
                    action="evidence_rematch_missing",
                    entity_type="compliance_evidence_link",
                    entity_id=str(old_link.id),
                    confidence=0.0,
                    auto_applied=False,
                    payload={"document_id": document_id, "clause_id": old_link.clause_id},
                )
                continue

            old_conf = _normalize_confidence(old_link.confidence)
            new_conf = _normalize_confidence(fresh.confidence)
            if new_conf < old_conf or new_conf < AUTO_CONFIRM_THRESHOLD:
                old_link.status = EvidenceLinkStatus.NEEDS_REVIEW
                old_link.rationale = f"Confidence dropped from {old_conf:.2f} to {new_conf:.2f} on document re-version"
                await self._log_ai_decision(
                    db,
                    tenant_id=tenant_id,
                    action="evidence_rematch_confidence_drop",
                    entity_type="compliance_evidence_link",
                    entity_id=str(old_link.id),
                    confidence=fresh.confidence,
                    auto_applied=False,
                    payload={
                        "document_id": document_id,
                        "clause_id": old_link.clause_id,
                        "old_confidence": old_conf,
                        "new_confidence": new_conf,
                    },
                )

        return fresh_mappings

    async def generate_quiz_draft(
        self,
        db: AsyncSession,
        *,
        document_id: int,
        content: str,
        version: str,
        tenant_id: int,
        user: Any,
        question_count: int = 5,
        include_open: bool = True,
        include_mcq: bool = True,
        pass_mark: int = 70,
        auto_approve_if_quality: bool = False,
    ) -> DocumentQuizDraft:
        """Generate quiz questions via DocumentAIService (Claude Sonnet 4)."""
        prompt_types = []
        if include_mcq:
            prompt_types.append("multiple_choice")
        if include_open:
            prompt_types.append("open_ended")

        prompt = f"""Generate {question_count} comprehension quiz questions from this document.
Question types: {', '.join(prompt_types) or 'multiple_choice'}.
Return JSON array only:
[{{"type": "mcq|open", "question": "...", "options": ["A","B","C","D"], "correct_answer": "...", "explanation": "..."}}]

DOCUMENT:
{content[:12000]}"""

        questions: list[dict[str, Any]] = []
        quality_score = 0.0

        if self._ai_service.api_key:
            try:
                import httpx

                from src.domain.services.upstream_circuit_breaker import call_via_upstream_breaker

                async def _do_call() -> dict:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            "https://api.anthropic.com/v1/messages",
                            headers={
                                "x-api-key": self._ai_service.api_key,
                                "anthropic-version": "2023-06-01",
                                "content-type": "application/json",
                            },
                            json={
                                "model": self._ai_service.model,
                                "max_tokens": 4096,
                                "system": "You are a compliance training quiz author. Return valid JSON only.",
                                "messages": [{"role": "user", "content": prompt}],
                            },
                            timeout=90.0,
                        )
                        response.raise_for_status()
                        return response.json()

                data = await call_via_upstream_breaker("document_ai", _do_call)
                text = data.get("content", [{}])[0].get("text", "[]")
                match = re.search(r"\[[\s\S]*\]", text)
                if match:
                    questions = json.loads(match.group())
                    quality_score = min(1.0, len(questions) / max(question_count, 1))
            except Exception:
                logger.exception("Quiz generation via DocumentAIService failed")

        if not questions:
            questions = [
                {
                    "type": "open",
                    "question": "Summarise the key compliance requirements in this document.",
                    "correct_answer": "See document summary.",
                    "explanation": "Fallback question — AI unavailable.",
                }
            ]

        status = QuizDraftStatus.DRAFT
        if auto_approve_if_quality and quality_score >= 0.85 and len(questions) >= question_count:
            status = QuizDraftStatus.APPROVED

        draft = DocumentQuizDraft(
            tenant_id=tenant_id,
            document_id=document_id,
            version=version,
            questions=questions,
            pass_mark=pass_mark,
            status=status,
            created_by_id=getattr(user, "id", 0),
        )
        db.add(draft)

        await self._log_ai_decision(
            db,
            tenant_id=tenant_id,
            action="quiz_generate",
            entity_type="document_quiz_draft",
            entity_id=str(document_id),
            confidence=quality_score * 100,
            auto_applied=status == QuizDraftStatus.APPROVED,
            payload={"question_count": len(questions), "pass_mark": pass_mark},
        )
        return draft

    async def draft_discussion_reply(
        self,
        thread_context: str,
        user_prompt: str,
    ) -> str:
        """Optional AI draft for discussion messages."""
        if not self._ai_service.api_key:
            return user_prompt

        try:
            import httpx

            from src.domain.services.upstream_circuit_breaker import call_via_upstream_breaker

            async def _do_call() -> dict:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": self._ai_service.api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": self._ai_service.model,
                            "max_tokens": 1024,
                            "system": "Draft a concise, professional reply for a document governance discussion.",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": f"Thread context:\n{thread_context}\n\nUser request:\n{user_prompt}",
                                }
                            ],
                        },
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    return response.json()

            data = await call_via_upstream_breaker("document_ai", _do_call)
            return data.get("content", [{}])[0].get("text", user_prompt)
        except Exception:
            logger.exception("Discussion AI draft failed")
            return user_prompt

    async def mark_quizzes_stale_for_document(
        self,
        db: AsyncSession,
        *,
        document_id: int,
        tenant_id: int,
        new_version: str,
    ) -> int:
        """Mark approved/draft quizzes as stale when a new controlled version is published."""
        result = await db.execute(
            select(DocumentQuizDraft).where(
                DocumentQuizDraft.tenant_id == tenant_id,
                DocumentQuizDraft.document_id == document_id,
                DocumentQuizDraft.status.in_([QuizDraftStatus.DRAFT, QuizDraftStatus.APPROVED]),
            )
        )
        drafts = list(result.scalars().all())
        for draft in drafts:
            draft.status = QuizDraftStatus.STALE
        if drafts:
            await self._log_ai_decision(
                db,
                tenant_id=tenant_id,
                action="quiz_marked_stale",
                entity_type="document",
                entity_id=str(document_id),
                confidence=None,
                auto_applied=True,
                payload={"new_version": new_version, "stale_count": len(drafts)},
            )
        return len(drafts)


governed_knowledge_service = GovernedKnowledgeService()
