#!/usr/bin/env python3
"""Validate security waivers and emit active pip-audit ignore args."""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def run_pip_audit() -> List[Dict]:
    """Run pip-audit and return list of vulnerabilities."""
    try:
        result = subprocess.run(
            ["pip-audit", "--format", "json"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            return []

        # Parse JSON output
        try:
            data = json.loads(result.stdout)
            vulnerabilities = []

            for package_data in data.get("dependencies", []):
                package_name = package_data.get("name")
                for vuln in package_data.get("vulns", []):
                    vulnerabilities.append(
                        {
                            "package": package_name,
                            "version": package_data.get("version"),
                            "id": vuln.get("id"),
                            "description": vuln.get("description", "")[:100],
                        }
                    )

            return vulnerabilities
        except json.JSONDecodeError:
            print("⚠️  Could not parse pip-audit JSON output")
            return []

    except FileNotFoundError:
        print("❌ pip-audit not found. Install with: pip install pip-audit")
        sys.exit(1)


def parse_waivers(waiver_file: Path) -> Dict[str, datetime]:
    """
    Parse SECURITY_WAIVERS.md and return dict of {CVE_ID: expiry_date}.

    Returns empty dict if file doesn't exist.
    """
    if not waiver_file.exists():
        return {}

    content = waiver_file.read_text()
    waivers = {}

    # Pattern to match advisory IDs and expiry dates.
    # Recognised forms: CVE-YYYY-NNNNNNN, PYSEC-YYYY-N, and GitHub Security
    # Advisory IDs (GHSA-xxxx-xxxx-xxxx) which pip-audit emits for
    # advisories that don't yet have a CVE assignment.
    # Looking for lines like: "**Expiry Date**: 2026-04-04 (90 days)"
    cve_pattern = (
        r"CVE-\d{4}-\d{4,7}|PYSEC-\d{4}-\d+|GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}"
    )
    expiry_pattern = r"\*\*Expiry Date\*\*:\s*(\d{4}-\d{2}-\d{2})"

    # Split into sections by "###" headers
    sections = re.split(r"^###\s+", content, flags=re.MULTILINE)

    for section in sections:
        # Find all CVE IDs in this section
        cve_ids = re.findall(cve_pattern, section)

        # Find expiry date in this section
        expiry_match = re.search(expiry_pattern, section)

        if cve_ids and expiry_match:
            expiry_str = expiry_match.group(1)
            try:
                expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
                for cve_id in cve_ids:
                    waivers[cve_id] = expiry_date
            except ValueError:
                print(f"⚠️  Invalid date format in waiver: {expiry_str}")

    return waivers


def get_active_waiver_ids(waivers: Dict[str, datetime], now: Optional[datetime] = None) -> List[str]:
    """Return non-expired waiver IDs sorted for stable output."""
    current_time = now or datetime.now()
    return sorted(cve_id for cve_id, expiry in waivers.items() if current_time <= expiry)


def build_pip_audit_ignore_args(waivers: Dict[str, datetime], now: Optional[datetime] = None) -> List[str]:
    """Build pip-audit ignore args from active waiver IDs."""
    args: List[str] = []
    for cve_id in get_active_waiver_ids(waivers, now=now):
        args.extend(["--ignore-vuln", cve_id])
    return args


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Validate security waivers and pip-audit ignores")
    parser.add_argument(
        "--emit-pip-audit-args",
        action="store_true",
        help="Print active pip-audit ignore args and exit",
    )
    return parser.parse_args()


def main() -> int:
    """Main validation logic."""
    args = parse_args()
    repo_root = Path(__file__).parent.parent
    waiver_file = repo_root / "docs" / "SECURITY_WAIVERS.md"

    if args.emit_pip_audit_args:
        waivers = parse_waivers(waiver_file)
        print(" ".join(build_pip_audit_ignore_args(waivers)))
        return 0

    print("🔍 Running security waiver validation...")
    print()

    # Step 1: Run pip-audit
    print("1. Running pip-audit...")
    vulnerabilities = run_pip_audit()

    if not vulnerabilities:
        print("✅ No vulnerabilities detected by pip-audit")
        print()
        return 0

    print(f"⚠️  Found {len(vulnerabilities)} vulnerability/vulnerabilities")
    print()

    # Step 2: Parse waivers
    print("2. Parsing security waivers...")
    waivers = parse_waivers(waiver_file)

    if not waivers:
        print("❌ No waivers found in docs/SECURITY_WAIVERS.md")
        print()
        print("All vulnerabilities must be either:")
        print("  1. Fixed by upgrading dependencies, OR")
        print("  2. Documented in docs/SECURITY_WAIVERS.md with expiry date")
        print()
        return 1

    print(f"✓ Found {len(waivers)} waived CVE(s)")
    print()

    # Step 3: Check each vulnerability
    print("3. Validating vulnerabilities against waivers...")
    print()

    now = datetime.now()
    unwaived = []
    expired = []
    waived_ok = []

    for vuln in vulnerabilities:
        cve_id = vuln["id"]

        if cve_id not in waivers:
            unwaived.append(vuln)
        else:
            expiry = waivers[cve_id]
            if now > expiry:
                expired.append((vuln, expiry))
            else:
                waived_ok.append((vuln, expiry))

    # Report waived vulnerabilities
    if waived_ok:
        print(f"✓ {len(waived_ok)} vulnerability/vulnerabilities properly waived:")
        for vuln, expiry in waived_ok:
            days_left = (expiry - now).days
            print(f"  - {vuln['id']} ({vuln['package']}) - expires in {days_left} days")
        print()

    # Report violations
    has_violations = False

    if unwaived:
        has_violations = True
        print(f"❌ {len(unwaived)} UNWAIVED vulnerability/vulnerabilities:")
        for vuln in unwaived:
            print(f"  - {vuln['id']} in {vuln['package']} {vuln['version']}")
            print(f"    {vuln['description']}")
        print()
        print("Action required:")
        print("  1. Upgrade the affected package to fix the vulnerability, OR")
        print("  2. Add a waiver entry to docs/SECURITY_WAIVERS.md with:")
        print("     - CVE ID, package, reason, mitigation, owner, expiry date")
        print()

    if expired:
        has_violations = True
        print(f"❌ {len(expired)} EXPIRED waiver(s):")
        for vuln, expiry in expired:
            days_expired = (now - expiry).days
            print(f"  - {vuln['id']} ({vuln['package']}) - expired {days_expired} days ago")
        print()
        print("Action required:")
        print("  1. Fix the vulnerability by upgrading dependencies, OR")
        print("  2. Extend the waiver in docs/SECURITY_WAIVERS.md with updated justification")
        print()

    if has_violations:
        print("❌ Security gate FAILED")
        print()
        return 1

    print("✅ Security waiver validation passed!")
    print()
    print("Summary:")
    print(f"  - {len(vulnerabilities)} total vulnerability/vulnerabilities")
    print(f"  - {len(waived_ok)} properly waived")
    print(f"  - 0 unwaived or expired")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
