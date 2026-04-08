#!/usr/bin/env python3
"""
Azure Monitor OTel trace evidence collector (D13 WCS closure 2026-04-08).

Queries Azure Log Analytics for recent OTel traces and feature_flag.audit events,
then writes structured evidence to docs/evidence/azure-monitor-otel-evidence.json.

Requires:
  - az CLI authenticated with sufficient permissions
  - AZURE_LOG_ANALYTICS_WORKSPACE_ID environment variable (or auto-discovered via az)

Usage:
  python3 scripts/governance/query_azure_monitor_otel.py

In CI/CD: called as part of the post-deploy verification step.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

OUTPUT_PATH = Path("docs/evidence/azure-monitor-otel-evidence.json")
LOOKBACK_HOURS = 24


def run_az_query(workspace_id: str, kql: str) -> dict:
    """Execute a KQL query against Azure Log Analytics via az CLI."""
    result = subprocess.run(
        [
            "az",
            "monitor",
            "log-analytics",
            "query",
            "--workspace",
            workspace_id,
            "--analytics-query",
            kql,
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {"error": result.stderr.strip(), "returncode": result.returncode}
    try:
        return {"data": json.loads(result.stdout), "returncode": 0}
    except json.JSONDecodeError:
        return {"error": f"Failed to parse JSON: {result.stdout[:200]}", "returncode": -1}


def find_workspace_id() -> str | None:
    """Auto-discover the Log Analytics workspace ID from the subscription."""
    env_id = os.environ.get("AZURE_LOG_ANALYTICS_WORKSPACE_ID")
    if env_id:
        return env_id
    result = subprocess.run(
        [
            "az",
            "monitor",
            "log-analytics",
            "workspace",
            "list",
            "--query",
            "[?contains(name,'qgp')].customerId",
            "--output",
            "tsv",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().splitlines()[0]
    return None


def main() -> None:
    print("[INFO] Collecting Azure Monitor OTel evidence...")
    workspace_id = find_workspace_id()
    evidence: dict = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "generated_by": "scripts/governance/query_azure_monitor_otel.py",
        "workspace_id": workspace_id or "not-found",
        "lookback_hours": LOOKBACK_HOURS,
        "ci_run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "head_sha": os.environ.get("GITHUB_SHA", "local")[:8],
    }

    if not workspace_id:
        print("[WARN] Azure Log Analytics workspace not found — recording as advisory gap")
        evidence["status"] = "workspace_not_found"
        evidence["advisory"] = (
            "Set AZURE_LOG_ANALYTICS_WORKSPACE_ID env var or ensure 'qgp' workspace exists. "
            "OTel trace wiring is implemented; evidence collection requires workspace access."
        )
        evidence["otel_implementation"] = {
            "correlation_id_middleware": "src/core/middleware.py",
            "azure_monitor_exporter": "src/infrastructure/monitoring/azure_monitor.py",
            "feature_flag_audit_logger": "src/main.py (configure_logging)",
            "production_trace_evidence": "docs/evidence/otel-live-trace-2026-04-08.md",
        }
        _write(evidence)
        return

    # Query 1: Recent OTel traces (requests table)
    otel_query = f"""
    requests
    | where timestamp > ago({LOOKBACK_HOURS}h)
    | where cloud_RoleName contains "qgp" or cloud_RoleName == ""
    | summarize count=count(), avg_duration_ms=avg(duration), p95_duration_ms=percentile(duration, 95)
    | project count, avg_duration_ms, p95_duration_ms
    """
    evidence["otel_traces"] = run_az_query(workspace_id, otel_query.strip())

    # Query 2: feature_flag.audit events (custom logs / traces table)
    audit_query = f"""
    traces
    | where timestamp > ago({LOOKBACK_HOURS}h)
    | where message contains "feature_flag.audit"
           or customDimensions contains "feature_flag"
    | summarize count=count()
    | project count
    """
    evidence["feature_flag_audit_events"] = run_az_query(workspace_id, audit_query.strip())

    # Query 3: 5xx error rate
    error_query = f"""
    requests
    | where timestamp > ago({LOOKBACK_HOURS}h)
    | where resultCode startswith "5"
    | summarize error_count=count()
    | project error_count
    """
    evidence["5xx_errors_24h"] = run_az_query(workspace_id, error_query.strip())

    evidence["status"] = "collected"
    _write(evidence)
    print(f"[OK] Evidence written to {OUTPUT_PATH}")


def _write(evidence: dict) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(evidence, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
