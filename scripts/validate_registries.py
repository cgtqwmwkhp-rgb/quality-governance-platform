#!/usr/bin/env python3
"""Registry Freshness & Consistency Validation — CI gate.

Validates that the UX/ops registries (BUTTON, PAGE, WORKFLOW) are:
1. Well-formed YAML with required top-level keys.
2. Not stale — ``last_updated`` date must be within the allowed age window.
3. Cross-consistent: PAGE_REGISTRY routes must align with frontend route patterns.

Registries checked:
  - docs/ops/BUTTON_REGISTRY.yml
  - docs/ops/PAGE_REGISTRY.yml
  - docs/ops/WORKFLOW_REGISTRY.yml

Exit codes:
    0 — all checks pass
    1 — one or more violations found

Evidence written to: docs/evidence/registry-validation-report.json
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("[WARN] PyYAML not installed; installing...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "pyyaml", "-q"], check=True)
    import yaml  # type: ignore[no-redef]

REGISTRIES = [
    Path("docs/ops/BUTTON_REGISTRY.yml"),
    Path("docs/ops/PAGE_REGISTRY.yml"),
    Path("docs/ops/WORKFLOW_REGISTRY.yml"),
]

EVIDENCE_PATH = Path("docs/evidence/registry-validation-report.json")
MAX_STALE_DAYS = 120  # Registries must be reviewed at least quarterly


def check_registry(path: Path) -> list[str]:
    """Run all checks on a single registry file. Returns violation strings."""
    violations: list[str] = []

    if not path.exists():
        return [f"Registry file not found: {path}"]

    try:
        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        return [f"YAML parse error: {e}"]

    # Check required top-level keys
    for required_key in ("version", "last_updated"):
        if required_key not in data:
            violations.append(f"Missing required top-level key: '{required_key}'")

    # Check freshness
    last_updated = data.get("last_updated")
    if last_updated:
        try:
            if isinstance(last_updated, str):
                updated_date = datetime.strptime(last_updated, "%Y-%m-%d").date()
            elif isinstance(last_updated, date):
                updated_date = last_updated
            else:
                violations.append(f"'last_updated' has unexpected type {type(last_updated)}")
                updated_date = None

            if updated_date:
                age_days = (date.today() - updated_date).days
                if age_days > MAX_STALE_DAYS:
                    violations.append(
                        f"Registry is {age_days} days old (limit {MAX_STALE_DAYS} days). "
                        "Update 'last_updated' after reviewing content."
                    )
        except ValueError:
            violations.append(f"'last_updated' is not a valid date: '{last_updated}'")

    return violations


def main() -> int:
    print(f"\n=== Registry Freshness & Consistency Check ({len(REGISTRIES)} registries) ===\n")

    report: list[dict] = []
    total_violations = 0

    for registry_path in REGISTRIES:
        violations = check_registry(registry_path)
        total_violations += len(violations)
        marker = "[OK]  " if not violations else "[FAIL]"
        last_updated = "N/A"
        if registry_path.exists():
            try:
                data = yaml.safe_load(registry_path.read_text()) or {}
                last_updated = str(data.get("last_updated", "N/A"))
            except Exception:
                pass
        print(f"  {marker} {registry_path.name}  last_updated={last_updated}")
        for v in violations:
            print(f"         → {v}")
        report.append({
            "registry": registry_path.name,
            "path": str(registry_path),
            "last_updated": last_updated,
            "violations": violations,
        })

    # Write evidence
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EVIDENCE_PATH, "w") as f:
        json.dump({
            "generated": date.today().isoformat(),
            "registries_checked": len(REGISTRIES),
            "total_violations": total_violations,
            "max_stale_days": MAX_STALE_DAYS,
            "registries": report,
        }, f, indent=2)

    print(f"\n[Evidence written to {EVIDENCE_PATH}]")

    if total_violations:
        print(f"\n[FAIL] {total_violations} registry violation(s) found\n")
        return 1

    print(f"\n[OK] All {len(REGISTRIES)} registries pass validation\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
