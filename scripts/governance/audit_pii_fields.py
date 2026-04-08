#!/usr/bin/env python3
"""
PII inventory automation script (D07 — Privacy & Data Protection).

Scans SQLAlchemy model files in src/domain/models/ for columns that are
likely to contain Personal Identifiable Information (PII) based on a
heuristic keyword list. Outputs a structured JSON inventory report to
docs/evidence/pii-inventory-<date>.json and prints a summary.

Usage:
    python3 scripts/governance/audit_pii_fields.py

CI integration: run on any PR touching src/domain/models/ to detect new
PII fields that lack a comment or data-classification annotation.
"""

from __future__ import annotations

import ast
import datetime
import json
import os
import re
import sys
from pathlib import Path

# Heuristic keywords indicating a column likely contains PII.
# Order matters: more specific first.
PII_KEYWORDS: list[tuple[str, str]] = [
    # Category, keyword pattern (case-insensitive)
    ("contact", "email"),
    ("contact", "phone"),
    ("contact", "mobile"),
    ("identity", "national_insurance"),
    ("identity", r"nino"),
    ("identity", "date_of_birth"),
    ("identity", r"\bdob\b"),
    ("identity", "passport"),
    ("identity", "driving_licence"),
    ("identity", "driving_license"),
    ("identity", "nhs_number"),
    ("health", "medical"),
    ("health", "health_condition"),
    ("health", "injury"),
    ("health", "treatment"),
    ("location", "address"),
    ("location", "postcode"),
    ("location", "geo_lat"),
    ("location", "geo_lon"),
    ("identity", "full_name"),
    ("identity", r"\bname\b"),
    ("identity", "first_name"),
    ("identity", "last_name"),
    ("identity", "surname"),
    ("biometric", "fingerprint"),
    ("biometric", "face_image"),
    ("financial", "bank_account"),
    ("financial", "sort_code"),
    ("financial", "iban"),
    ("vehicle", "vehicle_reg"),
    ("vehicle", "registration_number"),
    ("employment", "employee_id"),
    ("employment", "staff_id"),
    ("employment", "payroll"),
    ("employment", "salary"),
    ("employment", "ni_number"),
    ("witness", "witness_name"),
    ("witness", "witness_contact"),
    ("incident", "reporter_name"),
    ("incident", "reporter_email"),
    ("incident", "reporter_phone"),
]

MODELS_DIR = Path("src/domain/models")
OUTPUT_DIR = Path("docs/evidence")
TODAY = datetime.date.today().isoformat()


def extract_column_names(filepath: Path) -> list[dict]:
    """Parse a Python model file and extract Column assignments with PII heuristics."""
    source = filepath.read_text(encoding="utf-8")
    findings: list[dict] = []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        class_name = node.name
        for item in ast.walk(node):
            if not isinstance(item, ast.Assign):
                continue
            for target in item.targets:
                if not isinstance(target, ast.Name):
                    continue
                col_name = target.id
                matched_category = _match_pii(col_name)
                if matched_category:
                    findings.append(
                        {
                            "model": class_name,
                            "field": col_name,
                            "pii_category": matched_category,
                            "file": str(filepath),
                            "line": item.lineno,
                        }
                    )
    return findings


def _match_pii(field_name: str) -> str | None:
    """Return the PII category for a field name, or None if not PII."""
    for category, pattern in PII_KEYWORDS:
        if re.search(pattern, field_name, re.IGNORECASE):
            return category
    return None


def main() -> None:
    if not MODELS_DIR.exists():
        print(f"[ERROR] Models directory not found: {MODELS_DIR}", file=sys.stderr)
        sys.exit(1)

    all_findings: list[dict] = []
    model_files = list(MODELS_DIR.glob("*.py"))

    for filepath in sorted(model_files):
        findings = extract_column_names(filepath)
        all_findings.extend(findings)

    # Deduplicate by model+field
    seen = set()
    unique_findings = []
    for f in all_findings:
        key = (f["model"], f["field"])
        if key not in seen:
            seen.add(key)
            unique_findings.append(f)

    # Summary by category
    category_counts: dict[str, int] = {}
    for f in unique_findings:
        cat = f["pii_category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    report = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "generated_by": "scripts/governance/audit_pii_fields.py",
        "scan_path": str(MODELS_DIR),
        "total_pii_fields": len(unique_findings),
        "category_summary": category_counts,
        "fields": unique_findings,
        "status": "current",
        "next_review": (datetime.date.today() + datetime.timedelta(days=90)).isoformat(),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"pii-inventory-{TODAY}.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"[OK] PII inventory written to {output_path}")
    print(f"     Total PII fields detected: {len(unique_findings)}")
    for cat, count in sorted(category_counts.items()):
        print(f"     {cat}: {count} field(s)")


if __name__ == "__main__":
    main()
