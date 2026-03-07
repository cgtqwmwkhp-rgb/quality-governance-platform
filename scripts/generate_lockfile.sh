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

PYTHON_BIN="python3"
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
fi

"$PYTHON_BIN" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" || {
  echo "[FAIL] Python 3.11+ required to generate requirements.lock"
  echo "[INFO] Activate a 3.11 venv or run from CI"
  exit 1
}

"$PYTHON_BIN" -m pip install --quiet pip-tools 2>/dev/null || true
"$PYTHON_BIN" -m piptools compile \
    "requirements.txt" \
    -o "$REPO_ROOT/requirements.lock" \
    --no-header \
    --strip-extras \
    --allow-unsafe \
    --generate-hashes \
    --quiet

echo "[OK] requirements.lock generated successfully (with hashes)"
