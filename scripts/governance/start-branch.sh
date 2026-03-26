#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <branch-name>"
  echo "Example: $0 fix/external-audit-import-workflow"
  exit 1
fi

branch_name="$1"

case "$branch_name" in
  feat/*|fix/*|chore/*|docs/*|refactor/*|test/*|perf/*|ci/*) ;;
  *)
    echo "Branch name must start with feat/, fix/, chore/, docs/, refactor/, test/, perf/, or ci/"
    exit 1
    ;;
esac

if git show-ref --verify --quiet "refs/heads/$branch_name"; then
  echo "Local branch '$branch_name' already exists."
  exit 1
fi

echo "Fetching latest origin/main..."
git fetch origin

echo "Creating '$branch_name' from origin/main..."
git switch -c "$branch_name" --track origin/main

echo "Ready. New work is now based on origin/main, not local main."
