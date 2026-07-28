"""Tests for the lockfile validity checker.

The checker replaced a gate that re-resolved against PyPI and therefore failed
whenever an upstream release appeared. These tests pin the properties that
replaced it, and in particular that the new check still refuses the things that
actually matter: a missing dependency, a pin outside its declared range, and an
entry with no hash.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_lockfile.py"


def load_checker(requirements: Path, lockfile: Path):
    """Import the script with its module-level paths pointed at fixtures."""
    spec = importlib.util.spec_from_file_location("verify_lockfile_under_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.REQUIREMENTS = requirements
    module.LOCKFILE = lockfile
    return module


def write(tmp_path: Path, requirements: str, lock: str) -> tuple[Path, Path]:
    req = tmp_path / "requirements.txt"
    lockfile = tmp_path / "requirements.lock"
    req.write_text(requirements)
    lockfile.write_text(lock)
    return req, lockfile


HASH = "--hash=sha256:" + "0" * 64

VALID_LOCK = f"""
fastapi==0.140.7 \\
    {HASH}
sqlalchemy==2.0.25 \\
    {HASH}
# via sqlalchemy
greenlet==3.3.2 \\
    {HASH}
"""

VALID_REQUIREMENTS = """
# comment line
fastapi>=0.109.0,<1.0.0
sqlalchemy==2.0.25
"""


def test_accepts_a_lock_that_is_not_the_newest_available(tmp_path):
    """The whole point: a valid lock passes without asking PyPI what is newest."""
    req, lock = write(tmp_path, VALID_REQUIREMENTS, VALID_LOCK)
    assert load_checker(req, lock).main() == 0


def test_rejects_a_declared_dependency_missing_from_the_lock(tmp_path):
    req, lock = write(tmp_path, VALID_REQUIREMENTS + "\nredis>=5.0.0\n", VALID_LOCK)
    assert load_checker(req, lock).main() == 1


def test_rejects_a_pin_outside_its_declared_range(tmp_path):
    """A lock claiming a version the project has not authorised must fail."""
    req, lock = write(tmp_path, "fastapi>=0.109.0,<1.0.0\n", f"fastapi==1.4.0 \\\n    {HASH}\n")
    assert load_checker(req, lock).main() == 1


def test_rejects_an_entry_with_no_hash(tmp_path):
    """Hash pinning is the supply-chain property; losing it must stay a failure."""
    req, lock = write(tmp_path, "fastapi>=0.109.0,<1.0.0\n", "fastapi==0.140.7\n")
    assert load_checker(req, lock).main() == 1


def test_rejects_an_empty_lock(tmp_path):
    req, lock = write(tmp_path, VALID_REQUIREMENTS, "# nothing pinned here\n")
    assert load_checker(req, lock).main() == 1


def test_rejects_a_missing_lock(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text(VALID_REQUIREMENTS)
    assert load_checker(req, tmp_path / "absent.lock").main() == 1


def test_extras_in_a_declared_requirement_resolve_by_base_name(tmp_path):
    """uvicorn[standard] is locked as 'uvicorn'; the extra must not read as absent."""
    req, lock = write(
        tmp_path,
        "uvicorn[standard]>=0.27.0,<1.0.0\n",
        f"uvicorn==0.51.0 \\\n    {HASH}\n",
    )
    assert load_checker(req, lock).main() == 0


def test_underscore_and_hyphen_spellings_are_the_same_package(tmp_path):
    req, lock = write(tmp_path, "python_dateutil>=2.9.0\n", f"python-dateutil==2.9.0 \\\n    {HASH}\n")
    assert load_checker(req, lock).main() == 0


@pytest.mark.parametrize("declared", ["fastapi", "fastapi>=0.1"])
def test_a_dependency_with_a_loose_or_absent_specifier_only_needs_to_be_present(tmp_path, declared):
    req, lock = write(tmp_path, declared + "\n", f"fastapi==0.140.7 \\\n    {HASH}\n")
    assert load_checker(req, lock).main() == 0


def test_the_repositorys_own_lockfile_is_valid(tmp_path):
    """Guard against the checker passing only on fixtures."""
    root = SCRIPT.parent.parent
    module = load_checker(root / "requirements.txt", root / "requirements.lock")
    assert module.main() == 0, "the committed requirements.lock does not satisfy requirements.txt"
