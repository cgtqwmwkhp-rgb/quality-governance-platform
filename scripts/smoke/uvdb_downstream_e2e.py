#!/usr/bin/env python3
"""Smoke: UVDB / Planet Mark route registration (no DB seed required)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _paths(router) -> set[str]:
    return {getattr(route, "path", "") for route in router.routes if getattr(route, "path", None)}


def main() -> int:
    from src.api.routes.planet_mark import router as pm_router
    from src.api.routes.uvdb import router as uvdb_router

    uvdb = _paths(uvdb_router)
    pm = _paths(pm_router)
    checks = [
        ("uvdb.dashboard", any("/dashboard" in p for p in uvdb)),
        ("uvdb.audits", any("/audits" in p for p in uvdb)),
        ("uvdb.sections", any("/sections" in p for p in uvdb)),
        ("planet_mark.dashboard", any("/dashboard" in p for p in pm)),
        ("planet_mark.years", any("/years" in p for p in pm)),
    ]
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}: {name}")
    if failed:
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("uvdb_downstream_e2e: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
