#!/usr/bin/env python3
"""Scan Python tests for values that look like real PII in test data.

Walks ``tests/**/*.py`` from the repository root, flags likely emails, phone-like
number runs, UK postcodes, and UK National Insurance numbers. Allowed fictional
domains are ignored for email checks.

Exit codes:
  0 — no suspicious PII patterns found
  1 — one or more potential leaks reported
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_GLOB = "tests/**/*.py"

ALLOWED_EMAIL_DOMAINS = frozenset(
    {
        "example.com",
        "test.com",
        "plantexpand.com",
    }
)

# Basic email token; domain group used for allowlisting.
EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@([a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,})",
)

# Contiguous digit runs of 10+ (phone-like).
PHONE_DIGITS_RUN_RE = re.compile(r"\d{10,}")

# UK postcode (outward + inward), common formats.
UK_POSTCODE_RE = re.compile(
    r"\b([A-Z]{1,2}\d[A-Z0-9]?\s*\d[A-Z]{2})\b",
    re.IGNORECASE,
)

# UK National Insurance number (2 letters + 6 digits + A–D); spaced or compact.
UK_NI_RE = re.compile(
    r"\b(?:[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]"
    r"|[A-CEGHJ-PR-TW-Z]{2}\s+\d{2}\s+\d{2}\s+\d{2}\s+[A-D])\b",
    re.IGNORECASE,
)


def _email_violations(line: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for m in EMAIL_RE.finditer(line):
        domain = m.group(1).lower()
        if domain in ALLOWED_EMAIL_DOMAINS:
            continue
        out.append((m.start() + 1, m.group(0)))
    return out


def _phone_violations(line: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for m in PHONE_DIGITS_RUN_RE.finditer(line):
        out.append((m.start() + 1, m.group(0)))
    return out


def _postcode_violations(line: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for m in UK_POSTCODE_RE.finditer(line):
        out.append((m.start() + 1, m.group(0)))
    return out


def _ni_violations(line: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for m in UK_NI_RE.finditer(line):
        out.append((m.start() + 1, m.group(0)))
    return out


def scan_file(path: Path) -> list[str]:
    """Return human-readable violation lines for this file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{path}:0: could not read file ({exc})"]

    violations: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        checks = (
            ("email", _email_violations(line)),
            ("phone-like digits", _phone_violations(line)),
            ("UK postcode", _postcode_violations(line)),
            ("UK NI number", _ni_violations(line)),
        )
        for kind, items in checks:
            for col, snippet in items:
                violations.append(
                    f"{path}:{lineno}:{col}: potential {kind}: {snippet!r}",
                )
    return violations


def main() -> int:
    test_root = REPO_ROOT / "tests"
    if not test_root.is_dir():
        print(f"No tests directory at {test_root}", file=sys.stderr)
        print("0 files checked, 0 potential PII leaks")
        return 0

    paths = sorted(p for p in test_root.rglob("*.py") if p.is_file())
    all_violations: list[str] = []
    for p in paths:
        all_violations.extend(scan_file(p))

    leak_count = len(all_violations)
    for line in all_violations:
        print(line)
    print(f"{len(paths)} files checked, {leak_count} potential PII leaks")

    return 1 if leak_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
