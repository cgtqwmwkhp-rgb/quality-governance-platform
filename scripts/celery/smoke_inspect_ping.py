#!/usr/bin/env python3
"""Fail-closed Celery worker smoke: require at least one inspect ping pong."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Repo root on sys.path so CI runners can import `src` without PYTHONPATH.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--retries", type=int, default=6)
    parser.add_argument("--sleep", type=float, default=5.0)
    parser.add_argument("--allow-missing", action="store_true",
                        help="Exit 0 with warning when no workers reply (pre-provision).")
    args = parser.parse_args()

    # Ensure broker env is present before importing celery_app (strict in staging/prod).
    for key in ("CELERY_BROKER_URL", "REDIS_URL"):
        if os.environ.get(key):
            break
    else:
        print("ERROR: CELERY_BROKER_URL or REDIS_URL required", file=sys.stderr)
        return 2

    if not os.environ.get("CELERY_BROKER_URL") and os.environ.get("REDIS_URL"):
        os.environ["CELERY_BROKER_URL"] = os.environ["REDIS_URL"]
    if not os.environ.get("CELERY_RESULT_BACKEND"):
        os.environ["CELERY_RESULT_BACKEND"] = os.environ.get(
            "CELERY_BROKER_URL", os.environ.get("REDIS_URL", "")
        )

    from src.infrastructure.tasks.celery_app import celery_app

    last_error = None
    for attempt in range(1, args.retries + 1):
        try:
            inspector = celery_app.control.inspect(timeout=args.timeout)
            ping = inspector.ping() or {}
            if ping:
                print(json.dumps({"ok": True, "attempt": attempt, "workers": ping}, indent=2))
                return 0
            last_error = "no workers replied to ping"
            print(f"attempt {attempt}/{args.retries}: {last_error}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — smoke surface
            last_error = str(exc)
            print(f"attempt {attempt}/{args.retries}: {last_error}", file=sys.stderr)
        time.sleep(args.sleep)

    payload = {"ok": False, "error": last_error}
    print(json.dumps(payload, indent=2))
    if args.allow_missing:
        print("WARNING: Celery workers not reachable; allow_missing=1", file=sys.stderr)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
