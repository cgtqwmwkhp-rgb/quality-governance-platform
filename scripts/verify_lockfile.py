#!/usr/bin/env python3
"""Verify requirements.lock is a valid lock for requirements.txt.

Checks the properties a lockfile exists to provide — every declared dependency
is resolved, every resolved version satisfies its declared constraint, and every
entry is hash-pinned — without re-resolving against PyPI.

Re-resolving is what the previous gate did, and it made the result depend on
what PyPI happened to be serving at the time: 32 of the declared dependencies
are ranges, so any upstream release anywhere in the tree made a committed,
working lockfile "stale" and failed every open pull request. The visible cost
was CI noise; the real cost was that unblocking meant regenerating the lock
inside whatever unrelated pull request happened to be open, which is an
unreviewed dependency bump smuggled through a change about something else.
Upgrades belong to Dependabot, where they are reviewed one dependency at a time.

Exit status is 0 when the lockfile is valid and 1 when it is not.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    from packaging.version import InvalidVersion, Version
except ModuleNotFoundError:  # pragma: no cover - CI installs packaging
    print("[FAIL] the 'packaging' library is required to verify the lockfile", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"
LOCKFILE = ROOT / "requirements.lock"

# A locked entry looks like "name==1.2.3 \" with --hash continuation lines under it.
_PIN = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)\s*==\s*(?P<version>[^\s\\;]+)")


def parse_declared(path: Path) -> list[Requirement]:
    """Read the direct dependencies, ignoring comments, options and -r includes."""
    declared: list[Requirement] = []
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        try:
            declared.append(Requirement(line))
        except Exception:
            print(f"[FAIL] cannot parse requirement: {raw!r}")
            sys.exit(1)
    return declared


def parse_locked(path: Path) -> tuple[dict[str, str], set[str]]:
    """Return {canonical name: version} plus the names carrying at least one hash."""
    versions: dict[str, str] = {}
    hashed: set[str] = set()
    current: str | None = None
    for raw in path.read_text().splitlines():
        stripped = raw.strip()
        if stripped.startswith("--hash"):
            # Belongs to the entry above it; a bare --hash with no entry is malformed.
            if current is not None:
                hashed.add(current)
            continue
        if not stripped or stripped.startswith("#"):
            continue
        match = _PIN.match(stripped)
        if match:
            current = canonicalize_name(match.group("name"))
            versions[current] = match.group("version")
        elif not stripped.startswith("-"):
            current = None
    return versions, hashed


def main() -> int:
    for path in (REQUIREMENTS, LOCKFILE):
        if not path.exists():
            print(f"[FAIL] {path.name} is required and missing.")
            return 1

    declared = parse_declared(REQUIREMENTS)
    locked, hashed = parse_locked(LOCKFILE)

    if not locked:
        print("[FAIL] requirements.lock contains no pinned versions.")
        return 1

    failures: list[str] = []

    for requirement in declared:
        name = canonicalize_name(requirement.name)
        if name not in locked:
            failures.append(f"{requirement.name}: declared in requirements.txt but absent from the lockfile")
            continue

        raw_version = locked[name]
        if not requirement.specifier:
            continue
        try:
            version = Version(raw_version)
        except InvalidVersion:
            failures.append(f"{requirement.name}: locked version {raw_version!r} is not a valid version")
            continue
        # prereleases=True so an intentionally locked pre-release is judged against
        # the declared range rather than silently rejected for being a pre-release.
        if not requirement.specifier.contains(version, prereleases=True):
            failures.append(
                f"{requirement.name}: locked at {raw_version} which does not satisfy "
                f"the declared constraint '{requirement.specifier}'"
            )

    unhashed = sorted(set(locked) - hashed)
    if unhashed:
        failures.append(
            "these locked packages carry no --hash, so the install is not verifiable: " + ", ".join(unhashed[:10])
        )

    if failures:
        print("[FAIL] requirements.lock is not a valid lock for requirements.txt:")
        for failure in failures:
            print(f"  - {failure}")
        print("\n[INFO] Regenerate with ./scripts/generate_lockfile.sh")
        return 1

    print(
        f"[OK] requirements.lock is valid: {len(declared)} declared dependencies resolved, "
        f"{len(locked)} packages pinned, all hash-verified."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
