#!/usr/bin/env python3
"""
Environment Sync Verification Script.

Verifies that staging and production are running the same build SHA.

Usage:
    python scripts/verify_env_sync.py --staging-url URL --prod-url URL [--expected-sha SHA]

Exit codes:
    0: Environments are in sync
    1: Environments are NOT in sync
    2: Error fetching build info
"""

import argparse
import json
import sys
from urllib.error import URLError
from urllib.request import urlopen


def fetch_build_sha(base_url: str) -> tuple[str, bool]:
    """
    Fetch build_sha from /api/v1/meta/version endpoint.

    Returns:
        (build_sha, success)
    """
    url = f"{base_url.rstrip('/')}/api/v1/meta/version"
    try:
        with urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data.get("build_sha", ""), True
    except URLError as e:
        print(f"ERROR: Failed to fetch from {url}: {e}")
        return "", False
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON from {url}: {e}")
        return "", False


def fetch_health(base_url: str, endpoint: str) -> tuple[int, bool]:
    """
    Fetch health endpoint status.

    Returns:
        (status_code, is_healthy)
    """
    url = f"{base_url.rstrip('/')}/{endpoint}"
    try:
        with urlopen(url, timeout=10) as response:
            return response.status, response.status == 200
    except URLError as e:
        print(f"ERROR: Health check failed for {url}: {e}")
        return 0, False


def main():
    parser = argparse.ArgumentParser(description="Verify staging and production environment sync")
    parser.add_argument("--staging-url", required=True, help="Staging environment URL")
    parser.add_argument("--prod-url", required=True, help="Production environment URL")
    parser.add_argument("--expected-sha", help="Expected git SHA (optional)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Fetch staging info
    staging_sha, staging_ok = fetch_build_sha(args.staging_url)
    staging_health, staging_healthy = fetch_health(args.staging_url, "healthz")
    staging_ready_status, staging_ready = fetch_health(args.staging_url, "readyz")

    # Fetch production info
    prod_sha, prod_ok = fetch_build_sha(args.prod_url)
    prod_health, prod_healthy = fetch_health(args.prod_url, "healthz")
    prod_ready_status, prod_ready = fetch_health(args.prod_url, "readyz")

    # Check sync
    shas_match = staging_sha == prod_sha and staging_ok and prod_ok
    expected_match = True
    if args.expected_sha:
        expected_match = staging_sha == args.expected_sha and prod_sha == args.expected_sha

    all_healthy = staging_healthy and prod_healthy and staging_ready and prod_ready
    sync_ok = shas_match and expected_match and all_healthy

    result = {
        "sync_status": "PASS" if sync_ok else "FAIL",
        "staging": {
            "url": args.staging_url,
            "build_sha": staging_sha,
            "healthz": staging_healthy,
            "readyz": staging_ready,
            "fetch_ok": staging_ok,
        },
        "production": {
            "url": args.prod_url,
            "build_sha": prod_sha,
            "healthz": prod_healthy,
            "readyz": prod_ready,
            "fetch_ok": prod_ok,
        },
        "shas_match": shas_match,
        "expected_sha": args.expected_sha,
        "expected_match": expected_match if args.expected_sha else None,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=" * 60)
        print("ENVIRONMENT SYNC VERIFICATION")
        print("=" * 60)
        print()
        print("| Environment | build_sha | healthz | readyz | fetch_ok |")
        print("|-------------|-----------|---------|--------|----------|")
        print(
            f"| Staging     | {staging_sha[:12] if staging_sha else 'N/A':12} | "
            f"{'✅' if staging_healthy else '❌':7} | "
            f"{'✅' if staging_ready else '❌':6} | "
            f"{'✅' if staging_ok else '❌':8} |"
        )
        print(
            f"| Production  | {prod_sha[:12] if prod_sha else 'N/A':12} | "
            f"{'✅' if prod_healthy else '❌':7} | "
            f"{'✅' if prod_ready else '❌':6} | "
            f"{'✅' if prod_ok else '❌':8} |"
        )
        print()
        print(f"SHAs Match: {'✅ YES' if shas_match else '❌ NO'}")
        if args.expected_sha:
            print(f"Expected SHA: {args.expected_sha}")
            print(f"Expected Match: {'✅ YES' if expected_match else '❌ NO'}")
        print()
        print(f"Overall: {'✅ PASS - Environments are in sync' if sync_ok else '❌ FAIL - Environments NOT in sync'}")
        print("=" * 60)

    # Exit code
    if not staging_ok or not prod_ok:
        sys.exit(2)
    if not sync_ok:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
