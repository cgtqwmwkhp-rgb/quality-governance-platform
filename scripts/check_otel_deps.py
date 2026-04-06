#!/usr/bin/env python3
"""Verify that OpenTelemetry packages are declared in requirements.txt.

Exits 0 if at least one opentelemetry package is found, 1 otherwise.
Intended for CI gates to catch accidental removal of observability deps.
"""

import pathlib
import sys

REQUIREMENTS_PATH = pathlib.Path(__file__).resolve().parent.parent / "requirements.txt"

REQUIRED_PREFIXES = [
    "opentelemetry-api",
    "opentelemetry-sdk",
]


def main() -> int:
    if not REQUIREMENTS_PATH.exists():
        print(f"ERROR: {REQUIREMENTS_PATH} not found", file=sys.stderr)
        return 1

    lines = REQUIREMENTS_PATH.read_text().splitlines()
    deps = [line.strip().lower() for line in lines if line.strip() and not line.strip().startswith("#")]

    missing: list[str] = []
    for prefix in REQUIRED_PREFIXES:
        if not any(dep.startswith(prefix) for dep in deps):
            missing.append(prefix)

    if missing:
        print(
            f"ERROR: Missing required OpenTelemetry packages in {REQUIREMENTS_PATH.name}:",
            file=sys.stderr,
        )
        for pkg in missing:
            print(f"  - {pkg}", file=sys.stderr)
        return 1

    found = [dep for dep in deps if dep.startswith("opentelemetry")]
    print(f"OK: Found {len(found)} opentelemetry package(s) in {REQUIREMENTS_PATH.name}:")
    for dep in found:
        print(f"  + {dep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
