#!/usr/bin/env python3
"""
Post-Deploy Runtime Smoke Check

Verifies production/staging deployments are healthy after deploy:
1. build_sha matches expected commit
2. CORS preflight works on key endpoints
3. PlanetMark dashboard returns 200
4. UVDB sections returns 200

Usage:
    python scripts/smoke/post_deploy_check.py --url https://app-qgp-prod.azurewebsites.net --sha abc123
    python scripts/smoke/post_deploy_check.py --url $STAGING_URL --sha $GITHUB_SHA

Exit codes:
    0 = All checks passed
    1 = One or more checks failed
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Optional

import requests

# Constants
TIMEOUT_SECONDS = 10
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 2

# Production SWA origin for CORS checks
CORS_ORIGIN = "https://purple-water-03205fa03.6.azurestaticapps.net"


@dataclass
class CheckResult:
    """Result of a single check."""

    name: str
    endpoint: str
    expected: str
    observed: str
    latency_ms: int
    passed: bool
    error: Optional[str] = None


def check_build_sha(base_url: str, expected_sha: str) -> CheckResult:
    """Verify deployed build_sha matches expected commit."""
    endpoint = "/api/v1/meta/version"
    url = f"{base_url}{endpoint}"

    start = time.time()
    try:
        resp = requests.get(url, timeout=TIMEOUT_SECONDS)
        latency_ms = int((time.time() - start) * 1000)

        if resp.status_code != 200:
            return CheckResult(
                name="build_sha",
                endpoint=endpoint,
                expected=f"200, sha={expected_sha[:8]}",
                observed=f"{resp.status_code}",
                latency_ms=latency_ms,
                passed=False,
                error=f"HTTP {resp.status_code}",
            )

        data = resp.json()
        actual_sha = data.get("build_sha", "")

        # Allow prefix match for short SHA
        if expected_sha and not actual_sha.startswith(expected_sha[:7]):
            return CheckResult(
                name="build_sha",
                endpoint=endpoint,
                expected=expected_sha[:8],
                observed=actual_sha[:8],
                latency_ms=latency_ms,
                passed=False,
                error="SHA mismatch",
            )

        return CheckResult(
            name="build_sha",
            endpoint=endpoint,
            expected=expected_sha[:8] if expected_sha else "any",
            observed=actual_sha[:8],
            latency_ms=latency_ms,
            passed=True,
        )

    except Exception as e:
        return CheckResult(
            name="build_sha",
            endpoint=endpoint,
            expected=f"200, sha={expected_sha[:8]}",
            observed="error",
            latency_ms=0,
            passed=False,
            error=str(e),
        )


def check_cors_preflight(base_url: str, endpoint: str) -> CheckResult:
    """Verify CORS preflight returns 200 with correct headers."""
    url = f"{base_url}{endpoint}"

    start = time.time()
    try:
        resp = requests.options(
            url,
            headers={
                "Origin": CORS_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
            timeout=TIMEOUT_SECONDS,
        )
        latency_ms = int((time.time() - start) * 1000)

        if resp.status_code != 200:
            return CheckResult(
                name=f"cors_preflight_{endpoint.split('/')[-1]}",
                endpoint=f"OPTIONS {endpoint}",
                expected="200 + CORS headers",
                observed=f"{resp.status_code}",
                latency_ms=latency_ms,
                passed=False,
                error=f"HTTP {resp.status_code}",
            )

        allow_origin = resp.headers.get("access-control-allow-origin", "")
        if allow_origin != CORS_ORIGIN:
            return CheckResult(
                name=f"cors_preflight_{endpoint.split('/')[-1]}",
                endpoint=f"OPTIONS {endpoint}",
                expected=f"ACAO: {CORS_ORIGIN}",
                observed=f"ACAO: {allow_origin or 'missing'}",
                latency_ms=latency_ms,
                passed=False,
                error="Missing/wrong CORS header",
            )

        return CheckResult(
            name=f"cors_preflight_{endpoint.split('/')[-1]}",
            endpoint=f"OPTIONS {endpoint}",
            expected="200 + CORS",
            observed="200 + CORS",
            latency_ms=latency_ms,
            passed=True,
        )

    except Exception as e:
        return CheckResult(
            name=f"cors_preflight_{endpoint.split('/')[-1]}",
            endpoint=f"OPTIONS {endpoint}",
            expected="200 + CORS",
            observed="error",
            latency_ms=0,
            passed=False,
            error=str(e),
        )


def check_endpoint_health(base_url: str, endpoint: str, name: str) -> CheckResult:
    """Verify endpoint returns 200."""
    url = f"{base_url}{endpoint}"

    for attempt in range(MAX_RETRIES):
        start = time.time()
        try:
            resp = requests.get(url, headers={"Origin": CORS_ORIGIN}, timeout=TIMEOUT_SECONDS)
            latency_ms = int((time.time() - start) * 1000)

            if resp.status_code == 200:
                return CheckResult(
                    name=name,
                    endpoint=endpoint,
                    expected="200",
                    observed="200",
                    latency_ms=latency_ms,
                    passed=True,
                )

            # Retry on 5xx
            if resp.status_code >= 500 and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
                continue

            return CheckResult(
                name=name,
                endpoint=endpoint,
                expected="200",
                observed=str(resp.status_code),
                latency_ms=latency_ms,
                passed=False,
                error=f"HTTP {resp.status_code}",
            )

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
                continue

            return CheckResult(
                name=name,
                endpoint=endpoint,
                expected="200",
                observed="error",
                latency_ms=0,
                passed=False,
                error=str(e),
            )

    # Should not reach here
    return CheckResult(
        name=name,
        endpoint=endpoint,
        expected="200",
        observed="unknown",
        latency_ms=0,
        passed=False,
        error="Max retries exceeded",
    )


def run_smoke_checks(base_url: str, expected_sha: str) -> list[CheckResult]:
    """Run all smoke checks and return results."""
    results = []

    # 1. Build SHA verification
    results.append(check_build_sha(base_url, expected_sha))

    # 2. CORS preflight checks
    results.append(check_cors_preflight(base_url, "/api/v1/planet-mark/dashboard"))
    results.append(check_cors_preflight(base_url, "/api/v1/uvdb/sections"))

    # 3. Endpoint health checks
    results.append(check_endpoint_health(base_url, "/api/v1/planet-mark/dashboard", "planetmark_dashboard"))
    results.append(check_endpoint_health(base_url, "/api/v1/uvdb/sections", "uvdb_sections"))

    return results


def print_results(results: list[CheckResult]) -> bool:
    """Print results table and return True if all passed."""
    print("\n" + "=" * 80)
    print("POST-DEPLOY SMOKE CHECK RESULTS")
    print("=" * 80)
    print(f"{'Check':<30} {'Endpoint':<30} {'Expected':<15} {'Observed':<15} {'Latency':<10} {'Status'}")
    print("-" * 80)

    all_passed = True
    for r in results:
        status = "✅ PASS" if r.passed else "❌ FAIL"
        if not r.passed:
            all_passed = False
        print(f"{r.name:<30} {r.endpoint:<30} {r.expected:<15} {r.observed:<15} {r.latency_ms:>6}ms   {status}")
        if r.error:
            print(f"{'':>30} Error: {r.error}")

    print("=" * 80)
    overall = "✅ ALL CHECKS PASSED" if all_passed else "❌ SOME CHECKS FAILED"
    print(f"Overall: {overall}")
    print("=" * 80 + "\n")

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Post-deploy runtime smoke check")
    parser.add_argument("--url", required=True, help="Base URL of the deployed API")
    parser.add_argument("--sha", default="", help="Expected build SHA (optional)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Remove trailing slash
    base_url = args.url.rstrip("/")

    print(f"\nRunning smoke checks against: {base_url}")
    if args.sha:
        print(f"Expected SHA: {args.sha[:8]}...")

    results = run_smoke_checks(base_url, args.sha)

    if args.json:
        output = {
            "url": base_url,
            "expected_sha": args.sha,
            "checks": [
                {
                    "name": r.name,
                    "endpoint": r.endpoint,
                    "expected": r.expected,
                    "observed": r.observed,
                    "latency_ms": r.latency_ms,
                    "passed": r.passed,
                    "error": r.error,
                }
                for r in results
            ],
            "all_passed": all(r.passed for r in results),
        }
        print(json.dumps(output, indent=2))
        sys.exit(0 if output["all_passed"] else 1)
    else:
        all_passed = print_results(results)
        sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
