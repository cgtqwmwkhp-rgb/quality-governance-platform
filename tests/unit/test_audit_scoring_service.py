"""Unit tests for Audit Scoring Service - can run standalone."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


class MockResponse:
    """Minimal mock for an audit checklist response."""

    def __init__(self, score, max_score, is_na=False):
        self.score = score
        self.max_score = max_score
        self.is_na = is_na


def test_score_result_dataclass():
    """Test ScoreResult dataclass construction and fields."""
    from src.domain.services.audit_scoring_service import ScoreResult

    result = ScoreResult(total_score=85.0, max_score=100.0, score_percentage=85.0)
    assert result.total_score == 85.0
    assert result.max_score == 100.0
    assert result.score_percentage == 85.0
    print("✓ ScoreResult fields accessible")
    print(f"  total={result.total_score}, max={result.max_score}, pct={result.score_percentage}%")

    print("\n✅ ScoreResult dataclass works correctly")


def test_calculate_run_score_basic():
    """Test basic score calculation with scored responses."""
    from src.domain.services.audit_scoring_service import AuditScoringService

    responses = [
        MockResponse(score=8, max_score=10),
        MockResponse(score=7, max_score=10),
        MockResponse(score=9, max_score=10),
        MockResponse(score=6, max_score=10),
    ]

    result = AuditScoringService.calculate_run_score(responses)

    assert result.total_score == 30, f"Expected total 30, got {result.total_score}"
    assert result.max_score == 40, f"Expected max 40, got {result.max_score}"
    assert result.score_percentage == 75.0, f"Expected 75.0%, got {result.score_percentage}"
    print(f"✓ Basic scoring: {result.total_score}/{result.max_score} = {result.score_percentage}%")

    print("\n✅ Basic score calculation correct")


def test_calculate_run_score_with_na_responses():
    """Test that N/A responses are excluded from scoring."""
    from src.domain.services.audit_scoring_service import AuditScoringService

    responses = [
        MockResponse(score=10, max_score=10),
        MockResponse(score=0, max_score=10, is_na=True),
        MockResponse(score=8, max_score=10),
        MockResponse(score=0, max_score=10, is_na=True),
        MockResponse(score=5, max_score=10),
    ]

    result = AuditScoringService.calculate_run_score(responses)

    assert result.total_score == 23, f"Expected total 23, got {result.total_score}"
    assert result.max_score == 30, f"Expected max 30 (3 scored items), got {result.max_score}"
    expected_pct = round(23 / 30 * 100, 10)
    assert abs(result.score_percentage - expected_pct) < 0.01
    print(f"✓ N/A items excluded: {result.total_score}/{result.max_score} = {result.score_percentage:.1f}%")
    print("  (2 N/A responses correctly excluded)")

    print("\n✅ N/A handling correct")


def test_calculate_run_score_all_na():
    """Test scoring when all responses are N/A (edge case, avoid division by zero)."""
    from src.domain.services.audit_scoring_service import AuditScoringService

    responses = [
        MockResponse(score=0, max_score=10, is_na=True),
        MockResponse(score=0, max_score=10, is_na=True),
    ]

    result = AuditScoringService.calculate_run_score(responses)

    assert result.total_score == 0
    assert result.max_score == 0
    assert result.score_percentage == 0.0
    print("✓ All N/A responses: score=0, max=0, pct=0% (no division by zero)")

    print("\n✅ All-N/A edge case handled")


def test_calculate_run_score_empty_list():
    """Test scoring with empty response list."""
    from src.domain.services.audit_scoring_service import AuditScoringService

    result = AuditScoringService.calculate_run_score([])

    assert result.total_score == 0
    assert result.max_score == 0
    assert result.score_percentage == 0.0
    print("✓ Empty list: score=0, max=0, pct=0%")

    print("\n✅ Empty list edge case handled")


def test_calculate_run_score_perfect():
    """Test perfect score (100%) calculation."""
    from src.domain.services.audit_scoring_service import AuditScoringService

    responses = [
        MockResponse(score=10, max_score=10),
        MockResponse(score=10, max_score=10),
        MockResponse(score=10, max_score=10),
    ]

    result = AuditScoringService.calculate_run_score(responses)

    assert result.total_score == 30
    assert result.max_score == 30
    assert result.score_percentage == 100.0
    print("✓ Perfect score: 30/30 = 100.0%")

    print("\n✅ Perfect score calculation correct")


def test_calculate_run_score_zero_scores():
    """Test scoring when all responses have zero scores."""
    from src.domain.services.audit_scoring_service import AuditScoringService

    responses = [
        MockResponse(score=0, max_score=10),
        MockResponse(score=0, max_score=10),
        MockResponse(score=0, max_score=10),
    ]

    result = AuditScoringService.calculate_run_score(responses)

    assert result.total_score == 0
    assert result.max_score == 30
    assert result.score_percentage == 0.0
    print("✓ All-zero scores: 0/30 = 0.0%")

    print("\n✅ Zero score calculation correct")


def test_calculate_run_score_none_scores():
    """Test scoring handles None score values gracefully (treated as 0)."""
    from src.domain.services.audit_scoring_service import AuditScoringService

    responses = [
        MockResponse(score=None, max_score=10),
        MockResponse(score=8, max_score=10),
        MockResponse(score=None, max_score=None),
    ]

    result = AuditScoringService.calculate_run_score(responses)

    assert result.total_score == 8, f"Expected 8, got {result.total_score}"
    assert result.max_score == 20, f"Expected 20, got {result.max_score}"
    print(f"✓ None scores treated as 0: {result.total_score}/{result.max_score} = {result.score_percentage:.1f}%")

    print("\n✅ None value handling correct")


if __name__ == "__main__":
    print("=" * 60)
    print("AUDIT SCORING SERVICE TESTS")
    print("=" * 60)
    print()

    test_score_result_dataclass()
    print()
    test_calculate_run_score_basic()
    print()
    test_calculate_run_score_with_na_responses()
    print()
    test_calculate_run_score_all_na()
    print()
    test_calculate_run_score_empty_list()
    print()
    test_calculate_run_score_perfect()
    print()
    test_calculate_run_score_zero_scores()
    print()
    test_calculate_run_score_none_scores()

    print()
    print("=" * 60)
    print("ALL AUDIT SCORING TESTS PASSED ✅")
    print("=" * 60)
