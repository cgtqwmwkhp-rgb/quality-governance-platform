#!/usr/bin/env bash
set -euo pipefail

# Generates a fully pinned requirements.lock from requirements.txt
# Must be run with Python 3.11+ (matching the Dockerfile target)
#
# Usage:
#   ./scripts/generate_lockfile.sh
#
# CI runs this automatically to verify the lockfile is fresh.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 -m pip install --quiet pip-tools 2>/dev/null || true
python3 -m piptools compile \
    "$REPO_ROOT/requirements.txt" \
    -o "$REPO_ROOT/requirements.lock" \
    --no-header \
    --strip-extras \
    --allow-unsafe \
    --quiet

echo "[OK] requirements.lock generated successfully"
