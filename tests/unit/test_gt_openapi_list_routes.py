"""Golden-thread OpenAPI freeze — primary list/create routes must stay published.

D22 residual from golden-thread UAT: dual slash mounts hide the empty-string
alias with include_in_schema=False, but the canonical '/' (or non-slash) mount
must remain in the committed contract so partners and OpenAPI consumers see
intake → work → CAPA/risk list surfaces.
"""

from __future__ import annotations

import json
from pathlib import Path

BASELINE = Path("openapi-baseline.json")
CONTRACT = Path("docs/contracts/openapi.json")

# Canonical published paths (trailing slash where dual-mount publishes '/').
GT_LIST_PATHS: dict[str, set[str]] = {
    "/api/v1/actions/": {"get", "post"},
    "/api/v1/capa": {"get", "post"},
    "/api/v1/incidents/": {"get", "post"},
    "/api/v1/investigations/": {"get", "post"},
    "/api/v1/risk-register/": {"get", "post"},
    "/api/v1/near-misses/": {"get", "post"},
}

GT_SUPPORTING_PATHS = {
    "/api/v1/actions/view-counts": {"get"},
    "/api/v1/engineers/by-user/me": {"get"},
    "/api/v1/meta/ocr-providers": {"get"},
    "/api/v1/privacy/data-processing-register": {"get"},
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_openapi_baseline_matches_contracts_artifact():
    assert BASELINE.exists(), "openapi-baseline.json missing"
    assert CONTRACT.exists(), "docs/contracts/openapi.json missing"
    assert _load(BASELINE) == _load(CONTRACT)


def test_gt_list_routes_published_in_baseline():
    paths = _load(BASELINE).get("paths", {})
    for path, methods in GT_LIST_PATHS.items():
        assert path in paths, f"Missing golden-thread list path: {path}"
        present = {m for m in paths[path] if not m.startswith("x-")}
        assert methods.issubset(present), f"{path} expected methods {methods}, got {present}"


def test_gt_supporting_routes_published_in_baseline():
    paths = _load(BASELINE).get("paths", {})
    for path, methods in GT_SUPPORTING_PATHS.items():
        assert path in paths, f"Missing golden-thread supporting path: {path}"
        present = {m for m in paths[path] if not m.startswith("x-")}
        assert methods.issubset(present), f"{path} expected methods {methods}, got {present}"
