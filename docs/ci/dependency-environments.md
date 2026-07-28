# Getting a Python environment that matches CI

CI installs `requirements.lock`, which is hash-pinned and fully resolved. It does
not install `requirements.txt`, which declares 32 of its 45 direct dependencies
as version ranges and therefore resolves differently depending on when you run it.

## Build the environment

Python 3.11 — the same minor version CI and the Dockerfile use.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.lock      # the runtime set, hash-verified
pip install -r requirements-dev.txt   # test and lint tooling, on top
```

The order matters. `requirements-dev.txt` begins with `-r requirements.txt`, so
installing it first lets pip choose the runtime versions itself. Installed
second, the locked versions are already present and already satisfy the declared
ranges, so pip leaves them alone.

Install the lockfile as its own command. It carries hashes, which puts pip into
`--require-hashes` mode, and in that mode every requirement in the same
invocation must be pinned with `==` — appending anything unpinned fails.

## Check your environment matches

```bash
pytest tests/test_lockfile_environment_match.py -q
```

This compares every pin in `requirements.lock` against what is actually
importable and names anything that differs. Run it before concluding that a test
failure is a code problem: a stale virtualenv produces failures that do not
reproduce in CI, and CI results that do not reproduce locally.

## Change a dependency

1. Edit `requirements.txt` (or `requirements-dev.txt` for tooling).
2. Regenerate the lockfile: `./scripts/generate_lockfile.sh`
3. Commit `requirements.txt` and `requirements.lock` together.

Step 3 is not optional. `scripts/verify_lockfile.py` runs in CI as a blocking
check and fails when a declared version is not satisfied by the lockfile, so a
bump committed without regenerating the lock cannot merge. This is why Dependabot
pull requests, which only edit `requirements.txt`, need the lockfile regenerated
before they go green.

To move pins forward within the existing declared ranges without changing
`requirements.txt`, run `LOCKFILE_UPGRADE=1 ./scripts/generate_lockfile.sh`.

## Two limits worth knowing

**The lockfile covers runtime dependencies only.** It is compiled from
`requirements.txt`, so `pytest`, `black`, `mypy`, `flake8`, `locust`,
`hypothesis`, `schemathesis` and around 90 other packages come from
`requirements-dev.txt` as ranges and still resolve fresh at job time. A new
`black` or `mypy` release can therefore turn a gate red with no commit. Locking
the development set requires a second lockfile and has not been done.

**Analysis tools installed by name in CI are unpinned.** `bandit`, `semgrep`,
`pip-audit`, `radon`, `pip-licenses` and similar are installed without a version.
They are enumerated in `tests/test_dependency_workflow_pinning.py` so the list
cannot grow unnoticed, but they are not pinned.
