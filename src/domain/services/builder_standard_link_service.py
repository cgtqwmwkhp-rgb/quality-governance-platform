"""Builder multi-scheme standard-link suggest + confirm persist (MAP-01..04).

Persists accepted/rejected links on AuditQuestion.assessor_guidance_json
(no Alembic) and optionally mirrors confirmed links into ComplianceEvidenceLink
for the shared confirm/reject audit spine.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditQuestion, AuditTemplate
from src.domain.models.compliance_evidence import (
    ComplianceEvidenceLink,
    EvidenceLinkMethod,
    EvidenceLinkStatus,
    EvidenceSignalType,
)
from src.domain.models.governed_knowledge import AiDecisionLog
from src.domain.services.governed_knowledge_service import (
    GovernedKnowledgeService,
    SchemeMapping,
)

logger = logging.getLogger(__name__)

STANDARD_LINKS_KEY = "map_standard_links"
LIBRARY_VERSION_KEY = "map_library_version"
DEFAULT_LIBRARY_VERSION = "builder-map-v1"

SchemeName = Literal["ISO", "Planet Mark", "UVDB"]
LinkDecision = Literal["accept", "edit", "reject"]

SCHEME_ALIASES: dict[str, SchemeName] = {
    "iso": "ISO",
    "iso9001": "ISO",
    "iso14001": "ISO",
    "iso45001": "ISO",
    "iso27001": "ISO",
    "planet_mark": "Planet Mark",
    "planet mark": "Planet Mark",
    "uvdb": "UVDB",
    "achilles": "UVDB",
}


def normalize_scheme(raw: str | None) -> SchemeName:
    key = (raw or "").strip().lower().replace("-", "_")
    if key in SCHEME_ALIASES:
        return SCHEME_ALIASES[key]
    if "planet" in key:
        return "Planet Mark"
    if "uvdb" in key or "achilles" in key:
        return "UVDB"
    return "ISO"


def _guidance_dict(question: AuditQuestion) -> dict[str, Any]:
    raw = question.assessor_guidance_json
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def read_standard_links(question: AuditQuestion) -> list[dict[str, Any]]:
    guidance = _guidance_dict(question)
    links = guidance.get(STANDARD_LINKS_KEY) or []
    if not isinstance(links, list):
        return []
    return [link for link in links if isinstance(link, dict)]


def write_standard_links(
    question: AuditQuestion,
    links: list[dict[str, Any]],
    *,
    library_version: str = DEFAULT_LIBRARY_VERSION,
) -> dict[str, Any]:
    guidance = _guidance_dict(question)
    guidance[STANDARD_LINKS_KEY] = links
    guidance[LIBRARY_VERSION_KEY] = library_version
    question.assessor_guidance_json = guidance
    # Keep ISO free-text / regulatory_reference in sync with primary accepted ISO link.
    accepted_iso = next(
        (
            link
            for link in links
            if link.get("status") == "accepted" and normalize_scheme(str(link.get("scheme"))) == "ISO"
        ),
        None,
    )
    if accepted_iso:
        ref = str(accepted_iso.get("refId") or accepted_iso.get("ref_id") or "").strip()
        label = str(accepted_iso.get("label") or "").strip()
        if ref:
            question.regulatory_reference = ref[:200]
        if label and not question.guidance_notes:
            question.guidance_notes = label[:500]
    return guidance


def compute_coverage_from_questions(questions: list[AuditQuestion]) -> dict[str, Any]:
    total = len(questions)
    with_accepted = 0
    accepted_links = 0
    by_scheme: dict[str, int] = {"ISO": 0, "Planet Mark": 0, "UVDB": 0}
    for question in questions:
        links = read_standard_links(question)
        accepted = [link for link in links if link.get("status") == "accepted"]
        if accepted:
            with_accepted += 1
        accepted_links += len(accepted)
        for link in accepted:
            scheme = normalize_scheme(str(link.get("scheme")))
            by_scheme[scheme] = by_scheme.get(scheme, 0) + 1
    percent = 0 if total == 0 else round((with_accepted / total) * 100)
    return {
        "total_questions": total,
        "questions_with_accepted_links": with_accepted,
        "accepted_multi_scheme_links": accepted_links,
        "coverage_percent": percent,
        "by_scheme": by_scheme,
        "assist_map_live": True,
        "library_version": DEFAULT_LIBRARY_VERSION,
    }


class BuilderStandardLinkService:
    """Suggest + confirm-loop persist for Audit / Inspection / Competency builders."""

    def __init__(self, knowledge: GovernedKnowledgeService | None = None) -> None:
        self._knowledge = knowledge or GovernedKnowledgeService()

    async def suggest_for_questions(
        self,
        db: AsyncSession,
        *,
        questions: list[dict[str, Any]],
        schemes: list[str] | None,
        tenant_id: int,
        library_version: str = DEFAULT_LIBRARY_VERSION,
    ) -> list[dict[str, Any]]:
        wanted = {normalize_scheme(s) for s in (schemes or ["ISO", "Planet Mark", "UVDB"])}
        suggestions: list[dict[str, Any]] = []

        for item in questions:
            question_id = str(item.get("question_id") or item.get("id") or "").strip()
            text = str(item.get("question_text") or item.get("text") or "").strip()
            description = str(item.get("description") or "").strip()
            if not question_id or not text:
                continue
            content = f"{text}\n{description}".strip()
            mappings: list[SchemeMapping] = []
            if "ISO" in wanted:
                mappings.extend(await self._knowledge._map_iso_schemes(content))
            if "UVDB" in wanted:
                mappings.extend(await self._knowledge._map_uvdb_schemes(db, content, tenant_id))
            if "Planet Mark" in wanted:
                mappings.extend(self._knowledge._map_planet_mark_schemes(content))

            # Rank + cap per question.
            mappings.sort(key=lambda m: m.confidence, reverse=True)
            seen: set[str] = set()
            for mapping in mappings:
                scheme = normalize_scheme(mapping.scheme)
                if scheme not in wanted:
                    continue
                dedupe = f"{scheme}:{mapping.clause_id}"
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                confidence = mapping.confidence
                if confidence > 1.0:
                    confidence = confidence / 100.0
                if confidence < 0.35:
                    continue
                suggestions.append(
                    {
                        "id": f"sug_{uuid.uuid4().hex[:12]}",
                        "questionId": question_id,
                        "scheme": scheme,
                        "refId": mapping.clause_id,
                        "label": mapping.title or mapping.clause_id,
                        "confidence": round(confidence, 3),
                        "status": "suggested",
                        "rationale": mapping.rationale,
                        "libraryVersion": library_version,
                    }
                )
                if len(seen) >= 6:
                    break
        return suggestions

    async def decide_link(
        self,
        db: AsyncSession,
        *,
        question_id: int,
        tenant_id: int,
        user: Any,
        decision: LinkDecision,
        link: dict[str, Any],
        edited_ref_id: str | None = None,
        edited_label: str | None = None,
        rationale: str | None = None,
    ) -> dict[str, Any]:
        question = await self._get_question(db, question_id, tenant_id)
        links = read_standard_links(question)
        link_id = str(link.get("id") or "").strip() or f"link_{uuid.uuid4().hex[:10]}"
        scheme = normalize_scheme(str(link.get("scheme")))
        ref_id = str(edited_ref_id or link.get("refId") or link.get("ref_id") or "").strip()
        label = str(edited_label or link.get("label") or ref_id).strip()
        if not ref_id:
            raise ValueError("refId is required for standard-link decisions")

        status = {
            "accept": "accepted",
            "edit": "accepted",
            "reject": "rejected",
        }[decision]

        existing_idx = next(
            (
                idx
                for idx, row in enumerate(links)
                if str(row.get("id")) == link_id
                or (
                    normalize_scheme(str(row.get("scheme"))) == scheme
                    and str(row.get("refId") or row.get("ref_id")) == ref_id
                )
            ),
            None,
        )
        payload = {
            "id": link_id if existing_idx is None else str(links[existing_idx].get("id") or link_id),
            "questionId": str(question_id),
            "scheme": scheme,
            "refId": ref_id,
            "label": label,
            "confidence": float(link.get("confidence") or 0),
            "status": status,
            "sourceFingerprint": str(link.get("sourceFingerprint") or ""),
            "libraryVersion": str(link.get("libraryVersion") or DEFAULT_LIBRARY_VERSION),
            "rationale": rationale or link.get("rationale"),
        }
        if existing_idx is None:
            links.append(payload)
        else:
            links[existing_idx] = {**links[existing_idx], **payload}

        write_standard_links(question, links)
        evidence_link = await self._mirror_evidence_link(
            db,
            question=question,
            tenant_id=tenant_id,
            user=user,
            link=payload,
            decision=decision,
            rationale=rationale,
        )
        db.add(
            AiDecisionLog(
                tenant_id=tenant_id,
                action=f"builder_standard_link_{decision}",
                entity_type="audit_question",
                entity_id=str(question_id),
                confidence=payload["confidence"],
                auto_applied=False,
                payload={
                    "link_id": payload["id"],
                    "scheme": scheme,
                    "ref_id": ref_id,
                    "status": status,
                    "evidence_link_id": getattr(evidence_link, "id", None),
                    "actor_email": getattr(user, "email", None),
                    "actor_id": getattr(user, "id", None),
                    "rationale": rationale,
                },
            )
        )
        await db.flush()
        return {
            "question_id": question_id,
            "link": payload,
            "links": links,
            "evidence_link_id": getattr(evidence_link, "id", None),
            "coverage": compute_coverage_from_questions([question]),
        }

    async def template_coverage(
        self,
        db: AsyncSession,
        *,
        template_id: int,
        tenant_id: int,
    ) -> dict[str, Any]:
        template = await db.scalar(select(AuditTemplate).where(AuditTemplate.id == template_id))
        if template is None:
            raise ValueError(f"Template {template_id} not found")
        if template.tenant_id is not None and template.tenant_id != tenant_id:
            raise ValueError(f"Template {template_id} not found")

        result = await db.execute(
            select(AuditQuestion).where(
                AuditQuestion.template_id == template_id,
                AuditQuestion.is_active.is_(True),
            )
        )
        questions = list(result.scalars().all())
        coverage = compute_coverage_from_questions(questions)
        coverage["template_id"] = template_id
        return coverage

    async def _get_question(
        self,
        db: AsyncSession,
        question_id: int,
        tenant_id: int,
    ) -> AuditQuestion:
        question = await db.scalar(select(AuditQuestion).where(AuditQuestion.id == question_id))
        if question is None:
            raise ValueError(f"Question {question_id} not found")
        template = await db.scalar(select(AuditTemplate).where(AuditTemplate.id == question.template_id))
        if template is None:
            raise ValueError(f"Question {question_id} not found")
        if template.tenant_id is not None and template.tenant_id != tenant_id:
            raise ValueError(f"Question {question_id} not found")
        return question

    async def _mirror_evidence_link(
        self,
        db: AsyncSession,
        *,
        question: AuditQuestion,
        tenant_id: int,
        user: Any,
        link: dict[str, Any],
        decision: LinkDecision,
        rationale: str | None,
    ) -> Optional[ComplianceEvidenceLink]:
        """Mirror builder decisions onto ComplianceEvidenceLink for shared confirm spine."""
        clause_id = str(link.get("refId") or "")[:50]
        if not clause_id:
            return None
        existing = await db.scalar(
            select(ComplianceEvidenceLink).where(
                ComplianceEvidenceLink.deleted_at.is_(None),
                ComplianceEvidenceLink.tenant_id == tenant_id,
                ComplianceEvidenceLink.entity_type == "audit_question",
                ComplianceEvidenceLink.entity_id == str(question.id),
                ComplianceEvidenceLink.clause_id == clause_id,
            )
        )
        if existing is None:
            existing = ComplianceEvidenceLink(
                tenant_id=tenant_id,
                entity_type="audit_question",
                entity_id=str(question.id),
                clause_id=clause_id,
                created_by_id=getattr(user, "id", None),
                created_by_email=getattr(user, "email", None),
            )
            db.add(existing)

        existing.scheme = normalize_scheme(str(link.get("scheme"))).lower().replace(" ", "_")
        existing.confidence = float(link.get("confidence") or 0)
        if existing.confidence <= 1.0:
            existing.confidence = existing.confidence * 100.0
        existing.title = str(link.get("label") or "")[:300] or None
        existing.rationale = str(link.get("rationale") or rationale or "")[:2000] or None
        existing.linked_by = EvidenceLinkMethod.AI
        existing.signal_type = EvidenceSignalType.EVIDENCE.value
        existing.auto_applied = False
        if decision == "reject":
            existing.status = EvidenceLinkStatus.REJECTED
            if rationale:
                note = f"Rejected: {rationale}"
                existing.notes = f"{existing.notes}\n{note}".strip() if existing.notes else note
        else:
            existing.status = EvidenceLinkStatus.CONFIRMED
        return existing


builder_standard_link_service = BuilderStandardLinkService()
