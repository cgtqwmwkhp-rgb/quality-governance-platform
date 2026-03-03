#!/usr/bin/env python3
"""
Quality Trend Artifact Generator

Generates a quality trend report as CI artifact containing:
- E2E passed/skipped counts
- Integration passed/skipped counts
- Quarantine count
- Baseline used + min acceptable

Output formats: JSON and Markdown
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class TestResults:
    """Test results for a test suite."""

    passed: int
    skipped: int
    failed: int
    total: int


@dataclass
class QualityTrendReport:
    """Quality trend report structure."""

    report_date: str
    report_time: str
    ci_run_id: str
    commit_sha: str
    branch: str

    # E2E results
    e2e_passed: int
    e2e_skipped: int
    e2e_failed: int
    e2e_total: int

    # Integration results
    integration_passed: int
    integration_skipped: int
    integration_failed: int
    integration_total: int

    # Unit results
    unit_passed: int
    unit_skipped: int
    unit_failed: int
    unit_total: int

    # Quarantine status
    quarantine_count: int
    quarantine_allowed: bool

    # Baseline info
    baseline_pass_count: int
    baseline_min_acceptable: int
    baseline_date: str
    baseline_notes: str

    # Gate status
    baseline_gate_passed: bool
    all_gates_passed: bool


def load_baseline(baseline_path: Path) -> dict:
    """Load baseline from JSON file."""
    if not baseline_path.exists():
        return {
            "baseline_pass_count": 0,
            "min_acceptable_percentage": 90,
            "baseline_date": "N/A",
            "baseline_notes": "Baseline file not found",
        }

    with open(baseline_path, "r") as f:
        return json.load(f)


def generate_report(
    e2e: TestResults,
    integration: TestResults,
    unit: TestResults,
    quarantine_count: int,
    baseline_path: Path,
    ci_run_id: str,
    commit_sha: str,
    branch: str,
) -> QualityTrendReport:
    """Generate the quality trend report."""
    now = datetime.now()
    baseline = load_baseline(baseline_path)

    baseline_pass = baseline.get("baseline_pass_count", 0)
    min_pct = baseline.get("min_acceptable_percentage", 90)
    min_acceptable = int(baseline_pass * min_pct / 100)

    baseline_gate_passed = e2e.passed >= min_acceptable
    all_gates_passed = (
        baseline_gate_passed
        and e2e.failed == 0
        and integration.failed == 0
        and unit.failed == 0
        and quarantine_count == 0
    )

    return QualityTrendReport(
        report_date=now.strftime("%Y-%m-%d"),
        report_time=now.strftime("%H:%M:%S"),
        ci_run_id=ci_run_id,
        commit_sha=commit_sha,
        branch=branch,
        e2e_passed=e2e.passed,
        e2e_skipped=e2e.skipped,
        e2e_failed=e2e.failed,
        e2e_total=e2e.total,
        integration_passed=integration.passed,
        integration_skipped=integration.skipped,
        integration_failed=integration.failed,
        integration_total=integration.total,
        unit_passed=unit.passed,
        unit_skipped=unit.skipped,
        unit_failed=unit.failed,
        unit_total=unit.total,
        quarantine_count=quarantine_count,
        quarantine_allowed=quarantine_count == 0,
        baseline_pass_count=baseline_pass,
        baseline_min_acceptable=min_acceptable,
        baseline_date=baseline.get("baseline_date", "N/A"),
        baseline_notes=baseline.get("baseline_notes", ""),
        baseline_gate_passed=baseline_gate_passed,
        all_gates_passed=all_gates_passed,
    )


def generate_json(report: QualityTrendReport, output_path: Path) -> None:
    """Generate JSON output."""
    with open(output_path, "w") as f:
        json.dump(asdict(report), f, indent=2)
    print(f"✅ JSON report written to: {output_path}")


def generate_markdown(report: QualityTrendReport, output_path: Path) -> None:
    """Generate Markdown output."""
    gate_emoji = "✅" if report.all_gates_passed else "❌"
    baseline_emoji = "✅" if report.baseline_gate_passed else "❌"
    quarantine_emoji = "✅" if report.quarantine_allowed else "⚠️"

    content = f"""# Quality Trend Report

**Generated**: {report.report_date} {report.report_time}
**CI Run**: {report.ci_run_id}
**Commit**: `{report.commit_sha}`
**Branch**: `{report.branch}`

## Overall Status

| Gate | Status |
|------|--------|
| All Gates | {gate_emoji} {'PASSED' if report.all_gates_passed else 'FAILED'} |
| Baseline Gate | {baseline_emoji} {'PASSED' if report.baseline_gate_passed else 'FAILED'} |
| Quarantine | {quarantine_emoji} {report.quarantine_count} quarantined |

## Test Results

### E2E Tests
| Metric | Count |
|--------|-------|
| Passed | {report.e2e_passed} |
| Skipped | {report.e2e_skipped} |
| Failed | {report.e2e_failed} |
| **Total** | **{report.e2e_total}** |

### Integration Tests
| Metric | Count |
|--------|-------|
| Passed | {report.integration_passed} |
| Skipped | {report.integration_skipped} |
| Failed | {report.integration_failed} |
| **Total** | **{report.integration_total}** |

### Unit Tests
| Metric | Count |
|--------|-------|
| Passed | {report.unit_passed} |
| Skipped | {report.unit_skipped} |
| Failed | {report.unit_failed} |
| **Total** | **{report.unit_total}** |

## Baseline Information

| Property | Value |
|----------|-------|
| Baseline Pass Count | {report.baseline_pass_count} |
| Min Acceptable (90%) | {report.baseline_min_acceptable} |
| Baseline Date | {report.baseline_date} |
| Notes | {report.baseline_notes} |

## Trend Summary

```
E2E:         {report.e2e_passed}/{report.e2e_total} passed ({100*report.e2e_passed//max(report.e2e_total,1)}%)
Integration: {report.integration_passed}/{report.integration_total} passed ({100*report.integration_passed//max(report.integration_total,1)}%)
Unit:        {report.unit_passed}/{report.unit_total} passed ({100*report.unit_passed//max(report.unit_total,1)}%)
Quarantine:  {report.quarantine_count} (target: 0)
```

---
*Generated by scripts/generate_quality_trend.py*
"""

    with open(output_path, "w") as f:
        f.write(content)
    print(f"✅ Markdown report written to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate quality trend artifact")

    # E2E results
    parser.add_argument("--e2e-passed", type=int, default=0)
    parser.add_argument("--e2e-skipped", type=int, default=0)
    parser.add_argument("--e2e-failed", type=int, default=0)

    # Integration results
    parser.add_argument("--integration-passed", type=int, default=0)
    parser.add_argument("--integration-skipped", type=int, default=0)
    parser.add_argument("--integration-failed", type=int, default=0)

    # Unit results
    parser.add_argument("--unit-passed", type=int, default=0)
    parser.add_argument("--unit-skipped", type=int, default=0)
    parser.add_argument("--unit-failed", type=int, default=0)

    # Quarantine
    parser.add_argument("--quarantine-count", type=int, default=0)

    # CI info
    parser.add_argument("--ci-run-id", type=str, default=os.environ.get("GITHUB_RUN_ID", "local"))
    parser.add_argument("--commit-sha", type=str, default=os.environ.get("GITHUB_SHA", "local")[:7])
    parser.add_argument("--branch", type=str, default=os.environ.get("GITHUB_REF_NAME", "local"))

    # Paths
    parser.add_argument("--baseline-file", type=str, default="docs/evidence/e2e_baseline.json")
    parser.add_argument("--output-dir", type=str, default=".")

    args = parser.parse_args()

    # Build test results
    e2e = TestResults(
        passed=args.e2e_passed,
        skipped=args.e2e_skipped,
        failed=args.e2e_failed,
        total=args.e2e_passed + args.e2e_skipped + args.e2e_failed,
    )

    integration = TestResults(
        passed=args.integration_passed,
        skipped=args.integration_skipped,
        failed=args.integration_failed,
        total=args.integration_passed + args.integration_skipped + args.integration_failed,
    )

    unit = TestResults(
        passed=args.unit_passed,
        skipped=args.unit_skipped,
        failed=args.unit_failed,
        total=args.unit_passed + args.unit_skipped + args.unit_failed,
    )

    # Resolve baseline path
    baseline_path = Path(args.baseline_file)
    if not baseline_path.is_absolute():
        repo_root = Path(__file__).parent.parent
        baseline_path = repo_root / baseline_path

    # Generate report
    report = generate_report(
        e2e=e2e,
        integration=integration,
        unit=unit,
        quarantine_count=args.quarantine_count,
        baseline_path=baseline_path,
        ci_run_id=args.ci_run_id,
        commit_sha=args.commit_sha,
        branch=args.branch,
    )

    # Output
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generate_json(report, output_dir / "quality_trend.json")
    generate_markdown(report, output_dir / "quality_trend.md")

    # Print summary
    print()
    print("=" * 50)
    print("QUALITY TREND SUMMARY")
    print("=" * 50)
    print(f"E2E:         {report.e2e_passed}/{report.e2e_total}")
    print(f"Integration: {report.integration_passed}/{report.integration_total}")
    print(f"Unit:        {report.unit_passed}/{report.unit_total}")
    print(f"Quarantine:  {report.quarantine_count}")
    print(f"Baseline:    {report.baseline_pass_count} (min: {report.baseline_min_acceptable})")
    print("=" * 50)

    if report.all_gates_passed:
        print("✅ All gates passed")
    else:
        print("❌ Some gates failed")
        if not report.baseline_gate_passed:
            print("   - Baseline gate failed")
        if report.quarantine_count > 0:
            print("   - Quarantine count > 0")


if __name__ == "__main__":
    main()
