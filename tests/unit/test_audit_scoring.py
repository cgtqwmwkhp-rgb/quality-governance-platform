"""Tests for AuditScoringService – score calculation for audit runs."""

from types import SimpleNamespace

import pytest

from src.domain.services.audit_scoring_service import AuditScoringService, ScoreResult


class TestScoreResult:
    def test_score_result_creation(self):
        sr = ScoreResult(total_score=80.0, max_score=100.0, score_percentage=80.0)
        assert sr.total_score == 80.0
        assert sr.max_score == 100.0
        assert sr.score_percentage == 80.0

    def test_score_result_zero(self):
        sr = ScoreResult(total_score=0.0, max_score=0.0, score_percentage=0.0)
        assert sr.total_score == 0.0


class TestCalculateRunScore:
    @staticmethod
    def _response(score, max_score, is_na=False):
        return SimpleNamespace(score=score, max_score=max_score, is_na=is_na)

    def test_perfect_score(self):
        responses = [
            self._response(10, 10),
            self._response(10, 10),
            self._response(10, 10),
        ]
        result = AuditScoringService.calculate_run_score(responses)

        assert result.total_score == 30
        assert result.max_score == 30
        assert result.score_percentage == 100.0

    def test_partial_score(self):
        responses = [
            self._response(5, 10),
            self._response(8, 10),
        ]
        result = AuditScoringService.calculate_run_score(responses)

        assert result.total_score == 13
        assert result.max_score == 20
        assert result.score_percentage == 65.0

    def test_zero_score(self):
        responses = [
            self._response(0, 10),
            self._response(0, 10),
        ]
        result = AuditScoringService.calculate_run_score(responses)

        assert result.total_score == 0
        assert result.max_score == 20
        assert result.score_percentage == 0.0

    def test_na_responses_excluded(self):
        responses = [
            self._response(10, 10),
            self._response(0, 10, is_na=True),
            self._response(8, 10),
        ]
        result = AuditScoringService.calculate_run_score(responses)

        assert result.total_score == 18
        assert result.max_score == 20
        assert result.score_percentage == 90.0

    def test_all_na_responses(self):
        responses = [
            self._response(0, 10, is_na=True),
            self._response(0, 10, is_na=True),
        ]
        result = AuditScoringService.calculate_run_score(responses)

        assert result.total_score == 0
        assert result.max_score == 0
        assert result.score_percentage == 0.0

    def test_empty_responses(self):
        result = AuditScoringService.calculate_run_score([])
        assert result.total_score == 0
        assert result.max_score == 0
        assert result.score_percentage == 0.0

    def test_none_scores_treated_as_zero(self):
        responses = [
            self._response(None, 10),
            self._response(5, None),
        ]
        result = AuditScoringService.calculate_run_score(responses)

        assert result.total_score == 5
        assert result.max_score == 10

    def test_single_response(self):
        responses = [self._response(7, 10)]
        result = AuditScoringService.calculate_run_score(responses)

        assert result.total_score == 7
        assert result.max_score == 10
        assert result.score_percentage == 70.0

    def test_large_number_of_responses(self):
        responses = [self._response(8, 10) for _ in range(100)]
        result = AuditScoringService.calculate_run_score(responses)

        assert result.total_score == 800
        assert result.max_score == 1000
        assert result.score_percentage == 80.0

    def test_mixed_na_and_scored(self):
        responses = [
            self._response(10, 10),
            self._response(0, 10, is_na=True),
            self._response(0, 10, is_na=True),
            self._response(5, 10),
        ]
        result = AuditScoringService.calculate_run_score(responses)

        assert result.total_score == 15
        assert result.max_score == 20
        assert result.score_percentage == 75.0
