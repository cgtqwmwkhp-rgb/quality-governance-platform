"""Unit tests for Locust profile + soft-gate threshold resolution (no live load)."""

import json

from tests.performance.thresholds import (
    LOCUST_PROFILES,
    QUEUE_DEPTH_SCALE_HINTS,
    SOFT_GATE_HARD_GATE_PROMOTE,
    SOFT_GATE_REENABLE,
    SOFT_GATE_TRIAL_TIGHTEN,
    build_trend_record,
    evaluate_hard_gate_promotion_readiness,
    evaluate_soft_gate_posture,
    evaluate_soft_gate_reenable_readiness,
    evaluate_sustained_scale_hints,
    evaluate_trial_tighten_readiness,
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


def test_queue_depth_scale_hints_match_docs():
    """Advisory constants stay aligned with docs/performance/queue-depth-scale-hint.md."""
    assert QUEUE_DEPTH_SCALE_HINTS["p95_breach_multiplier"] == 1.5
    assert QUEUE_DEPTH_SCALE_HINTS["error_rate_breach_multiplier"] == 2.0
    assert QUEUE_DEPTH_SCALE_HINTS["sustained_run_count"] == 3
    assert QUEUE_DEPTH_SCALE_HINTS["staging_users"] == LOCUST_PROFILES["staging"]["users"]
    staging_p95 = int(LOCUST_PROFILES["staging"]["p95_response_ms"])
    assert staging_p95 * QUEUE_DEPTH_SCALE_HINTS["p95_breach_multiplier"] == 750.0


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
    posture_path = tmp_path / "locust-soft-gate-posture.json"
    assert posture_path.is_file()
    posture = json.loads(posture_path.read_text(encoding="utf-8"))
    assert posture["schema"] == "locust-soft-gate-posture/v1"
    assert posture["recommended_posture"] == "observe"
    summary_md = (tmp_path / "locust-soft-gate-summary.md").read_text(encoding="utf-8")
    assert "Recommended posture" in summary_md
    assert "`observe`" in summary_md
    assert "**Signals:**" in summary_md
    assert "scale=`False`" in summary_md
    assert "promote=`False`" in summary_md


def _trend(p95_ms: float, error_rate_pct: float = 0.0) -> dict:
    return {
        "schema": "locust-soft-gate-trend/v1",
        "result": {"p95_ms": p95_ms, "error_rate_pct": error_rate_pct},
    }


def test_evaluate_sustained_scale_hints_needs_window():
    out = evaluate_sustained_scale_hints([_trend(900.0), _trend(950.0)])
    assert out["schema"] == "locust-soft-gate-scale-hint/v1"
    assert out["enough_runs"] is False
    assert out["p95_scale_hint"] is False
    assert out["required_runs"] == QUEUE_DEPTH_SCALE_HINTS["sustained_run_count"]
    assert "Collect ≥3" in out["actions"][0]


def test_evaluate_sustained_scale_hints_p95_triggers():
    records = [_trend(800.0), _trend(900.0), _trend(1000.0)]
    out = evaluate_sustained_scale_hints(records)
    assert out["enough_runs"] is True
    assert out["p95_hint_limit_ms"] == 750.0
    assert out["p95_scale_hint"] is True
    assert out["error_rate_scale_hint"] is False
    assert any("Sustained p95" in a for a in out["actions"])


def test_evaluate_sustained_scale_hints_error_rate_triggers():
    records = [_trend(100.0, 2.5), _trend(120.0, 3.0), _trend(110.0, 2.1)]
    out = evaluate_sustained_scale_hints(records)
    assert out["error_rate_scale_hint"] is True
    assert out["p95_scale_hint"] is False
    assert any("Sustained error rate" in a for a in out["actions"])


def test_evaluate_sustained_scale_hints_no_trigger_when_mixed():
    # One run under the hint limit → no sustained p95 hint
    records = [_trend(800.0), _trend(600.0), _trend(900.0)]
    out = evaluate_sustained_scale_hints(records)
    assert out["p95_scale_hint"] is False
    assert out["error_rate_scale_hint"] is False
    assert out["actions"] == ["No sustained scale hint — keep observing under soft-gate."]


def test_soft_gate_trial_tighten_constants_match_docs():
    assert SOFT_GATE_TRIAL_TIGHTEN["p95_response_ms"] == 350
    assert SOFT_GATE_TRIAL_TIGHTEN["error_rate_pct"] == 1.0
    assert SOFT_GATE_TRIAL_TIGHTEN["stable_run_count"] == 3
    # Trial is stricter than staging bar but still soft-gate only.
    assert SOFT_GATE_TRIAL_TIGHTEN["p95_response_ms"] < LOCUST_PROFILES["staging"]["p95_response_ms"]


def test_evaluate_trial_tighten_readiness_needs_window():
    out = evaluate_trial_tighten_readiness([_trend(100.0), _trend(120.0)])
    assert out["schema"] == "locust-soft-gate-trial-tighten/v1"
    assert out["enough_runs"] is False
    assert out["ready_for_trial_tighten"] is False
    assert out["trial_p95_ms"] == 350
    assert "Collect ≥3" in out["actions"][0]


def test_evaluate_trial_tighten_readiness_stable_window():
    records = [_trend(200.0), _trend(180.0, 0.2), _trend(220.0, 0.5)]
    out = evaluate_trial_tighten_readiness(records)
    assert out["enough_runs"] is True
    assert out["stable_under_staging_bar"] is True
    assert out["ready_for_trial_tighten"] is True
    assert any("LOCUST_P95_MS=350" in a for a in out["actions"])


def test_evaluate_trial_tighten_readiness_rejects_breach():
    records = [_trend(200.0), _trend(600.0), _trend(180.0)]
    out = evaluate_trial_tighten_readiness(records)
    assert out["ready_for_trial_tighten"] is False
    assert out["stable_under_staging_bar"] is False
    assert any("Not ready for trial tighten" in a for a in out["actions"])


def test_soft_gate_hard_gate_promote_constants_match_docs():
    assert SOFT_GATE_HARD_GATE_PROMOTE["stable_run_count"] == 5
    assert SOFT_GATE_HARD_GATE_PROMOTE["p95_headroom_fraction"] == 0.8
    # Stricter window than trial tighten; headroom is below staging bar.
    assert SOFT_GATE_HARD_GATE_PROMOTE["stable_run_count"] > SOFT_GATE_TRIAL_TIGHTEN["stable_run_count"]
    staging_p95 = int(LOCUST_PROFILES["staging"]["p95_response_ms"])
    assert staging_p95 * SOFT_GATE_HARD_GATE_PROMOTE["p95_headroom_fraction"] == 400.0


def test_evaluate_hard_gate_promotion_readiness_needs_window():
    out = evaluate_hard_gate_promotion_readiness([_trend(100.0)] * 3)
    assert out["schema"] == "locust-soft-gate-hard-gate-ready/v1"
    assert out["enough_runs"] is False
    assert out["ready_for_hard_gate_promotion"] is False
    assert out["p95_headroom_limit_ms"] == 400.0
    assert "Collect ≥5" in out["actions"][0]


def test_evaluate_hard_gate_promotion_readiness_stable_with_headroom():
    records = [_trend(200.0), _trend(180.0), _trend(220.0), _trend(190.0), _trend(210.0)]
    out = evaluate_hard_gate_promotion_readiness(records)
    assert out["enough_runs"] is True
    assert out["stable_under_staging_bar"] is True
    assert out["within_p95_headroom"] is True
    assert out["ready_for_hard_gate_promotion"] is True
    assert any("LOCUST_SOFT_GATE" in a for a in out["actions"])


def test_evaluate_hard_gate_promotion_readiness_rejects_thin_margin():
    # Under staging bar (500) but above 80% headroom (400) → not ready.
    records = [_trend(200.0), _trend(180.0), _trend(450.0), _trend(190.0), _trend(210.0)]
    out = evaluate_hard_gate_promotion_readiness(records)
    assert out["stable_under_staging_bar"] is True
    assert out["within_p95_headroom"] is False
    assert out["ready_for_hard_gate_promotion"] is False
    assert any("80%" in a or "400" in a for a in out["actions"])


def test_soft_gate_reenable_constants_match_docs():
    assert SOFT_GATE_REENABLE["breach_run_count"] == 2
    # Demote window is shorter than hard-gate promote (fail-fast back to soft-gate).
    assert SOFT_GATE_REENABLE["breach_run_count"] < SOFT_GATE_HARD_GATE_PROMOTE["stable_run_count"]


def test_evaluate_soft_gate_reenable_readiness_needs_window():
    out = evaluate_soft_gate_reenable_readiness([_trend(900.0)])
    assert out["schema"] == "locust-soft-gate-reenable/v1"
    assert out["enough_runs"] is False
    assert out["ready_for_soft_gate_reenable"] is False
    assert "Collect ≥2" in out["actions"][0]


def test_evaluate_soft_gate_reenable_readiness_sustained_breaches():
    records = [_trend(600.0), _trend(550.0, 1.5)]
    out = evaluate_soft_gate_reenable_readiness(records)
    assert out["enough_runs"] is True
    assert out["sustained_staging_breaches"] is True
    assert out["ready_for_soft_gate_reenable"] is True
    assert any("LOCUST_SOFT_GATE=1" in a for a in out["actions"])


def test_evaluate_soft_gate_reenable_readiness_rejects_mixed_window():
    # One run still under staging bar → do not demote.
    records = [_trend(600.0), _trend(200.0)]
    out = evaluate_soft_gate_reenable_readiness(records)
    assert out["ready_for_soft_gate_reenable"] is False
    assert out["sustained_staging_breaches"] is False
    assert any("Not ready for soft-gate re-enable" in a for a in out["actions"])


def test_evaluate_soft_gate_posture_observe_when_insufficient():
    out = evaluate_soft_gate_posture([_trend(200.0)])
    assert out["schema"] == "locust-soft-gate-posture/v1"
    assert out["recommended_posture"] == "observe"
    assert out["signals"]["promote_hard_gate"] is False
    assert out["signals"]["reenable_soft_gate"] is False
    assert any("keep observing" in a for a in out["actions"])


def test_evaluate_soft_gate_posture_prefers_scale_over_reenable():
    # Sustained >1.5× staging p95 → scale_investigate beats demote.
    records = [_trend(800.0), _trend(820.0), _trend(850.0)]
    out = evaluate_soft_gate_posture(records)
    assert out["recommended_posture"] == "scale_investigate"
    assert out["signals"]["scale_investigate"] is True
    assert out["signals"]["reenable_soft_gate"] is True


def test_evaluate_soft_gate_posture_promote_when_stable_headroom():
    records = [_trend(200.0), _trend(180.0), _trend(220.0), _trend(190.0), _trend(210.0)]
    out = evaluate_soft_gate_posture(records)
    assert out["recommended_posture"] == "promote_hard_gate"
    assert out["signals"]["promote_hard_gate"] is True
    assert out["signals"]["trial_tighten"] is True


def test_evaluate_soft_gate_posture_trial_when_stable_without_headroom():
    # Under staging bar but above 80% headroom → trial tighten, not promote.
    records = [_trend(450.0), _trend(420.0), _trend(430.0)]
    out = evaluate_soft_gate_posture(records)
    assert out["recommended_posture"] == "trial_tighten"
    assert out["signals"]["trial_tighten"] is True
    assert out["signals"]["promote_hard_gate"] is False


def test_write_soft_gate_summary_uses_trend_history_for_posture(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCUST_SUMMARY_DIR", str(tmp_path))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    history = [_trend(200.0), _trend(180.0), _trend(220.0), _trend(190.0)]
    history_path = tmp_path / "prior-trends.json"
    history_path.write_text(json.dumps(history), encoding="utf-8")
    monkeypatch.setenv("LOCUST_TREND_HISTORY", str(history_path))

    payload = {
        "profile": "staging",
        "soft_gate": True,
        "overall": "PASS",
        "p95_ms": 210.0,
        "p95_limit_ms": 500,
        "p95_status": "OK",
        "error_rate_pct": 0.0,
        "error_rate_limit_pct": 1.0,
        "error_status": "OK",
        "num_requests": 50,
        "num_failures": 0,
        "breaches": [],
    }
    write_soft_gate_summary(payload)

    posture = json.loads((tmp_path / "locust-soft-gate-posture.json").read_text(encoding="utf-8"))
    assert posture["recommended_posture"] == "promote_hard_gate"
    summary_md = (tmp_path / "locust-soft-gate-summary.md").read_text(encoding="utf-8")
    assert "`promote_hard_gate`" in summary_md
    assert "4 prior + current run" in summary_md
