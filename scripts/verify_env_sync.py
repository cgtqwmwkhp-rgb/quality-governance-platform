#!/usr/bin/env python3
"""
Environment Sync Verification Script.

Two modes:
1. Build sync: Verifies that staging and production are running the same build SHA.
2. Env check: Validates .env against .env.example (all vars present, no placeholder secrets).

Usage:
    # Build sync (staging vs prod)
    python scripts/verify_env_sync.py --staging-url URL --prod-url URL [--expected-sha SHA]

    # Env file validation
    python scripts/verify_env_sync.py --check-env [--env-file .env] [--example .env.example]

Exit codes:
    0: Pass (sync OK or env check OK)
    1: Fail (environments NOT in sync, or env validation failed)
    2: Error (fetch error, or missing files)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

# Placeholder values that indicate secrets have not been configured
SECRET_PLACEHOLDERS = [
    "__CHANGE_ME__",
    "__change_me__",
    "change-me",
    "changeme",
    "change-me-in-production",
    "your-secret-key-here",
    "__YOUR_",
    "password",  # when used as literal DB password in DATABASE_URL
]

# Vars that must not have placeholder values (secrets)
SECRET_VARS = [
    "SECRET_KEY",
    "JWT_SECRET_KEY",
    "SMTP_PASSWORD",
    "EMAIL_PASSWORD",
    "AZURE_STORAGE_CONNECTION_STRING",
    "DATABASE_URL",
]

# Required vars that must be present in .env
REQUIRED_VARS = ["DATABASE_URL", "SECRET_KEY"]


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse .env file and return key -> value mapping (excluding comments/empties)."""
    result = {}
    if not path.exists():
        return result
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                result[key] = val
    return result


def check_env_sync(
    env_path: Path, example_path: Path
) -> tuple[bool, list[str], list[str], list[str]]:
    """
    Validate .env against .env.example.

    Returns:
        (ok, missing_vars, placeholder_secrets, missing_required)
    """
    env_vars = parse_env_file(env_path)
    example_vars = parse_env_file(example_path)
    example_keys = {k for k in example_vars if not k.startswith("VITE_")}
    # VITE_ vars are frontend-only, often in separate config
    backend_example_keys = {k for k in example_keys if not k.startswith("VITE_")}

    missing_in_env = []
    for key in backend_example_keys:
        if key not in env_vars:
            missing_in_env.append(key)
        elif env_vars[key] == "" and example_vars.get(key, "") != "":
            # Empty in .env but example has something - could be optional
            pass

    missing_required = [k for k in REQUIRED_VARS if k not in env_vars or not env_vars.get(k)]

    placeholder_secrets = []
    for key in SECRET_VARS:
        if key not in env_vars:
            continue
        val = env_vars[key]
        val_lower = val.lower()
        # Check DATABASE_URL for literal 'password' as placeholder (e.g. postgres:password@)
        if key == "DATABASE_URL":
            if re.search(r"://[^:]+:password@", val):
                placeholder_secrets.append(f"{key}=...password@... (placeholder)")
            continue
        for ph in SECRET_PLACEHOLDERS:
            if ph.lower() in val_lower:
                placeholder_secrets.append(f"{key}=... (placeholder)")
                break

    ok = (
        len(missing_in_env) == 0
        and len(placeholder_secrets) == 0
        and len(missing_required) == 0
    )
    return ok, missing_in_env, placeholder_secrets, missing_required


def run_check_env(env_path: Path, example_path: Path, json_output: bool) -> int:
    """Run env file validation. Returns exit code."""
    if not example_path.exists():
        print(f"ERROR: .env.example not found at {example_path}")
        return 2
    if not env_path.exists():
        print(f"ERROR: .env not found at {env_path}")
        return 2

    ok, missing, placeholders, missing_req = check_env_sync(env_path, example_path)

    result = {
        "env_check_status": "PASS" if ok else "FAIL",
        "missing_from_env": missing,
        "placeholder_secrets": placeholders,
        "missing_required": missing_req,
    }

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print("=" * 60)
        print("ENV FILE VALIDATION")
        print("=" * 60)
        print()
        if missing:
            print("Missing vars in .env (from .env.example):")
            for m in missing:
                print(f"  - {m}")
            print()
        if placeholders:
            print("Secrets with placeholder/default values:")
            for p in placeholders:
                print(f"  - {p}")
            print()
        if missing_req:
            print("Missing required vars:")
            for m in missing_req:
                print(f"  - {m}")
            print()
        status = "PASS" if ok else "FAIL"
        print(f"Overall: {'PASS' if ok else 'FAIL'}")
        print("=" * 60)

    return 0 if ok else 1


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
    parser = argparse.ArgumentParser(
        description="Verify staging/production sync or validate .env files"
    )
    parser.add_argument("--check-env", action="store_true", help="Validate .env vs .env.example")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to .env file (default: .env)",
    )
    parser.add_argument(
        "--example",
        default=".env.example",
        help="Path to .env.example file (default: .env.example)",
    )
    parser.add_argument("--staging-url", help="Staging environment URL")
    parser.add_argument("--prod-url", help="Production environment URL")
    parser.add_argument("--expected-sha", help="Expected git SHA (optional)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Resolve paths relative to project root (script lives in scripts/)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    if args.check_env:
        env_path = project_root / args.env_file
        example_path = project_root / args.example
        sys.exit(run_check_env(env_path, example_path, args.json))

    if not args.staging_url or not args.prod_url:
        parser.error("--staging-url and --prod-url are required when not using --check-env")

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
