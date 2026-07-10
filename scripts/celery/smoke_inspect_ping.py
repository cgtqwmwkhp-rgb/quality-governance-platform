#!/usr/bin/env python3
"""Fail-closed Celery worker smoke: require at least one inspect ping pong.

Uses a lightweight Celery client (broker URL only) so CI runners do not need
the full app dependency tree (SQLAlchemy, etc.).
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _normalize_redis_ssl_url(url: str) -> str:
    if urlsplit(url).scheme.lower() != "rediss":
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if "ssl_cert_reqs" in query:
        return url
    query["ssl_cert_reqs"] = "CERT_REQUIRED"
    return urlunsplit(parts._replace(query=urlencode(query)))


def _redis_ssl_options(url: str) -> dict[str, Any] | None:
    if urlsplit(url).scheme.lower() != "rediss":
        return None
    return {"ssl_cert_reqs": ssl.CERT_REQUIRED}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--retries", type=int, default=6)
    parser.add_argument("--sleep", type=float, default=5.0)
    args = parser.parse_args()

    broker = (os.environ.get("CELERY_BROKER_URL") or os.environ.get("REDIS_URL") or "").strip()
    if not broker:
        print("ERROR: CELERY_BROKER_URL or REDIS_URL required", file=sys.stderr)
        return 2

    backend = (os.environ.get("CELERY_RESULT_BACKEND") or broker).strip()
    broker = _normalize_redis_ssl_url(broker)
    backend = _normalize_redis_ssl_url(backend)

    try:
        from celery import Celery
    except ImportError:
        print(
            "ERROR: celery package required. In CI: pip install 'celery[redis]' redis",
            file=sys.stderr,
        )
        return 2

    app = Celery("qgp_smoke_inspect", broker=broker, backend=backend)
    conf: dict[str, Any] = {}
    broker_ssl = _redis_ssl_options(broker)
    backend_ssl = _redis_ssl_options(backend)
    if broker_ssl:
        conf["broker_use_ssl"] = broker_ssl
    if backend_ssl:
        conf["redis_backend_use_ssl"] = backend_ssl
    if conf:
        app.conf.update(conf)

    last_error = None
    for attempt in range(1, args.retries + 1):
        try:
            inspector = app.control.inspect(timeout=args.timeout)
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

    print(json.dumps({"ok": False, "error": last_error}, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
