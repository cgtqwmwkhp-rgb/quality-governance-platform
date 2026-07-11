"""Unit tests for Locust profile + soft-gate threshold resolution (no live load)."""

from tests.performance.thresholds import LOCUST_PROFILES, resolve_perf_thresholds


def test_staging_profile_matches_preferred_bar():
    resolved = resolve_perf_thresholds("staging")
    assert resolved["profile"] == "staging"
    assert resolved["p95_response_ms"] == 500
    assert resolved["error_rate_pct"] == 1.0
    assert resolved["users"] == 20
    assert resolved["spawn_rate"] == 5
    assert resolved["run_time"] == "60s"


def test_ci_profile_is_relaxed_for_runner_noise():
    resolved = resolve_perf_thresholds("ci")
    assert resolved["profile"] == "ci"
    assert resolved["p95_response_ms"] == 10000
    assert resolved["error_rate_pct"] == 3.0


def test_env_overrides_win_over_profile():
    resolved = resolve_perf_thresholds(
        "staging",
        p95_override="750",
        error_rate_override="2.5",
    )
    assert resolved["p95_response_ms"] == 750
    assert resolved["error_rate_pct"] == 2.5


def test_unknown_profile_falls_back_to_default():
    resolved = resolve_perf_thresholds("not-a-real-profile")
    assert resolved["profile"] == "default"
    assert resolved["p95_response_ms"] == LOCUST_PROFILES["default"]["p95_response_ms"]
