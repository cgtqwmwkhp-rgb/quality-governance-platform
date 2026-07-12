"""Locust performance profiles and soft-gate threshold helpers (no Locust import)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Advisory Preferred S14 queue-depth / soft-gate scale hints (docs only semantics).
# Ratios apply to the staging soft-gate bar; they never change Locust exit codes.
QUEUE_DEPTH_SCALE_HINTS: dict[str, float | int] = {
    "p95_breach_multiplier": 1.5,  # sustained p95 > 1.5× staging limit → investigate/scale
    "error_rate_breach_multiplier": 2.0,  # sustained error rate > 2× staging limit
    "sustained_run_count": 3,  # compare ≥ N recent soft-gate trend records
    "staging_users": 20,  # soft-gate load shape (capacity-plan alignment)
}

# Candidate non-blocking soft-gate tighten (docs Observe → Document → Promote).
# Applied only via env overrides (e.g. LOCUST_P95_MS=350); never mutates profiles.
SOFT_GATE_TRIAL_TIGHTEN: dict[str, float | int] = {
    "p95_response_ms": 350,  # trial LOCUST_P95_MS while LOCUST_SOFT_GATE=1
    "error_rate_pct": 1.0,  # keep staging error bar; tighten latency first
    "stable_run_count": 3,  # ≥ N recent runs under current staging bar before trial
}

# Advisory hard-gate promotion readiness (docs Observe → Document → Promote).
# Never flips workflow YAML or branch protection; operators still act manually.
SOFT_GATE_HARD_GATE_PROMOTE: dict[str, float | int] = {
    "stable_run_count": 5,  # ≥ N recent runs under staging bar before considering hard-gate
    "p95_headroom_fraction": 0.8,  # all runs ≤ 0.8× staging p95 (margin vs flaky runners)
}

# Advisory soft-gate re-enable / demote readiness (Promote → Demote safety valve).
# Never flips workflow YAML or branch protection; operators still act manually.
SOFT_GATE_REENABLE: dict[str, float | int] = {
    "breach_run_count": 2,  # ≥ N recent staging-bar breaches → consider re-enabling soft-gate
}

# Named profiles for Preferred S14 performance bar. Env overrides always win.
LOCUST_PROFILES: dict[str, dict[str, float | int | str]] = {
    "default": {
        "p95_response_ms": 500,
        "error_rate_pct": 1.0,
        "users": 20,
        "spawn_rate": 5,
        "run_time": "60s",
    },
    # Staging profile = capacity-plan load shape + documented load-test SLO thresholds.
    "staging": {
        "p95_response_ms": 500,
        "error_rate_pct": 1.0,
        "users": 20,
        "spawn_rate": 5,
        "run_time": "60s",
    },
    # CI smoke: keep the pipeline green on noisy GHA runners; soft-gate uses staging.
    "ci": {
        "p95_response_ms": 10000,
        "error_rate_pct": 3.0,
        "users": 20,
        "spawn_rate": 5,
        "run_time": "60s",
    },
}


def truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def resolve_perf_thresholds(
    profile: str | None = None,
    *,
    p95_override: str | None = None,
    error_rate_override: str | None = None,
) -> dict[str, float | int | str]:
    """Resolve thresholds for LOCUST_PROFILE with optional env overrides."""
    name = (profile or os.environ.get("LOCUST_PROFILE") or "default").strip().lower()
    if name not in LOCUST_PROFILES:
        logger.warning("Unknown LOCUST_PROFILE=%s — falling back to default", name)
        name = "default"
    resolved = dict(LOCUST_PROFILES[name])
    resolved["profile"] = name

    p95_raw = p95_override if p95_override is not None else os.environ.get("LOCUST_P95_MS")
    err_raw = error_rate_override if error_rate_override is not None else os.environ.get("LOCUST_ERROR_RATE_PCT")
    if p95_raw not in (None, ""):
        resolved["p95_response_ms"] = int(p95_raw)
    if err_raw not in (None, ""):
        resolved["error_rate_pct"] = float(err_raw)
    return resolved


def build_trend_record(payload: dict) -> dict:
    """Build a single-run trend snapshot for Preferred S14 soft-gate artifacts."""
    return {
        "schema": "locust-soft-gate-trend/v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "github": {
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "sha": os.environ.get("GITHUB_SHA"),
            "ref": os.environ.get("GITHUB_REF"),
            "workflow": os.environ.get("GITHUB_WORKFLOW"),
            "repository": os.environ.get("GITHUB_REPOSITORY"),
        },
        "result": {
            "profile": payload["profile"],
            "soft_gate": payload["soft_gate"],
            "overall": payload["overall"],
            "p95_ms": payload["p95_ms"],
            "p95_limit_ms": payload["p95_limit_ms"],
            "p95_status": payload["p95_status"],
            "error_rate_pct": payload["error_rate_pct"],
            "error_rate_limit_pct": payload["error_rate_limit_pct"],
            "error_status": payload["error_status"],
            "num_requests": payload["num_requests"],
            "num_failures": payload.get("num_failures"),
            "breaches": list(payload.get("breaches") or []),
        },
    }


def _trend_result(record: dict) -> dict:
    """Accept full trend records or flattened result dicts."""
    if isinstance(record.get("result"), dict):
        return record["result"]
    return record


def evaluate_sustained_scale_hints(trend_records: list[dict]) -> dict:
    """Evaluate successive soft-gate trend records against QUEUE_DEPTH_SCALE_HINTS.

    Advisory only — never changes Locust exit codes or CI merge gates.
    Uses the most recent ``sustained_run_count`` records (newest last).
    """
    required = int(QUEUE_DEPTH_SCALE_HINTS["sustained_run_count"])
    p95_mult = float(QUEUE_DEPTH_SCALE_HINTS["p95_breach_multiplier"])
    err_mult = float(QUEUE_DEPTH_SCALE_HINTS["error_rate_breach_multiplier"])
    staging_p95 = int(LOCUST_PROFILES["staging"]["p95_response_ms"])
    staging_err = float(LOCUST_PROFILES["staging"]["error_rate_pct"])
    p95_hint_limit = staging_p95 * p95_mult
    err_hint_limit = staging_err * err_mult

    window = list(trend_records[-required:]) if trend_records else []
    enough = len(window) >= required
    actions: list[str] = []

    if not enough:
        actions.append(
            f"Collect ≥{required} trend records before applying sustained scale hints " f"(have {len(window)})."
        )
        return {
            "schema": "locust-soft-gate-scale-hint/v1",
            "window_size": len(window),
            "required_runs": required,
            "enough_runs": False,
            "p95_hint_limit_ms": p95_hint_limit,
            "error_rate_hint_limit_pct": err_hint_limit,
            "p95_scale_hint": False,
            "error_rate_scale_hint": False,
            "actions": actions,
        }

    p95_scale = all(float(_trend_result(r).get("p95_ms") or 0) > p95_hint_limit for r in window)
    err_scale = all(float(_trend_result(r).get("error_rate_pct") or 0) > err_hint_limit for r in window)
    if p95_scale:
        actions.append(
            f"Sustained p95 > {p95_hint_limit:.0f} ms across {required} runs — "
            "investigate hotspots / consider App Service scale-out."
        )
    if err_scale:
        actions.append(
            f"Sustained error rate > {err_hint_limit:.1f}% across {required} runs — "
            "check dependency/DB pool saturation before raising instance count."
        )
    if not actions:
        actions.append("No sustained scale hint — keep observing under soft-gate.")

    return {
        "schema": "locust-soft-gate-scale-hint/v1",
        "window_size": len(window),
        "required_runs": required,
        "enough_runs": True,
        "p95_hint_limit_ms": p95_hint_limit,
        "error_rate_hint_limit_pct": err_hint_limit,
        "p95_scale_hint": p95_scale,
        "error_rate_scale_hint": err_scale,
        "actions": actions,
    }


def evaluate_trial_tighten_readiness(trend_records: list[dict]) -> dict:
    """Decide whether soft-gate trends are stable enough to trial a tighter p95.

    Advisory only — never changes Locust exit codes, workflow YAML, or profiles.
    Ready when the last ``stable_run_count`` runs are all under the current
    staging p95 / error-rate bars (so operators may trial ``LOCUST_P95_MS=350``
    with ``LOCUST_SOFT_GATE=1`` still on).
    """
    required = int(SOFT_GATE_TRIAL_TIGHTEN["stable_run_count"])
    trial_p95 = int(SOFT_GATE_TRIAL_TIGHTEN["p95_response_ms"])
    trial_err = float(SOFT_GATE_TRIAL_TIGHTEN["error_rate_pct"])
    staging_p95 = int(LOCUST_PROFILES["staging"]["p95_response_ms"])
    staging_err = float(LOCUST_PROFILES["staging"]["error_rate_pct"])

    window = list(trend_records[-required:]) if trend_records else []
    enough = len(window) >= required
    actions: list[str] = []

    if not enough:
        actions.append(
            f"Collect ≥{required} soft-gate trend records under the staging bar "
            f"before trialling LOCUST_P95_MS={trial_p95} (have {len(window)})."
        )
        return {
            "schema": "locust-soft-gate-trial-tighten/v1",
            "window_size": len(window),
            "required_runs": required,
            "enough_runs": False,
            "staging_p95_limit_ms": staging_p95,
            "staging_error_rate_limit_pct": staging_err,
            "trial_p95_ms": trial_p95,
            "trial_error_rate_pct": trial_err,
            "stable_under_staging_bar": False,
            "ready_for_trial_tighten": False,
            "actions": actions,
        }

    stable = all(
        float(_trend_result(r).get("p95_ms") or 0) <= staging_p95
        and float(_trend_result(r).get("error_rate_pct") or 0) <= staging_err
        for r in window
    )
    if stable:
        actions.append(
            f"Staging bar stable across {required} runs — trial "
            f"LOCUST_P95_MS={trial_p95} with LOCUST_SOFT_GATE=1 still on "
            "(do not tighten the blocking ci profile)."
        )
    else:
        actions.append(
            "Not ready for trial tighten — keep observing until p95/error rate "
            f"stay ≤ staging bar ({staging_p95} ms / {staging_err}%) across "
            f"{required} recent runs."
        )

    return {
        "schema": "locust-soft-gate-trial-tighten/v1",
        "window_size": len(window),
        "required_runs": required,
        "enough_runs": True,
        "staging_p95_limit_ms": staging_p95,
        "staging_error_rate_limit_pct": staging_err,
        "trial_p95_ms": trial_p95,
        "trial_error_rate_pct": trial_err,
        "stable_under_staging_bar": stable,
        "ready_for_trial_tighten": stable,
        "actions": actions,
    }


def evaluate_hard_gate_promotion_readiness(trend_records: list[dict]) -> dict:
    """Decide whether soft-gate trends are stable enough to consider a hard gate.

    Advisory only — never changes Locust exit codes, workflow YAML, branch
    protection, or profiles. Ready when the last ``stable_run_count`` runs are
    all under the staging bar **and** p95 stays within the documented headroom
    fraction (low false-positive margin on GHA runners).
    """
    required = int(SOFT_GATE_HARD_GATE_PROMOTE["stable_run_count"])
    headroom = float(SOFT_GATE_HARD_GATE_PROMOTE["p95_headroom_fraction"])
    staging_p95 = int(LOCUST_PROFILES["staging"]["p95_response_ms"])
    staging_err = float(LOCUST_PROFILES["staging"]["error_rate_pct"])
    p95_headroom_limit = staging_p95 * headroom

    window = list(trend_records[-required:]) if trend_records else []
    enough = len(window) >= required
    actions: list[str] = []

    if not enough:
        actions.append(
            f"Collect ≥{required} soft-gate trend records under the staging bar "
            f"before considering hard-gate promotion (have {len(window)})."
        )
        return {
            "schema": "locust-soft-gate-hard-gate-ready/v1",
            "window_size": len(window),
            "required_runs": required,
            "enough_runs": False,
            "staging_p95_limit_ms": staging_p95,
            "staging_error_rate_limit_pct": staging_err,
            "p95_headroom_limit_ms": p95_headroom_limit,
            "stable_under_staging_bar": False,
            "within_p95_headroom": False,
            "ready_for_hard_gate_promotion": False,
            "actions": actions,
        }

    stable = all(
        float(_trend_result(r).get("p95_ms") or 0) <= staging_p95
        and float(_trend_result(r).get("error_rate_pct") or 0) <= staging_err
        for r in window
    )
    within_headroom = all(float(_trend_result(r).get("p95_ms") or 0) <= p95_headroom_limit for r in window)
    ready = stable and within_headroom

    if ready:
        actions.append(
            f"Staging bar stable across {required} runs with p95 ≤ "
            f"{p95_headroom_limit:.0f} ms headroom — consider dropping "
            "LOCUST_SOFT_GATE / requiring the soft-gate check (keep the relaxed "
            "ci profile for smoke-only runs)."
        )
    else:
        if not stable:
            actions.append(
                "Not ready for hard-gate promotion — keep observing until "
                f"p95/error rate stay ≤ staging bar ({staging_p95} ms / "
                f"{staging_err}%) across {required} recent runs."
            )
        elif not within_headroom:
            actions.append(
                "Not ready for hard-gate promotion — p95 must stay ≤ "
                f"{p95_headroom_limit:.0f} ms ({headroom:.0%} of staging bar) "
                f"across {required} runs for a low false-positive margin."
            )

    return {
        "schema": "locust-soft-gate-hard-gate-ready/v1",
        "window_size": len(window),
        "required_runs": required,
        "enough_runs": True,
        "staging_p95_limit_ms": staging_p95,
        "staging_error_rate_limit_pct": staging_err,
        "p95_headroom_limit_ms": p95_headroom_limit,
        "stable_under_staging_bar": stable,
        "within_p95_headroom": within_headroom,
        "ready_for_hard_gate_promotion": ready,
        "actions": actions,
    }


def evaluate_soft_gate_reenable_readiness(trend_records: list[dict]) -> dict:
    """Decide whether repeated staging-bar breaches warrant soft-gate re-enable.

    Advisory only — never changes Locust exit codes, workflow YAML, branch
    protection, or profiles. Ready when the last ``breach_run_count`` runs all
    exceed the staging p95 **or** error-rate bar (false-positive / capacity
    noise after a hard-gate promote). Operators may then re-set
    ``LOCUST_SOFT_GATE=1`` and drop hard-gate branch protection.
    """
    required = int(SOFT_GATE_REENABLE["breach_run_count"])
    staging_p95 = int(LOCUST_PROFILES["staging"]["p95_response_ms"])
    staging_err = float(LOCUST_PROFILES["staging"]["error_rate_pct"])

    window = list(trend_records[-required:]) if trend_records else []
    enough = len(window) >= required
    actions: list[str] = []

    if not enough:
        actions.append(
            f"Collect ≥{required} soft-gate trend records before considering "
            f"soft-gate re-enable / hard-gate demote (have {len(window)})."
        )
        return {
            "schema": "locust-soft-gate-reenable/v1",
            "window_size": len(window),
            "required_runs": required,
            "enough_runs": False,
            "staging_p95_limit_ms": staging_p95,
            "staging_error_rate_limit_pct": staging_err,
            "sustained_staging_breaches": False,
            "ready_for_soft_gate_reenable": False,
            "actions": actions,
        }

    def _breaches_staging(record: dict) -> bool:
        result = _trend_result(record)
        return float(result.get("p95_ms") or 0) > staging_p95 or float(result.get("error_rate_pct") or 0) > staging_err

    sustained = all(_breaches_staging(r) for r in window)
    if sustained:
        actions.append(
            f"Staging bar breached across {required} recent runs — consider "
            "re-enabling LOCUST_SOFT_GATE=1 and removing any hard-gate branch "
            "protection requirement until trends stabilize again."
        )
    else:
        actions.append(
            "Not ready for soft-gate re-enable — keep the current gate posture "
            f"until p95/error rate exceed the staging bar ({staging_p95} ms / "
            f"{staging_err}%) across {required} recent runs."
        )

    return {
        "schema": "locust-soft-gate-reenable/v1",
        "window_size": len(window),
        "required_runs": required,
        "enough_runs": True,
        "staging_p95_limit_ms": staging_p95,
        "staging_error_rate_limit_pct": staging_err,
        "sustained_staging_breaches": sustained,
        "ready_for_soft_gate_reenable": sustained,
        "actions": actions,
    }


def write_soft_gate_summary(payload: dict) -> None:
    """Emit a human + machine readable soft-gate summary for CI artifacts."""
    lines = [
        "### Locust soft-gate summary (Preferred S14 staging profile)",
        "",
        f"- **Profile:** `{payload['profile']}`",
        f"- **Soft-gate:** `{'on' if payload['soft_gate'] else 'off'}`",
        f"- **Requests:** {payload['num_requests']}",
        f"- **p95:** {payload['p95_ms']:.0f} ms "
        f"(limit ≤ {payload['p95_limit_ms']} ms) — **{payload['p95_status']}**",
        f"- **Error rate:** {payload['error_rate_pct']:.2f}% "
        f"(limit ≤ {payload['error_rate_limit_pct']}%) — **{payload['error_status']}**",
        f"- **Overall:** **{payload['overall']}**",
        "",
    ]
    if payload["breaches"]:
        lines.append("**Breaches:**")
        for breach in payload["breaches"]:
            lines.append(f"- {breach}")
        lines.append("")
    if payload["soft_gate"] and payload["overall"] == "BREACH":
        lines.append(
            "_Soft-gate mode: breach is reported but does not fail the job "
            "(exit 0). Promote to hard-gate once staging p95 is stable._"
        )
        lines.append("")

    text = "\n".join(lines)
    print(text)

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fh:
            fh.write(text)

    out_dir = Path(os.environ.get("LOCUST_SUMMARY_DIR", "."))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "locust-soft-gate-summary.md").write_text(text, encoding="utf-8")
    (out_dir / "locust-soft-gate-summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    trend = build_trend_record(payload)
    (out_dir / "locust-soft-gate-trend.json").write_text(json.dumps(trend, indent=2) + "\n", encoding="utf-8")
