"""Unit tests for Locust profile + soft-gate threshold resolution (no live load)."""

import json

from tests.performance.thresholds import (
    LOCUST_PROFILES,
    build_trend_record,
    resolve_perf_thresholds,
    write_soft_gate_summary,
)


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


def test_build_trend_record_includes_result_and_optional_github(monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    monkeypatch.delenv("GITHUB_REF", raising=False)

    payload = {
        "profile": "staging",
        "soft_gate": True,
        "overall": "PASS",
        "p95_ms": 120.0,
        "p95_limit_ms": 500,
        "p95_status": "OK",
        "error_rate_pct": 0.1,
        "error_rate_limit_pct": 1.0,
        "error_status": "OK",
        "num_requests": 200,
        "num_failures": 0,
        "breaches": [],
    }
    trend = build_trend_record(payload)
    assert trend["schema"] == "locust-soft-gate-trend/v1"
    assert trend["github"]["run_id"] == "12345"
    assert trend["github"]["sha"] == "abc123"
    assert trend["github"]["ref"] is None
    assert trend["result"]["overall"] == "PASS"
    assert trend["result"]["p95_ms"] == 120.0


def test_write_soft_gate_summary_emits_trend_artifact(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCUST_SUMMARY_DIR", str(tmp_path))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    payload = {
        "profile": "staging",
        "soft_gate": True,
        "overall": "BREACH",
        "p95_ms": 900.0,
        "p95_limit_ms": 500,
        "p95_status": "BREACH",
        "error_rate_pct": 0.0,
        "error_rate_limit_pct": 1.0,
        "error_status": "OK",
        "num_requests": 50,
        "num_failures": 0,
        "breaches": ["p95 response time 900ms > 500ms limit"],
    }
    write_soft_gate_summary(payload)

    trend_path = tmp_path / "locust-soft-gate-trend.json"
    assert trend_path.is_file()
    trend = json.loads(trend_path.read_text(encoding="utf-8"))
    assert trend["schema"] == "locust-soft-gate-trend/v1"
    assert trend["result"]["overall"] == "BREACH"
    assert (tmp_path / "locust-soft-gate-summary.md").is_file()
    assert (tmp_path / "locust-soft-gate-summary.json").is_file()
