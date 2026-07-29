#!/usr/bin/env python3
"""Fail the build when a security test skipped instead of running.

C-58: the security suite reported "45 passed, 12 skipped, Failed: 0" for as long
as it had no database. Ten OWASP tests obtain auth through a real login, found no
backend, and called ``pytest.skip("Auth required")``; a skip costs nothing, so
the workflow named "Security Scan" was green over a suite that had never
exercised its subject. Once the tests can run, a skip is a regression and has to
be treated as one.

One skip reason is accepted, and printed even when accepted:
``test_rate_limiting_on_login`` sends fifteen failed logins, the login rate
limiter answers 429, and that suite's helper treats 429 as "auth backend
unavailable" and skips — the skip is the rate limiter working as intended. The
exception is matched on the status code so that a genuine 5xx, which shares the
same message prefix, is not swallowed with it.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Matched against the skip reason. Narrow on purpose: "auth backend unavailable"
# alone would also absorb 500/502/503/504, which are exactly the failures that
# hid this defect in the first place.
ACCEPTED_SKIP_MARKER = "status=429"


def _skips(report: Path) -> list[tuple[str, str]]:
    """Return (test id, skip reason) for every skipped case in a JUnit report."""
    root = ET.parse(report).getroot()
    skipped: list[tuple[str, str]] = []
    for case in root.iter("testcase"):
        element = case.find("skipped")
        if element is None:
            continue
        test_id = f"{case.get('classname', '')}::{case.get('name', '')}"
        reason = element.get("message") or (element.text or "").strip() or "no reason recorded"
        skipped.append((test_id, reason))
    return skipped


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} <junit-xml>", file=sys.stderr)
        return 2

    report = Path(argv[1])
    if not report.is_file():
        # A missing report is not "nothing to check": pytest produced no record,
        # so nothing can be said about what ran.
        print(f"::error title=Security suite::No JUnit report at {report}; the suite produced no record of what ran.")
        return 1

    try:
        skipped = _skips(report)
    except ET.ParseError as exc:
        print(f"::error title=Security suite::JUnit report {report} could not be parsed: {exc}")
        return 1

    accepted = [entry for entry in skipped if ACCEPTED_SKIP_MARKER in entry[1]]
    refused = [entry for entry in skipped if ACCEPTED_SKIP_MARKER not in entry[1]]

    for test_id, reason in accepted:
        print(f"[accepted skip] {test_id}: {reason}")

    if refused:
        print(
            f"::error title=Security suite::{len(refused)} security test(s) skipped rather than ran. "
            "A skipped security test is not a passing one."
        )
        for test_id, reason in refused:
            print(f"  - {test_id}: {reason}")
        return 1

    print(f"[OK] No security test skipped for want of a working environment ({len(accepted)} accepted skip(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
