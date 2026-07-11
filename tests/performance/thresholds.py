"""Locust performance profiles and soft-gate threshold helpers (no Locust import)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

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
