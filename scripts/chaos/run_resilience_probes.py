#!/usr/bin/env python3
"""Chaos resilience probes for the Quality Governance Platform.

Runs a set of deterministic API resilience checks against a target environment.
Designed to run in CI (chaos-testing.yml) against staging.

Usage:
    CHAOS_TARGET_URL=https://staging.example.com python scripts/chaos/run_resilience_probes.py

Exit codes:
    0 — all probes passed
    1 — one or more probes failed
"""

from __future__ import annotations

import os
import sys
import json
import time
from typing import Any

import httpx

TARGET_URL = os.environ.get("CHAOS_TARGET_URL", "http://localhost:8000")

RESULTS: list[dict[str, Any]] = []


def probe(name: str, method: str, path: str, expected_status: set[int], **kwargs: Any) -> bool:
    """Run a single HTTP probe and record the result."""
    url = f"{TARGET_URL}{path}"
    start = time.monotonic()
    try:
        response = httpx.request(method, url, timeout=10.0, **kwargs)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        passed = response.status_code in expected_status
        RESULTS.append(
            {
                "probe": name,
                "url": url,
                "method": method,
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
                "passed": passed,
                "expected": sorted(expected_status),
            }
        )
        marker = "[OK]  " if passed else "[FAIL]"
        print(f"  {marker} {name}: HTTP {response.status_code} ({elapsed_ms}ms)")
        return passed
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        RESULTS.append(
            {
                "probe": name,
                "url": url,
                "method": method,
                "status": None,
                "elapsed_ms": elapsed_ms,
                "passed": False,
                "error": str(exc),
            }
        )
        print(f"  [FAIL] {name}: Exception — {exc}")
        return False


def run_all_probes() -> int:
    """Run all resilience probes. Returns number of failures."""
    print(f"\n=== Resilience Probes: {TARGET_URL} ===\n")

    failures = 0

    # Group 1: Health & readiness
    print("Group 1: Health & readiness endpoints")
    failures += 0 if probe("healthz", "GET", "/healthz", {200}) else 1
    failures += 0 if probe("readyz", "GET", "/readyz", {200, 503}) else 1
    failures += 0 if probe("version", "GET", "/api/v1/meta/version", {200}) else 1

    # Group 2: Auth boundary — unauthenticated access must return 401/403, not 500
    print("\nGroup 2: Auth boundary (expect 401/403, not 5xx)")
    protected = [
        "/api/v1/incidents/",
        "/api/v1/audits/",
        "/api/v1/risks/",
        "/api/v1/compliance/standards",
    ]
    for path in protected:
        passed = probe(f"auth-boundary:{path}", "GET", path, {401, 403, 422})
        failures += 0 if passed else 1

    # Group 3: Invalid input — must return 4xx, not 5xx
    print("\nGroup 3: Invalid input handling (expect 4xx, not 5xx)")
    failures += 0 if probe("invalid-uuid", "GET", "/api/v1/incidents/not-a-uuid", {401, 403, 404, 422}) else 1
    failures += 0 if probe("oversized-query", "GET", "/api/v1/incidents/?limit=999999", {200, 401, 403, 422}) else 1

    # Group 4: Response time SLO — health endpoint must respond < 500ms
    print("\nGroup 4: Response time SLO")
    slow_results = [r for r in RESULTS if r.get("probe", "").startswith("health") and r.get("elapsed_ms", 999) > 500]
    if slow_results:
        for r in slow_results:
            print(f"  [FAIL] SLO breach: {r['probe']} took {r['elapsed_ms']}ms (limit: 500ms)")
            failures += 1
    else:
        print("  [OK]   All health probes within 500ms SLO")

    # Summary
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["passed"])
    print(f"\n=== Results: {passed}/{total} probes passed, {failures} failures ===\n")

    # Write structured results
    output_path = "docs/evidence/chaos-runs"
    os.makedirs(output_path, exist_ok=True)
    with open(f"{output_path}/probe-results-latest.json", "w") as f:
        json.dump(
            {
                "target": TARGET_URL,
                "total": total,
                "passed": passed,
                "failures": failures,
                "probes": RESULTS,
            },
            f,
            indent=2,
        )

    return failures


if __name__ == "__main__":
    failure_count = run_all_probes()
    sys.exit(0 if failure_count == 0 else 1)
