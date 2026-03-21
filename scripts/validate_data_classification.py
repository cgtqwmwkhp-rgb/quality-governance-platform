#!/usr/bin/env python3
"""Validate that all domain models declare a __data_classification__ attribute.

Exit 0 if all models are classified, exit 1 if any are missing.
Intended for CI enforcement (see docs/privacy/data-classification.md).
"""

import importlib
import inspect
import sys

MODEL_MODULES = [
    "src.domain.models.incident",
    "src.domain.models.complaint",
    "src.domain.models.risk",
    "src.domain.models.rta",
    "src.domain.models.audit",
    "src.domain.models.capa",
    "src.domain.models.near_miss",
    "src.domain.models.policy",
    "src.domain.models.user",
    "src.domain.models.tenant",
    "src.domain.models.investigation",
]

VALID_LEVELS = {"C1_PUBLIC", "C2_INTERNAL", "C3_CONFIDENTIAL", "C4_RESTRICTED"}


def main() -> int:
    missing = []
    classified = []
    errors = []

    for mod_path in MODEL_MODULES:
        try:
            mod = importlib.import_module(mod_path)
        except Exception as exc:
            errors.append(f"  IMPORT ERROR: {mod_path} — {exc}")
            continue

        for name, obj in inspect.getmembers(mod, inspect.isclass):
            if not hasattr(obj, "__tablename__"):
                continue
            if obj.__module__ != mod_path:
                continue

            level = getattr(obj, "__data_classification__", None)
            if level is None:
                missing.append(f"  MISSING: {mod_path}.{name}")
            elif level not in VALID_LEVELS:
                missing.append(f"  INVALID ({level}): {mod_path}.{name}")
            else:
                classified.append(f"  {level}: {mod_path}.{name}")

    print("=== Data Classification Validation ===\n")

    if classified:
        print(f"Classified ({len(classified)}):")
        for line in sorted(classified):
            print(line)
        print()

    if errors:
        print(f"Import Errors ({len(errors)}):")
        for line in errors:
            print(line)
        print()

    if missing:
        print(f"UNCLASSIFIED ({len(missing)}):")
        for line in sorted(missing):
            print(line)
        print()
        print("FAIL: All models with __tablename__ must declare __data_classification__.")
        print("See docs/privacy/data-classification.md for valid levels (C1–C4).")
        return 1

    print("PASS: All models are classified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
