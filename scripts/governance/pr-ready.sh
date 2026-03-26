#!/usr/bin/env bash
set -euo pipefail

python_bin="${PYTHON_BIN:-./.venv/bin/python}"
branch_name="$(git rev-parse --abbrev-ref HEAD)"

if [[ "$branch_name" == "main" || "$branch_name" == "master" ]]; then
  echo "Do not work from local $branch_name."
  echo "Create a branch from origin/main first:"
  echo "  make start-branch BRANCH=fix/your-change"
  exit 1
fi

if [[ ! -x "$python_bin" ]]; then
  echo "Expected Python 3.11 virtualenv at $python_bin"
  echo "Create it first, then run: make install"
  exit 1
fi

if [[ ! -d "frontend/node_modules" ]]; then
  echo "frontend/node_modules is missing."
  echo "Run: make install"
  exit 1
fi

echo "Fetching latest origin/main for branch hygiene check..."
git fetch origin

echo "Checking branch ancestry..."
merge_base="$(git merge-base HEAD origin/main)"
remote_main_sha="$(git rev-parse origin/main)"
if [[ "$merge_base" != "$remote_main_sha" ]]; then
  echo "Warning: your branch is not based on the latest origin/main."
  echo "Rebase or recreate the branch from origin/main before opening the PR."
  exit 1
fi

echo "Running backend code-quality gates..."
"$python_bin" -m black --check src/ tests/
"$python_bin" -m isort --check-only --settings-path pyproject.toml src/ tests/
"$python_bin" -m flake8 src/ tests/
"$python_bin" scripts/validate_type_ignores.py
"$python_bin" -m mypy src/ --config-file pyproject.toml
"$python_bin" scripts/check_mock_data.py --repo-root .

echo "Running backend unit tests..."
"$python_bin" -m pytest tests/unit/ -q

echo "Running frontend gates..."
(
  cd frontend
  npx eslint src/ --max-warnings 0
  npx vitest run --passWithNoTests
)

echo "PR-ready checks passed."
echo "When creating a PR with gh CLI, use:"
echo "  gh pr create --body-file scripts/governance/pr_body_template.md"
