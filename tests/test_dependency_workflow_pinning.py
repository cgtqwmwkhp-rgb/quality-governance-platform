"""Guard: no CI job may install the application's dependencies unpinned.

Twenty-three jobs used to run `pip install -r requirements.txt`, directly or via
`requirements-dev.txt`, whose first line is `-r requirements.txt`. Thirty-two of
the forty-five declared dependencies are version ranges, so every one of those
jobs re-resolved against whatever PyPI was serving at job time. Two consequences
mattered: the dependency set changed with no commit, so a new upstream release
retroactively changed what every open pull request was tested against; and for a
product whose release evidence is its test results, "CI was green" did not
identify what had been tested.

This test fails if a future contributor reintroduces an unpinned install route.
It is written to fail loudly rather than pass by inspecting nothing: it asserts
it actually found a plausible number of workflow files, jobs and install
commands before it draws any conclusion.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

# The lockfile covers requirements.txt only, so the test tooling that actually
# runs the suite still comes from requirements-dev.txt. That is allowed, but only
# on top of the lockfile: the locked runtime set must already be installed so the
# dev resolution cannot choose the runtime versions.
LOCK_ROUTE = "requirements.lock"
UNPINNED_ROUTE = "requirements.txt"
DEV_ROUTE = "requirements-dev.txt"

# Standalone tools installed by name rather than from a requirements file. These
# are analysis and load-testing tools, not application dependencies: they do not
# change what the application under test is built from. They are enumerated
# rather than pattern-matched so that adding a new one is a visible decision.
ALLOWED_STANDALONE_TOOLS = frozenset(
    {
        "bandit",
        "celery",
        "coverage",
        "cyclonedx-bom",
        "httpx",
        "locust",
        "mutmut",
        "packaging",
        "pip",
        "pip-audit",
        "pip-licenses",
        "pip-tools",
        "pytest",
        "pytest-asyncio",
        "pyyaml",
        "radon",
        "redis",
        "requests",
        "safety",
        "schemathesis",
        "semgrep",
        "setuptools",
        "wheel",
    }
)

# Floors, not exact counts, so that adding a workflow or a job does not fail this
# test — but deleting most of them, or a parser change that silently matches
# nothing, does. Current actuals are well above each floor.
MIN_WORKFLOW_FILES = 15
MIN_JOBS_TOTAL = 40
MIN_INSTALL_COMMANDS = 50
MIN_JOBS_INSTALLING_DEPENDENCIES = 20

_PIP_INSTALL = re.compile(r"(?:python[0-9.]*\s+-m\s+)?pip[0-9.]*\s+install\s+([^\n]*)")


class InstallCommand:
    """One `pip install` invocation found in a workflow step."""

    def __init__(self, workflow: str, job: str, step: str, raw: str, arguments: str) -> None:
        self.workflow = workflow
        self.job = job
        self.step = step
        self.raw = " ".join(raw.split())
        # Only the text after `install`, so the interpreter and pip itself are not
        # mistaken for packages being installed.
        self.arguments = " ".join(arguments.split())

    @property
    def requirement_files(self) -> list[str]:
        """The `-r <file>` targets of this command."""
        files: list[str] = []
        tokens = _tokenize(self.arguments)
        for index, token in enumerate(tokens):
            if token == "-r" and index + 1 < len(tokens):
                files.append(Path(tokens[index + 1]).name)
            elif token.startswith("--requirement="):
                files.append(Path(token.split("=", 1)[1]).name)
        return files

    @property
    def standalone_packages(self) -> list[str]:
        """Package names given directly on the command line, normalised."""
        packages: list[str] = []
        tokens = _tokenize(self.arguments)
        skip_next = False
        for token in tokens:
            if skip_next:
                skip_next = False
                continue
            if token in {"-r", "--requirement", "-c", "--constraint", "-o", "--output-file"}:
                skip_next = True
                continue
            if token.startswith("-"):
                continue
            packages.append(_normalise(token))
        return [p for p in packages if p]

    def __str__(self) -> str:
        return f"{self.workflow}:{self.job} / {self.step!r}: {self.raw}"

    __repr__ = __str__


def _tokenize(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        # Unbalanced quoting from a shell expression we do not need to understand.
        return command.split()


def _normalise(token: str) -> str:
    """`'celery[redis]'` -> `celery`, `"mutmut<3"` -> `mutmut`."""
    token = token.strip("\"'")
    token = re.split(r"[<>=!~\[;]", token, maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", token).strip().lower()


def _load_workflows() -> list[Path]:
    return sorted(list(WORKFLOW_DIR.glob("*.yml")) + list(WORKFLOW_DIR.glob("*.yaml")))


def _collect() -> tuple[list[InstallCommand], int, set[tuple[str, str]]]:
    """Return every pip install command, the job count, and the jobs installing deps."""
    commands: list[InstallCommand] = []
    job_count = 0
    dependency_jobs: set[tuple[str, str]] = set()

    for path in _load_workflows():
        document = yaml.safe_load(path.read_text())
        if not isinstance(document, dict):
            continue
        for job_id, job in (document.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            job_count += 1
            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                run = step.get("run")
                if not isinstance(run, str):
                    continue
                step_name = step.get("name", "<unnamed step>")
                for match in _PIP_INSTALL.finditer(run):
                    command = InstallCommand(path.name, job_id, step_name, match.group(0), match.group(1))
                    commands.append(command)
                    if command.requirement_files:
                        dependency_jobs.add((path.name, job_id))

    return commands, job_count, dependency_jobs


@pytest.fixture(scope="module")
def inventory() -> tuple[list[InstallCommand], int, set[tuple[str, str]]]:
    return _collect()


def test_the_guard_actually_inspected_the_workflows(inventory) -> None:
    """A guard that matches nothing is worse than no guard, so prove it matched."""
    commands, job_count, dependency_jobs = inventory
    workflows = _load_workflows()

    assert WORKFLOW_DIR.is_dir(), f"{WORKFLOW_DIR} does not exist — this test is looking in the wrong place"
    assert len(workflows) >= MIN_WORKFLOW_FILES, (
        f"only found {len(workflows)} workflow files under {WORKFLOW_DIR}, expected at least "
        f"{MIN_WORKFLOW_FILES}; the parser or the path is wrong, not the repository"
    )
    assert job_count >= MIN_JOBS_TOTAL, f"only parsed {job_count} jobs, expected at least {MIN_JOBS_TOTAL}"
    assert (
        len(commands) >= MIN_INSTALL_COMMANDS
    ), f"only found {len(commands)} pip install commands, expected at least {MIN_INSTALL_COMMANDS}"
    assert len(dependency_jobs) >= MIN_JOBS_INSTALLING_DEPENDENCIES, (
        f"only found {len(dependency_jobs)} jobs installing from a requirements file, "
        f"expected at least {MIN_JOBS_INSTALLING_DEPENDENCIES}"
    )


def test_no_job_installs_requirements_txt_directly(inventory) -> None:
    """requirements.txt is a specification of ranges, not an installable set."""
    commands, _, _ = inventory
    offenders = [c for c in commands if UNPINNED_ROUTE in c.requirement_files]
    assert not offenders, (
        "these jobs install the unpinned requirements.txt, so they are tested against whatever "
        "PyPI serves at job time rather than an identified dependency set:\n  "
        + "\n  ".join(str(c) for c in offenders)
        + "\n\nInstall `-r requirements.lock` instead. See docs/ci/dependency-environments.md."
    )


def test_dev_tooling_is_only_ever_layered_on_top_of_the_lockfile(inventory) -> None:
    """requirements-dev.txt pulls in requirements.txt, so the lock must come first.

    Installed second, with the locked runtime set already present, pip keeps the
    locked versions because they already satisfy the declared ranges. Installed
    first or alone, it chooses the runtime versions itself.
    """
    commands, _, _ = inventory
    lock_installed_in: set[tuple[str, str]] = {
        (c.workflow, c.job) for c in commands if LOCK_ROUTE in c.requirement_files
    }

    offenders = [
        c for c in commands if DEV_ROUTE in c.requirement_files and (c.workflow, c.job) not in lock_installed_in
    ]
    assert not offenders, (
        "these jobs install requirements-dev.txt without installing requirements.lock in the "
        "same job, so the runtime dependency set is resolved fresh at job time:\n  "
        + "\n  ".join(str(c) for c in offenders)
        + "\n\nAdd `pip install -r requirements.lock` before it."
    )


def test_the_lockfile_is_installed_as_its_own_command(inventory) -> None:
    """The lockfile carries hashes, which puts pip into --require-hashes mode.

    In that mode every requirement in the same invocation must be pinned with a
    hash, so appending an unpinned tool to the lockfile install fails outright.
    Verified by running: `pip install -c requirements.lock -r requirements-dev.txt`
    is rejected with "In --require-hashes mode, all requirements must have their
    versions pinned with ==".
    """
    commands, _, _ = inventory
    offenders = [
        c
        for c in commands
        if LOCK_ROUTE in c.requirement_files and (len(c.requirement_files) > 1 or c.standalone_packages)
    ]
    assert not offenders, (
        "these commands install the hash-pinned lockfile together with something else, which pip "
        "rejects in --require-hashes mode:\n  "
        + "\n  ".join(str(c) for c in offenders)
        + "\n\nSplit them into separate `pip install` commands."
    )


def test_standalone_tool_installs_are_explicitly_known(inventory) -> None:
    """Tools installed by name are allowed, but each one has to be a decision.

    These are unpinned and therefore float — a new bandit or semgrep release can
    add a rule and turn a gate red with no commit. That is a smaller problem than
    floating the application's own dependencies and is deliberately not fixed
    here, but it should not grow silently.
    """
    commands, _, _ = inventory
    unknown: dict[str, list[str]] = {}
    for command in commands:
        if command.requirement_files:
            continue
        for package in command.standalone_packages:
            if package not in ALLOWED_STANDALONE_TOOLS:
                unknown.setdefault(package, []).append(str(command))

    assert not unknown, (
        "these packages are installed by name in CI but are not in the known-tools allowlist:\n  "
        + "\n  ".join(f"{name}: {sites[0]}" for name, sites in sorted(unknown.items()))
        + "\n\nIf it is an application dependency, declare it in requirements.txt and regenerate "
        "the lockfile. If it is a CI tool, add it to ALLOWED_STANDALONE_TOOLS in this test."
    )
