"""Audit scoring service."""

from dataclasses import dataclass


@dataclass
class ScoreResult:
    total_score: float
    max_score: float
    score_percentage: float


class AuditScoringService:
    @staticmethod
    def calculate_run_score(responses: list) -> ScoreResult:
        scored_responses = [r for r in responses if not r.is_na]
        total_score = sum(r.score or 0 for r in scored_responses)
        max_score = sum(r.max_score or 0 for r in scored_responses)
        score_percentage = (total_score / max_score * 100) if max_score > 0 else 0.0
        return ScoreResult(
            total_score=total_score,
            max_score=max_score,
            score_percentage=score_percentage,
        )
