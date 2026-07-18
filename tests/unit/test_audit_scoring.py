"""Tests for AuditScoringService – score calculation for audit runs."""

from types import SimpleNamespace

import pytest

from src.domain.services.audit_scoring_service import AuditScoringService, ScoreResult


class TestDeriveResponseScore:
    def test_yes_no_positive_derives_full_score_and_max(self):
        question = SimpleNamespace(
            question_type="yes_no",
            max_score=1.0,
            weight=1.0,
            positive_answer="yes",
            options_json=None,
            max_value=None,
        )
        score, max_score = AuditScoringService.derive_response_score(
            question,
            response_value="yes",
        )
        assert score == 1.0
        assert max_score == 1.0

    def test_yes_no_negative_derives_zero(self):
        question = SimpleNamespace(
            question_type="yes_no",
            max_score=2.0,
            weight=2.0,
            positive_answer="yes",
            options_json=None,
            max_value=None,
        )
        score, max_score = AuditScoringService.derive_response_score(
            question,
            response_value="no",
        )
        assert score == 0.0
        assert max_score == 2.0

    def test_apply_derived_scores_fills_missing_fields(self):
        question = SimpleNamespace(
            question_type="pass_fail",
            max_score=1.0,
            weight=1.0,
            positive_answer="yes",
            options_json=None,
            max_value=None,
        )
        enriched = AuditScoringService.apply_derived_scores(
            question,
            {"question_id": 1, "response_value": "pass"},
        )
        assert enriched["score"] == 1.0
        assert enriched["max_score"] == 1.0

    def test_client_supplied_scores_win(self):
        question = SimpleNamespace(
            question_type="yes_no",
            max_score=1.0,
            weight=1.0,
            positive_answer="yes",
            options_json=None,
            max_value=None,
        )
        score, max_score = AuditScoringService.derive_response_score(
            question,
            response_value="yes",
            score=0.5,
            max_score=2.0,
        )
        assert score == 0.5
        assert max_score == 2.0

    def test_radio_option_score_not_full_credit(self):
        question = SimpleNamespace(
            question_type="radio",
            max_score=10.0,
            weight=10.0,
            positive_answer="yes",
            options_json=[
                {"label": "Good", "value": "good", "score": 10},
                {"label": "Partial", "value": "partial", "score": 4},
            ],
            max_value=None,
        )
        score, max_score = AuditScoringService.derive_response_score(
            question,
            response_value="partial",
        )
        assert score == 4.0
        assert max_score == 10.0

    def test_apply_derived_scores_recomputes_when_score_omitted(self):
        question = SimpleNamespace(
            question_type="yes_no",
            max_score=1.0,
            weight=1.0,
            positive_answer="yes",
            options_json=None,
            max_value=None,
        )
        enriched = AuditScoringService.apply_derived_scores(
            question,
            {"response_value": "no"},
        )
        assert enriched["score"] == 0.0
        assert enriched["max_score"] == 1.0


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
