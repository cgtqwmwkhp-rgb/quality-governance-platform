"""Competency scoring service -- fundamentally different from AuditScoringService.

Assessment scoring: Pass/Fail with competency gate (Essential + Not Competent = FAIL).
Induction scoring: counts competent/not-yet-competent, generates CAPA for gaps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.domain.models.assessment import AssessmentResponse
    from src.domain.models.audit import AuditQuestion
    from src.domain.models.induction import InductionResponse


@dataclass
class AssessmentScoreResult:
    outcome: str  # "pass", "fail", "conditional"
    scorable_items: int  # excludes N/A responses
    competent_count: int
    not_competent_count: int
    na_count: int
    essential_failures: int
    good_to_have_failures: int


@dataclass
class InductionScoreResult:
    scorable_items: int  # excludes N/A responses
    competent_count: int
    not_yet_competent_count: int
    na_count: int
    items_needing_capa: List[int]  # question_ids that need CAPA


class CompetencyScoringService:
    @staticmethod
    def score_assessment(
        responses: List["AssessmentResponse"],
        questions: List["AuditQuestion"],
    ) -> AssessmentScoreResult:
        """Score an assessment run. Essential + Not Competent = FAIL."""
        criticality_map = {q.id: getattr(q, "criticality", None) for q in questions}

        total = 0
        competent = 0
        not_competent = 0
        na = 0
        essential_failures = 0
        good_to_have_failures = 0

        for r in responses:
            verdict = getattr(r, "verdict", None)
            if verdict is None:
                continue
            verdict_val = verdict.value if hasattr(verdict, "value") else str(verdict)

            if verdict_val == "na":
                na += 1
                continue

            total += 1
            if verdict_val == "competent":
                competent += 1
            elif verdict_val == "not_competent":
                not_competent += 1
                crit = criticality_map.get(r.question_id)
                crit_val = (
                    crit.value
                    if hasattr(crit, "value")
                    else str(crit) if crit else None
                )
                if crit_val == "essential":
                    essential_failures += 1
                else:
                    good_to_have_failures += 1

        if total == 0:
            outcome = "incomplete"
        elif essential_failures > 0:
            outcome = "fail"
        elif not_competent > 0:
            outcome = "conditional"
        else:
            outcome = "pass"

        return AssessmentScoreResult(
            outcome=outcome,
            scorable_items=total,
            competent_count=competent,
            not_competent_count=not_competent,
            na_count=na,
            essential_failures=essential_failures,
            good_to_have_failures=good_to_have_failures,
        )

    @staticmethod
    def score_induction(responses: List["InductionResponse"]) -> InductionScoreResult:
        """Score an induction run. Not Yet Competent items generate CAPA."""
        total = 0
        competent = 0
        not_yet = 0
        na = 0
        capa_items = []

        for r in responses:
            understanding = getattr(r, "understanding", None)
            if understanding is None:
                continue
            understanding_val = (
                understanding.value
                if hasattr(understanding, "value")
                else str(understanding)
            )

            if understanding_val == "na":
                na += 1
                continue

            total += 1
            if understanding_val == "competent":
                competent += 1
            elif understanding_val == "not_yet_competent":
                not_yet += 1
                capa_items.append(r.question_id)

        return InductionScoreResult(
            scorable_items=total,
            competent_count=competent,
            not_yet_competent_count=not_yet,
            na_count=na,
            items_needing_capa=capa_items,
        )
