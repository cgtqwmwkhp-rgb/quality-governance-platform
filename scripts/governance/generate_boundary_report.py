#!/usr/bin/env python3
"""Generate boundary enforcement metric report for CI (D09 — AP-E)."""
import datetime
import json
import os
import subprocess

result = subprocess.run(
    ["python3", "scripts/check_import_boundaries.py"],
    capture_output=True,
    text=True,
)
violations = [
    line
    for line in result.stdout.splitlines()
    if "VIOLATION" in line.upper() or "ERROR" in line.upper()
]
report = {
    "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    "ci_run_id": os.environ.get("GITHUB_RUN_ID", "local"),
    "head_sha": os.environ.get("GITHUB_SHA", "local")[:8],
    "violation_count": len(violations),
    "violations": violations[:20],
    "check_passed": result.returncode == 0,
}
os.makedirs("docs/evidence", exist_ok=True)
with open("docs/evidence/boundary-enforcement-report.json", "w") as fh:
    json.dump(report, fh, indent=2)
print(
    f"[OK] Boundary report: {len(violations)} violations, "
    f"passed={result.returncode == 0}"
)
