"""AI + deterministic regulatory-basis suggestions for Compliance Schedule.

Propose → confirm only: this service never mutates a requirement. Accept happens
in the form submit path via ``regulatory_standard_id`` / ``regulatory_clause_id``.

Identifier safety: the model may re-rank and write rationale; ``standard_id`` and
``clause_ids`` are always re-resolved from our own Standards catalogue / UK map.
An invented code is capped below the confidence threshold so it cannot skip
clarification as a confident top answer.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.domain.data.uk_regulatory_basis_map import (
    lookup_by_code,
    match_uk_regulations,
)
from src.domain.models.governed_knowledge import AiDecisionLog
from src.domain.models.standard import Clause, Standard
from src.domain.services.ai_models import AIConfig, get_ai_client
from src.domain.services.upstream_circuit_breaker import call_via_upstream_breaker

logger = logging.getLogger(__name__)

DEFAULT_CONFIDENCE_THRESHOLD = 0.7
AI_BREAKER_NAME = "document_ai"
MAX_CANDIDATES = 5
MIN_CLARIFY_QUESTIONS = 2
MAX_CLARIFY_QUESTIONS = 4
AI_ONLY_CONFIDENCE_CAP = 0.65

AI_UNCONFIGURED_NOTICE = (
    "AI suggestions are not configured in this environment. These matches come from "
    "the standards catalogue and the built-in UK regulation list only."
)
AI_UNAVAILABLE_NOTICE = (
    "The AI service could not be reached, so these matches come from the standards "
    "catalogue and the built-in UK regulation list only."
)
NO_MATCH_NOTICE = (
    "No regulation or standard could be matched from the title and description. " "Enter the regulatory basis by hand."
)

_SOURCE_STANDARDS = "standards_catalogue"
_SOURCE_CURATED = "curated_uk_map"
_SOURCE_AI = "ai"


@dataclass(frozen=True)
class RegulatoryCandidate:
    label: str
    regulation_or_standard_code: str
    standard_id: Optional[int]
    clause_ids: tuple[int, ...]
    confidence: float
    rationale: str
    source: str


@dataclass(frozen=True)
class ClarifyingQuestion:
    id: str
    question: str
    options: tuple[str, ...]
    why: str


@dataclass(frozen=True)
class RegulatorySuggestion:
    candidates: tuple[RegulatoryCandidate, ...]
    needs_clarification: bool
    clarifying_questions: tuple[ClarifyingQuestion, ...]
    confidence_threshold: float
    ai_available: bool
    notice: Optional[str]


class ComplianceScheduleRegulatoryAiService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def suggest(
        self,
        *,
        tenant_id: int,
        title: str,
        taxonomy_id: str,
        description: Optional[str],
        statutory: bool,
        answers: Optional[Mapping[str, str]] = None,
        requirement_id: Optional[int] = None,
    ) -> RegulatorySuggestion:
        threshold = self._threshold()
        text = self._compose_context(title, description, answers)
        answered_ids = frozenset((answers or {}).keys())

        db_hits = await self._match_db_standards(tenant_id, text)
        curated_hits = self._match_curated(text, taxonomy_id=taxonomy_id, statutory=statutory)
        merged = self._reconcile(db_hits, curated_hits)

        ai_available = self._ai_is_configured()
        notice: Optional[str] = None
        ai_invoked = False

        if ai_available:
            try:
                ai_candidates, ai_questions = await self._rank_with_ai(
                    text=text,
                    shortlist=merged,
                    taxonomy_id=taxonomy_id,
                    statutory=statutory,
                    answered_ids=answered_ids,
                )
                ai_invoked = True
                merged = self._merge_with_ai(merged, ai_candidates)
            except Exception:
                logger.exception("regulatory_basis AI ranking failed; using deterministic matches")
                ai_available = False
                notice = AI_UNAVAILABLE_NOTICE
        else:
            notice = AI_UNCONFIGURED_NOTICE

        candidates = self._dedupe_rank(merged)[:MAX_CANDIDATES]
        top_confidence = candidates[0].confidence if candidates else 0.0
        needs_clarification = bool(candidates) and top_confidence < threshold

        questions: tuple[ClarifyingQuestion, ...] = ()
        if needs_clarification:
            bank = self._clarifying_questions(text, taxonomy_id, answered_ids)
            if len(bank) >= MIN_CLARIFY_QUESTIONS:
                questions = bank[:MAX_CLARIFY_QUESTIONS]
            else:
                # Exhausted bank with still-low confidence: stop the loop.
                needs_clarification = False
                if not candidates:
                    notice = NO_MATCH_NOTICE
                elif notice is None:
                    notice = NO_MATCH_NOTICE

        if not candidates and not needs_clarification:
            notice = NO_MATCH_NOTICE

        if ai_invoked:
            await self._log_decision(
                tenant_id=tenant_id,
                requirement_id=requirement_id,
                top_confidence=top_confidence,
                candidate_count=len(candidates),
            )

        return RegulatorySuggestion(
            candidates=tuple(candidates),
            needs_clarification=needs_clarification,
            clarifying_questions=questions,
            confidence_threshold=threshold,
            ai_available=ai_available,
            notice=notice,
        )

    def _threshold(self) -> float:
        raw = getattr(
            settings,
            "compliance_schedule_regulatory_ai_confidence_threshold",
            DEFAULT_CONFIDENCE_THRESHOLD,
        )
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = DEFAULT_CONFIDENCE_THRESHOLD
        return max(0.1, min(0.99, value))

    @staticmethod
    def _ai_is_configured() -> bool:
        cfg = AIConfig.from_env()
        return bool(cfg.anthropic_api_key or cfg.openai_api_key or cfg.genspark_api_key)

    @staticmethod
    def _compose_context(
        title: str,
        description: Optional[str],
        answers: Optional[Mapping[str, str]],
    ) -> str:
        parts = [title or ""]
        if description:
            parts.append(description)
        if answers:
            for qid, answer in answers.items():
                parts.append(f"{qid}: {answer}")
        return " ".join(parts)

    async def _match_db_standards(self, tenant_id: int, text: str) -> list[RegulatoryCandidate]:
        normalised = text.lower()
        result = await self.db.execute(
            select(Standard).where(
                Standard.is_active.is_(True),
                or_(Standard.tenant_id.is_(None), Standard.tenant_id == tenant_id),
            )
        )
        standards = list(result.scalars().all())
        hits: list[RegulatoryCandidate] = []
        for standard in standards:
            score = self._score_standard(standard, normalised)
            if score < 0.5:
                continue
            clause_ids = await self._match_clauses(standard.id, normalised)
            hits.append(
                RegulatoryCandidate(
                    label=(standard.full_name or standard.name)[:255],
                    regulation_or_standard_code=standard.code,
                    standard_id=standard.id,
                    clause_ids=tuple(clause_ids),
                    confidence=round(score, 3),
                    rationale=f"Matched standards catalogue entry {standard.code}.",
                    source=_SOURCE_STANDARDS,
                )
            )
        return hits

    @staticmethod
    def _score_standard(standard: Standard, text: str) -> float:
        code = (standard.code or "").lower()
        name = (standard.name or "").lower()
        full = (standard.full_name or "").lower()
        if code and code.lower() in text.replace(" ", ""):
            return 0.9
        # ISO 45001 style mentions
        digits = re.sub(r"[^0-9]", "", code)
        if digits and len(digits) >= 4 and digits in re.sub(r"[^0-9]", "", text):
            return 0.88
        for hay in (name, full):
            if hay and hay in text:
                return 0.85
            tokens = [t for t in re.split(r"\W+", hay) if len(t) > 3]
            if tokens:
                overlap = sum(1 for t in tokens if t in text) / len(tokens)
                if overlap >= 0.6:
                    return 0.55 + overlap * 0.3
        return 0.0

    async def _match_clauses(self, standard_id: int, text: str) -> list[int]:
        result = await self.db.execute(
            select(Clause).where(
                Clause.standard_id == standard_id,
                Clause.is_active.is_(True),
            )
        )
        scored: list[tuple[float, int]] = []
        for clause in result.scalars().all():
            title = (clause.title or "").lower()
            number = (clause.clause_number or "").lower()
            score = 0.0
            if number and number in text:
                score = 0.8
            else:
                tokens = [t for t in re.split(r"\W+", title) if len(t) > 3]
                if tokens:
                    overlap = sum(1 for t in tokens if t in text) / len(tokens)
                    if overlap >= 0.4:
                        score = 0.4 + overlap * 0.4
            if score >= 0.4:
                scored.append((score, clause.id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [cid for _, cid in scored[:3]]

    def _match_curated(
        self,
        text: str,
        *,
        taxonomy_id: str,
        statutory: bool,
    ) -> list[RegulatoryCandidate]:
        hits: list[RegulatoryCandidate] = []
        for entry, score in match_uk_regulations(text, taxonomy_id=taxonomy_id, statutory=statutory, min_score=0.5):
            hits.append(
                RegulatoryCandidate(
                    label=entry.label[:255],
                    regulation_or_standard_code=entry.code,
                    standard_id=None,
                    clause_ids=(),
                    confidence=score,
                    rationale=f"Matched curated UK regulation map ({entry.code}).",
                    source=_SOURCE_CURATED,
                )
            )
        return hits

    async def _resolve_code(
        self, code: str, *, tenant_id: Optional[int] = None
    ) -> tuple[Optional[int], tuple[int, ...], Optional[str]]:
        """Resolve a regulation/standard code to DB ids and a display label."""
        result = await self.db.execute(
            select(Standard).where(
                Standard.is_active.is_(True),
                Standard.code == code,
            )
        )
        standard = result.scalar_one_or_none()
        if standard is not None:
            if tenant_id is not None and standard.tenant_id is not None and standard.tenant_id != tenant_id:
                return None, (), None
            return standard.id, (), (standard.full_name or standard.name)[:255]
        entry = lookup_by_code(code)
        if entry:
            return None, (), entry.label[:255]
        return None, (), None

    def _reconcile(
        self,
        db_hits: Sequence[RegulatoryCandidate],
        curated_hits: Sequence[RegulatoryCandidate],
    ) -> list[RegulatoryCandidate]:
        by_code: dict[str, RegulatoryCandidate] = {}
        for hit in list(db_hits) + list(curated_hits):
            key = hit.regulation_or_standard_code.upper()
            existing = by_code.get(key)
            if existing is None:
                by_code[key] = hit
                continue
            # Prefer the row that carries a standard_id; take max confidence.
            prefer_new = False
            if hit.standard_id and not existing.standard_id:
                prefer_new = True
            elif (hit.standard_id is not None) == (existing.standard_id is not None):
                prefer_new = hit.confidence > existing.confidence
            if prefer_new:
                by_code[key] = RegulatoryCandidate(
                    label=hit.label if hit.standard_id else existing.label,
                    regulation_or_standard_code=hit.regulation_or_standard_code,
                    standard_id=hit.standard_id or existing.standard_id,
                    clause_ids=hit.clause_ids or existing.clause_ids,
                    confidence=max(hit.confidence, existing.confidence),
                    rationale=hit.rationale if hit.standard_id else existing.rationale,
                    source=_SOURCE_STANDARDS if (hit.standard_id or existing.standard_id) else hit.source,
                )
            else:
                by_code[key] = RegulatoryCandidate(
                    label=existing.label,
                    regulation_or_standard_code=existing.regulation_or_standard_code,
                    standard_id=existing.standard_id or hit.standard_id,
                    clause_ids=existing.clause_ids or hit.clause_ids,
                    confidence=max(existing.confidence, hit.confidence),
                    rationale=existing.rationale,
                    source=_SOURCE_STANDARDS if (existing.standard_id or hit.standard_id) else existing.source,
                )
        return list(by_code.values())

    async def _rank_with_ai(
        self,
        *,
        text: str,
        shortlist: Sequence[RegulatoryCandidate],
        taxonomy_id: str,
        statutory: bool,
        answered_ids: frozenset[str],
    ) -> tuple[list[RegulatoryCandidate], list[ClarifyingQuestion]]:
        shortlist_payload = [
            {
                "code": c.regulation_or_standard_code,
                "label": c.label,
                "confidence": c.confidence,
                "source": c.source,
            }
            for c in shortlist
        ]
        system = (
            "You rank UK health & safety / ISO regulatory bases for compliance obligations. "
            "Return JSON only: "
            '{"candidates":[{"code":"...","label":"...","confidence":0.0,"rationale":"..."}],'
            '"questions":[{"id":"...","question":"...","options":[],"why":"..."}]}'
            " Prefer shortlist codes. Do not invent database ids."
        )
        prompt = (
            f"Obligation context:\n{text}\n"
            f"taxonomy_id={taxonomy_id} statutory={statutory}\n"
            f"Shortlist:\n{json.dumps(shortlist_payload)}\n"
            f"Already answered question ids: {sorted(answered_ids)}\n"
            "Return up to 5 candidates and 0–4 clarifying questions."
        )

        async def _do_call() -> str:
            client = get_ai_client()
            return await client.complete(prompt, system_prompt=system)

        raw = await call_via_upstream_breaker(AI_BREAKER_NAME, _do_call)
        return self._validate_ai_output(raw, shortlist)

    def _validate_ai_output(
        self,
        raw: Any,
        shortlist: Sequence[RegulatoryCandidate],
    ) -> tuple[list[RegulatoryCandidate], list[ClarifyingQuestion]]:
        payload = self._parse_json(raw)
        known = {c.regulation_or_standard_code.upper(): c for c in shortlist}
        candidates: list[RegulatoryCandidate] = []
        for item in payload.get("candidates") or []:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or item.get("regulation_or_standard_code") or "").strip()
            if not code:
                continue
            label = str(item.get("label") or "").strip()[:255]
            try:
                confidence = float(item.get("confidence") or 0)
            except (TypeError, ValueError):
                confidence = 0.0
            confidence = max(0.0, min(1.0, confidence))
            rationale = str(item.get("rationale") or "AI ranking").strip()[:500]
            known_hit = known.get(code.upper())
            curated = lookup_by_code(code)
            if known_hit is not None:
                candidates.append(
                    RegulatoryCandidate(
                        label=label or known_hit.label,
                        regulation_or_standard_code=known_hit.regulation_or_standard_code,
                        standard_id=known_hit.standard_id,
                        clause_ids=known_hit.clause_ids,
                        confidence=round(confidence, 3),
                        rationale=rationale or known_hit.rationale,
                        source=known_hit.source,
                    )
                )
            elif curated is not None:
                candidates.append(
                    RegulatoryCandidate(
                        label=label or curated.label,
                        regulation_or_standard_code=curated.code,
                        standard_id=None,
                        clause_ids=(),
                        confidence=round(confidence, 3),
                        rationale=rationale,
                        source=_SOURCE_CURATED,
                    )
                )
            else:
                # Invented citation: free text only, capped below threshold.
                candidates.append(
                    RegulatoryCandidate(
                        label=label or code,
                        regulation_or_standard_code=code[:40],
                        standard_id=None,
                        clause_ids=(),
                        confidence=round(min(confidence, AI_ONLY_CONFIDENCE_CAP), 3),
                        rationale=rationale,
                        source=_SOURCE_AI,
                    )
                )

        questions: list[ClarifyingQuestion] = []
        for item in payload.get("questions") or []:
            if not isinstance(item, dict):
                continue
            qid = str(item.get("id") or "").strip()[:64]
            question = str(item.get("question") or "").strip()[:200]
            why = str(item.get("why") or "").strip()[:200]
            options_raw = item.get("options") or []
            if not qid or not question:
                continue
            options: list[str] = []
            if isinstance(options_raw, list):
                for opt in options_raw[:6]:
                    s = str(opt).strip()[:80]
                    if s:
                        options.append(s)
            questions.append(ClarifyingQuestion(id=qid, question=question, options=tuple(options), why=why))
        if not (MIN_CLARIFY_QUESTIONS <= len(questions) <= MAX_CLARIFY_QUESTIONS):
            questions = []
        return candidates, questions

    @staticmethod
    def _parse_json(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        text = str(raw or "").strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return {}
            try:
                parsed = json.loads(match.group(0))
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}

    def _merge_with_ai(
        self,
        base: Sequence[RegulatoryCandidate],
        ai_candidates: Sequence[RegulatoryCandidate],
    ) -> list[RegulatoryCandidate]:
        return self._reconcile(list(base), list(ai_candidates))

    @staticmethod
    def _dedupe_rank(candidates: Sequence[RegulatoryCandidate]) -> list[RegulatoryCandidate]:
        by_code: dict[str, RegulatoryCandidate] = {}
        for hit in candidates:
            key = hit.regulation_or_standard_code.upper()
            existing = by_code.get(key)
            if existing is None or hit.confidence > existing.confidence:
                by_code[key] = hit
            elif hit.confidence == existing.confidence and hit.standard_id and not existing.standard_id:
                by_code[key] = hit
        ranked = list(by_code.values())
        ranked.sort(key=lambda c: (-c.confidence, c.regulation_or_standard_code))
        return ranked

    def _clarifying_questions(
        self,
        text: str,
        taxonomy_id: str,
        answered_ids: frozenset[str],
    ) -> tuple[ClarifyingQuestion, ...]:
        bank = [
            ClarifyingQuestion(
                id="topic_domain",
                question="Which area does this obligation primarily cover?",
                options=(
                    "Fire safety",
                    "Electrical / fixed wire",
                    "Hazardous substances / COSHH",
                    "Gas safety",
                    "Asbestos",
                    "Other / not sure",
                ),
                why="Narrows the regulation family when the title is ambiguous.",
            ),
            ClarifyingQuestion(
                id="statutory_nature",
                question="Is this a statutory legal duty or an internal / ISO programme requirement?",
                options=("Statutory legal duty", "ISO / management system", "Internal policy only", "Not sure"),
                why="Separates UK statute citations from ISO clause references.",
            ),
            ClarifyingQuestion(
                id="premises_or_activity",
                question="Does this apply to premises equipment, or to a work activity / process?",
                options=("Premises / building", "Work activity / process", "Both", "Not sure"),
                why="Distinguishes FSO/EAWR-style premises duties from activity regs.",
            ),
            ClarifyingQuestion(
                id="known_citation",
                question="Do you already know a short name for the regulation or standard?",
                options=(),
                why="Lets a known citation (e.g. FSO 2005, LOLER) raise confidence immediately.",
            ),
        ]
        remaining = [q for q in bank if q.id not in answered_ids]
        # Prefer domain question first when taxonomy is missing/generic
        if taxonomy_id.startswith("03") and "topic_domain" in answered_ids:
            remaining = [q for q in remaining if q.id != "topic_domain"]
        return tuple(remaining)

    async def _log_decision(
        self,
        *,
        tenant_id: int,
        requirement_id: Optional[int],
        top_confidence: float,
        candidate_count: int,
    ) -> None:
        try:
            self.db.add(
                AiDecisionLog(
                    tenant_id=tenant_id,
                    action="compliance_schedule_regulatory_basis_suggest",
                    entity_type="compliance_requirement",
                    entity_id=str(requirement_id) if requirement_id else "new",
                    confidence=round(top_confidence * 100, 2),
                    auto_applied=False,
                    payload={"candidate_count": candidate_count},
                )
            )
            await self.db.flush()
        except Exception:
            logger.exception("Failed to write AiDecisionLog for regulatory basis suggest")
            await self.db.rollback()
