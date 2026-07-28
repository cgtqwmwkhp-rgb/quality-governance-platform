"""Assert the interpreter running this test has exactly the locked dependency set.

The static guard in test_dependency_workflow_pinning.py reads workflow YAML, so
it proves what CI is *configured* to install. This one reads the live
environment, so it proves what is *actually* importable. Both are needed: a job
can install the lockfile and then have a later step move a pin.

The lockfile is parsed with scripts/verify_lockfile.py rather than a second
parser, so there is one definition of what the lockfile says.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
from pathlib import Path

import pytest
from packaging.utils import canonicalize_name

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCKFILE = REPO_ROOT / "requirements.lock"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_lockfile.py"

# The lockfile currently pins 116 packages. A floor rather than an exact number,
# so declaring a new dependency does not fail this test, but a parser that
# silently returns nothing does.
MIN_LOCKED_PACKAGES = 100

REGENERATE_HINT = (
    "\n\nThis environment does not match requirements.lock. To rebuild it:\n"
    "    python3.11 -m venv .venv && . .venv/bin/activate\n"
    "    pip install -r requirements.lock\n"
    "    pip install -r requirements-dev.txt\n"
    "See docs/ci/dependency-environments.md."
)


def _load_lockfile_parser():
    spec = importlib.util.spec_from_file_location("verify_lockfile", VERIFY_SCRIPT)
    assert spec and spec.loader, f"cannot load {VERIFY_SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def locked_versions() -> dict[str, str]:
    assert LOCKFILE.is_file(), f"{LOCKFILE} is missing"
    assert VERIFY_SCRIPT.is_file(), f"{VERIFY_SCRIPT} is missing"
    versions, _hashed = _load_lockfile_parser().parse_locked(LOCKFILE)
    return versions


def test_the_lockfile_parsed_to_something_plausible(locked_versions: dict[str, str]) -> None:
    """Guard the guard: an empty parse must not read as "nothing diverges"."""
    assert len(locked_versions) >= MIN_LOCKED_PACKAGES, (
        f"parsed only {len(locked_versions)} pins out of {LOCKFILE.name}, expected at least "
        f"{MIN_LOCKED_PACKAGES}; the lockfile or the parser is broken, so this test cannot "
        "conclude anything about the environment"
    )
    assert "fastapi" in locked_versions, "expected fastapi among the locked pins"


def test_every_locked_package_is_installed_at_the_locked_version(
    locked_versions: dict[str, str],
) -> None:
    """The exact property the lockfile exists to provide, checked at runtime."""
    # Collect every version found per name rather than one, because a failed
    # uninstall can leave two dist-info directories for the same package and
    # keeping only the last one silently reports the wrong answer.
    installed: dict[str, set[str]] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        if name:
            installed.setdefault(canonicalize_name(name), set()).add(distribution.version)

    missing: list[str] = []
    mismatched: list[str] = []
    duplicated: list[str] = []
    for name, locked_version in sorted(locked_versions.items()):
        actual = installed.get(canonicalize_name(name))
        if not actual:
            missing.append(f"{name}: locked at {locked_version}, not installed")
        elif len(actual) > 1:
            duplicated.append(
                f"{name}: locked at {locked_version}, but {len(actual)} versions are "
                f"installed simultaneously ({', '.join(sorted(actual))})"
            )
        elif actual != {locked_version}:
            mismatched.append(f"{name}: locked at {locked_version}, installed {actual.pop()}")

    problems = missing + mismatched + duplicated
    assert not problems, (
        f"{len(problems)} of {len(locked_versions)} locked packages do not match this "
        "environment:\n  " + "\n  ".join(problems) + REGENERATE_HINT
    )
