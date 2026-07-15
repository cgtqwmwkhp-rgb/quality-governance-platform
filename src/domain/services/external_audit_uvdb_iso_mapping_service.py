"""Attach UVDB matrix-backed ISO context to external-audit import drafts."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.uvdb_achilles import UVDBISOCrossMapping, UVDBQuestion


@dataclass(frozen=True)
class UVDBISOMappingEnrichment:
    """Matrix context to persist with an external-audit import review."""

    mapped_standards: list[dict[str, object]]
    candidate_mapped_standards: list[list[dict[str, object]]]
    candidate_readiness: list[dict[str, object]]
    readiness_checklist: dict[str, object]


class ExternalAuditUVDBISOMappingService:
    """Resolve Achilles / UVDB draft findings against the persisted ISO matrix."""

    _UVDB_SCHEME = "achilles_uvdb"

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def enrich(
        self,
        *,
        detected_scheme: str,
        tenant_id: int | None,
        candidate_texts: list[str],
    ) -> UVDBISOMappingEnrichment:
        """Load tenant-visible matrix rows and prepare draft-safe mapping payloads."""
        if detected_scheme != self._UVDB_SCHEME:
            return self.enrich_from_rows(detected_scheme=detected_scheme, candidate_texts=candidate_texts, rows=[])

        tenant_filter = (
            UVDBISOCrossMapping.tenant_id.is_(None)
            if tenant_id is None
            else or_(UVDBISOCrossMapping.tenant_id == tenant_id, UVDBISOCrossMapping.tenant_id.is_(None))
        )
        result = await self.db.execute(
            select(UVDBISOCrossMapping, UVDBQuestion)
            .join(UVDBQuestion, UVDBQuestion.id == UVDBISOCrossMapping.uvdb_question_id)
            .where(tenant_filter)
            .order_by(UVDBQuestion.question_number, UVDBISOCrossMapping.iso_standard, UVDBISOCrossMapping.iso_clause)
        )
        return self.enrich_from_rows(
            detected_scheme=detected_scheme,
            candidate_texts=candidate_texts,
            rows=result.all(),
        )

    @classmethod
    def enrich_from_rows(
        cls,
        *,
        detected_scheme: str,
        candidate_texts: list[str],
        rows: Iterable[tuple[UVDBISOCrossMapping, UVDBQuestion]],
    ) -> UVDBISOMappingEnrichment:
        """Create JSON-safe mappings and non-blocking reviewer readiness flags."""
        matrix = cls._dedupe_mappings(cls._serialize_row(mapping, question) for mapping, question in rows)
        is_uvdb = detected_scheme == cls._UVDB_SCHEME
        candidate_mappings = [
            (
                cls._dedupe_mappings(mapping for mapping in matrix if cls._mapping_matches_text(mapping, text))
                if is_uvdb
                else []
            )
            for text in candidate_texts
        ]
        candidate_readiness = [
            cls._candidate_readiness(is_uvdb=is_uvdb, mappings=mappings) for mappings in candidate_mappings
        ]
        return UVDBISOMappingEnrichment(
            mapped_standards=matrix if is_uvdb else [],
            candidate_mapped_standards=candidate_mappings,
            candidate_readiness=candidate_readiness,
            readiness_checklist={
                "uvdb_iso_matrix_applicable": is_uvdb,
                "uvdb_iso_matrix_available": bool(matrix) if is_uvdb else None,
                "mapped_uvdb_iso_clauses": len(matrix) if is_uvdb else 0,
                "reviewer_confirmation_required": is_uvdb,
                "non_blocking": True,
            },
        )

    @staticmethod
    def _serialize_row(mapping: UVDBISOCrossMapping, question: UVDBQuestion) -> dict[str, object]:
        return {
            "standard": f"ISO {mapping.iso_standard}",
            "clause_number": mapping.iso_clause,
            "title": mapping.iso_clause_title,
            "basis": "uvdb_iso_cross_mapping",
            "confidence": {"direct": 0.95, "partial": 0.75, "related": 0.6}.get(mapping.mapping_type, 0.6),
            "mapping_type": mapping.mapping_type,
            "uvdb_question": question.question_number,
            "uvdb_question_text": question.question_text,
            "mapping_notes": mapping.mapping_notes,
        }

    @staticmethod
    def _mapping_matches_text(mapping: dict[str, object], text: str) -> bool:
        normalized = text.lower()
        question_number = str(mapping["uvdb_question"])
        if re.search(rf"(?<!\d){re.escape(question_number)}(?!\d)", normalized):
            return True

        question_words = {
            word
            for word in re.findall(r"[a-z]{5,}", str(mapping["uvdb_question_text"]).lower())
            if word not in {"company", "their", "these", "which", "where", "would"}
        }
        return len(question_words.intersection(re.findall(r"[a-z]{5,}", normalized))) >= 2

    @staticmethod
    def _candidate_readiness(*, is_uvdb: bool, mappings: list[dict[str, object]]) -> dict[str, object]:
        return {
            "uvdb_iso_matrix_applicable": is_uvdb,
            "matrix_mappings_found": len(mappings),
            "verify_mapped_iso_clause_evidence": bool(mappings),
            "confirm_uvdb_question_alignment": is_uvdb,
            "manual_mapping_review_required": is_uvdb and not mappings,
            "blocks_promotion": False,
        }

    @staticmethod
    def merge_mapped_standards(
        existing: list[dict[str, object]], matrix_mappings: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """Preserve text-derived matches while adding distinct matrix mappings."""
        merged = [*existing, *matrix_mappings]
        seen: set[tuple[object, ...]] = set()
        result: list[dict[str, object]] = []
        for mapping in merged:
            key = (
                mapping.get("standard"),
                mapping.get("clause_id") or mapping.get("clause_number"),
                mapping.get("uvdb_question"),
                mapping.get("basis"),
            )
            if key not in seen:
                seen.add(key)
                result.append(mapping)
        return result

    @staticmethod
    def _dedupe_mappings(mappings: Iterable[dict[str, object]]) -> list[dict[str, object]]:
        seen: set[tuple[object, ...]] = set()
        result: list[dict[str, object]] = []
        for mapping in mappings:
            key = (mapping["standard"], mapping["clause_number"], mapping["uvdb_question"])
            if key not in seen:
                seen.add(key)
                result.append(mapping)
        return result
