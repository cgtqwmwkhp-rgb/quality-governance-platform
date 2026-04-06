#!/usr/bin/env python3
"""Admin CLI for Quality Governance Platform operations.

Usage:
    python scripts/admin_cli.py health
    python scripts/admin_cli.py db-status
    python scripts/admin_cli.py feature-flags
    python scripts/admin_cli.py migration-status
    python scripts/admin_cli.py config-check
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path


def cmd_health(args: argparse.Namespace) -> int:
    """Check platform health endpoints."""
    base = args.url.rstrip("/")
    endpoints = ["/healthz", "/readyz", "/api/v1/meta/version"]
    all_ok = True

    for ep in endpoints:
        url = f"{base}{ep}"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                status = "OK" if resp.status == 200 else f"WARN ({resp.status})"
                print(f"  [{status}] {ep}")
                if args.verbose:
                    print(f"         {json.dumps(data, indent=2)}")
        except Exception as exc:
            print(f"  [FAIL] {ep} — {exc}")
            all_ok = False

    return 0 if all_ok else 1


def cmd_db_status(args: argparse.Namespace) -> int:
    """Show Alembic migration status."""
    try:
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        print("Current migration head:")
        print(f"  {result.stdout.strip()}")
        if result.returncode != 0:
            print(f"  stderr: {result.stderr.strip()}")
        return result.returncode
    except FileNotFoundError:
        print("  alembic not found — install with: pip install alembic")
        return 1


def cmd_feature_flags(args: argparse.Namespace) -> int:
    """List feature flags via API."""
    base = args.url.rstrip("/")
    url = f"{base}/api/v1/feature-flags"
    try:
        req = urllib.request.Request(url, method="GET")
        if args.token:
            req.add_header("Authorization", f"Bearer {args.token}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                for flag in data:
                    name = flag.get("name", "unknown")
                    enabled = flag.get("enabled", False)
                    status = "ON" if enabled else "OFF"
                    print(f"  [{status}] {name}")
            else:
                print(json.dumps(data, indent=2))
        return 0
    except Exception as exc:
        print(f"  Failed to fetch flags: {exc}")
        return 1


def cmd_migration_status(args: argparse.Namespace) -> int:
    """Count and list recent Alembic migrations."""
    versions_dir = Path("alembic/versions")
    if not versions_dir.exists():
        print("  alembic/versions/ not found")
        return 1

    migrations = sorted(versions_dir.glob("*.py"))
    migrations = [m for m in migrations if m.name != "__init__.py"]
    print(f"  Total migrations: {len(migrations)}")
    print(f"  Latest 5:")
    for m in migrations[-5:]:
        print(f"    {m.name}")
    return 0


def cmd_config_check(args: argparse.Namespace) -> int:
    """Verify .env.example vs required config."""
    env_example = Path(".env.example")
    if not env_example.exists():
        print("  .env.example not found")
        return 1

    lines = env_example.read_text().splitlines()
    vars_found = [l.split("=")[0].strip() for l in lines if "=" in l and not l.strip().startswith("#")]
    print(f"  Environment variables in .env.example: {len(vars_found)}")

    env_file = Path(".env")
    if env_file.exists():
        env_lines = env_file.read_text().splitlines()
        env_vars = {l.split("=")[0].strip() for l in env_lines if "=" in l and not l.strip().startswith("#")}
        missing = [v for v in vars_found if v not in env_vars]
        if missing:
            print(f"  Missing from .env: {', '.join(missing[:10])}")
        else:
            print("  All .env.example vars present in .env")
    else:
        print("  .env not found (expected in development)")

    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    """Print recent structured log entries from local or Docker."""
    tail_count = getattr(args, "tail", 100)

    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", str(tail_count), "qgp-app"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
            return 0
        print(f"  Docker container 'qgp-app' not running: {result.stderr.strip()}")
    except FileNotFoundError:
        print("  Docker not found on PATH")
    except subprocess.TimeoutExpired:
        print("  Docker logs timed out")

    log_file = Path("logs/app.log")
    if log_file.exists():
        lines = log_file.read_text().splitlines()
        for line in lines[-tail_count:]:
            print(line)
        return 0

    print("  No local log source available.")
    print("  Azure Monitor KQL queries: docs/ops/kql-queries.md")
    print("  Local Docker: docker logs -f qgp-app --tail 100")
    return 1


def cmd_cache_stats(args: argparse.Namespace) -> int:
    """Print Redis cache statistics."""
    import os

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    print(f"  Redis URL: {redis_url}")
    try:
        import redis

        r = redis.from_url(redis_url, socket_connect_timeout=3)
        dbsize = r.dbsize()
        info = r.info(section="memory")
        print(f"  Connection: OK")
        print(f"  DBSIZE (keys): {dbsize}")
        print(f"  Used memory: {info.get('used_memory_human', 'unknown')}")
        print(f"  Peak memory: {info.get('used_memory_peak_human', 'unknown')}")
        r.close()
    except ImportError:
        print("  redis package not installed — pip install redis")
    except Exception as exc:
        print(f"  Connection failed: {exc}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Quality Governance Platform Admin CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--token", default=None, help="Bearer token for authenticated endpoints")
    parser.add_argument("--verbose", "-v", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("health", help="Check health endpoints")
    sub.add_parser("db-status", help="Show current Alembic migration")
    sub.add_parser("feature-flags", help="List feature flags")
    sub.add_parser("migration-status", help="Count and list migrations")
    sub.add_parser("config-check", help="Verify environment config")
    logs_parser = sub.add_parser("logs", help="Show recent log entries")
    logs_parser.add_argument("--tail", type=int, default=100, help="Number of lines to show")
    sub.add_parser("cache-stats", help="Show Redis cache statistics")

    args = parser.parse_args()
    commands = {
        "health": cmd_health,
        "db-status": cmd_db_status,
        "feature-flags": cmd_feature_flags,
        "migration-status": cmd_migration_status,
        "config-check": cmd_config_check,
        "logs": cmd_logs,
        "cache-stats": cmd_cache_stats,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
