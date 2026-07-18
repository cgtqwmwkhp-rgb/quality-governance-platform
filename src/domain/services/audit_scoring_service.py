"""Audit scoring service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ScoreResult:
    total_score: float
    max_score: float
    score_percentage: float


class AuditScoringService:
    @staticmethod
    def calculate_run_score(responses: list) -> ScoreResult:
        # Only count fully scored answers. Notes/photos without a score must not
        # inflate the denominator (and NA is excluded entirely).
        scored_responses = [r for r in responses if not r.is_na and r.score is not None and r.max_score is not None]
        total_score = sum(float(r.score) for r in scored_responses)
        max_score = sum(float(r.max_score) for r in scored_responses)
        score_percentage = (total_score / max_score * 100) if max_score > 0 else 0.0
        return ScoreResult(
            total_score=total_score,
            max_score=max_score,
            score_percentage=score_percentage,
        )

    @staticmethod
    def question_max_score(question: Any) -> float:
        """Resolve the maximum points available for a question."""
        if question is None:
            return 1.0
        if getattr(question, "max_score", None) is not None:
            return float(question.max_score)
        weight = getattr(question, "weight", None)
        if weight is not None:
            return float(weight)
        return 1.0

    @classmethod
    def derive_response_score(
        cls,
        question: Any,
        *,
        response_value: Optional[str] = None,
        response_text: Optional[str] = None,
        response_number: Optional[float] = None,
        response_bool: Optional[bool] = None,
        is_na: bool = False,
        score: Optional[float] = None,
        max_score: Optional[float] = None,
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Derive (score, max_score) for a response.

        Client-supplied values win when present. Otherwise score from question
        type + answer so run completion is not stuck at 0%.
        """
        resolved_max = float(max_score) if max_score is not None else cls.question_max_score(question)
        if is_na:
            return (0.0 if score is None else float(score), resolved_max)

        if score is not None and max_score is not None:
            return float(score), resolved_max

        question_type = (getattr(question, "question_type", None) or "").lower()
        positive = (getattr(question, "positive_answer", None) or "yes").lower()
        answer = cls._normalize_answer(
            response_value=response_value,
            response_text=response_text,
            response_number=response_number,
            response_bool=response_bool,
        )

        derived: Optional[float]
        if question_type in {"yes_no", "yes_no_na"}:
            if answer in {"", None}:
                derived = None
            elif answer == "na":
                derived = resolved_max
            else:
                positive_val = "no" if positive == "no" else "yes"
                derived = resolved_max if answer == positive_val else 0.0
        elif question_type == "pass_fail":
            if answer in {"", None}:
                derived = None
            else:
                positive_val = "fail" if positive == "no" else "pass"
                derived = resolved_max if answer == positive_val else 0.0
        elif question_type in {"rating", "score", "number", "numeric"}:
            if response_number is not None:
                max_value = float(
                    getattr(question, "max_value", None) or getattr(question, "max_score", None) or resolved_max or 1
                )
                derived = (float(response_number) / max_value) * resolved_max if max_value else 0.0
            elif answer not in {"", None}:
                try:
                    num = float(answer)
                except ValueError:
                    derived = resolved_max
                else:
                    max_value = float(
                        getattr(question, "max_value", None)
                        or getattr(question, "max_score", None)
                        or resolved_max
                        or 1
                    )
                    derived = (num / max_value) * resolved_max if max_value else 0.0
            else:
                derived = None
        elif question_type in {
            "radio",
            "select",
            "dropdown",
            "checkbox",
            "multi_select",
            "multi_choice",
            "checklist",
        }:
            derived = cls._score_from_options(question, answer, resolved_max)
        elif question_type in {"text", "textarea", "date", "photo", "signature"}:
            has_answer = bool(answer) or response_text not in (None, "") or response_number is not None
            derived = resolved_max if has_answer else None
        else:
            has_answer = bool(answer) or response_text not in (None, "") or response_number is not None
            derived = resolved_max if has_answer else None

        if score is not None:
            return float(score), resolved_max
        # Unanswered: leave both unset so notes-only rows don't enter the denominator.
        if derived is None:
            return None, None
        return derived, resolved_max

    @classmethod
    def apply_derived_scores(cls, question: Any, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a shallow-copied payload with score/max_score filled in."""
        enriched = dict(payload)
        score, max_score = cls.derive_response_score(
            question,
            response_value=enriched.get("response_value"),
            response_text=enriched.get("response_text"),
            response_number=enriched.get("response_number"),
            response_bool=enriched.get("response_bool"),
            is_na=bool(enriched.get("is_na", False)),
            score=enriched.get("score"),
            max_score=enriched.get("max_score"),
        )
        enriched["max_score"] = max_score
        enriched["score"] = score
        return enriched

    @staticmethod
    def _normalize_answer(
        *,
        response_value: Optional[str],
        response_text: Optional[str],
        response_number: Optional[float],
        response_bool: Optional[bool],
    ) -> str:
        if response_value not in (None, ""):
            return str(response_value).strip().lower()
        if response_bool is not None:
            return "yes" if response_bool else "no"
        if response_number is not None:
            return str(response_number)
        if response_text not in (None, ""):
            return str(response_text).strip().lower()
        return ""

    @staticmethod
    def _score_from_options(question: Any, answer: str, resolved_max: float) -> Optional[float]:
        if not answer:
            return None
        options = getattr(question, "options_json", None) or getattr(question, "options", None) or []
        selected = {part.strip().lower() for part in answer.replace(";", ",").split(",") if part.strip()}
        if not selected:
            return None

        matched_scores: list[float] = []
        for option in options:
            if not isinstance(option, dict):
                continue
            option_value = str(option.get("value", "")).strip().lower()
            option_label = str(option.get("label", "")).strip().lower()
            if not (selected & {option_value, option_label}):
                continue
            if option.get("score") is not None:
                matched_scores.append(float(option["score"]))
            else:
                matched_scores.append(resolved_max)

        if matched_scores:
            return min(resolved_max, sum(matched_scores))
        # Answered without option metadata — credit full points.
        return resolved_max
