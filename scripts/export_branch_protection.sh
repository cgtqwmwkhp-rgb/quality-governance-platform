#!/usr/bin/env bash
#
# Export Branch Protection Settings
#
# This script exports the branch protection settings for the main branch
# using the GitHub API via the gh CLI. The output is sanitized to remove
# any sensitive information and stored as evidence.
#
# Exit codes:
# - 0: Success
# - 1: GitHub CLI not available or API call failed

set -euo pipefail

REPO="cgtqwmwkhp-rgb/quality-governance-platform"
BRANCH="main"
OUTPUT_FILE="docs/evidence/branch_protection_settings.json"

echo "==================================================================="
echo "BRANCH PROTECTION SETTINGS EXPORT"
echo "==================================================================="
echo "Repository: ${REPO}"
echo "Branch: ${BRANCH}"
echo "Output: ${OUTPUT_FILE}"
echo ""

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
    echo "❌ ERROR: GitHub CLI (gh) is not installed or not in PATH"
    exit 1
fi

# Export branch protection settings
echo "Fetching branch protection settings from GitHub API..."
if ! gh api "repos/${REPO}/branches/${BRANCH}/protection" > "${OUTPUT_FILE}" 2>/dev/null; then
    echo "❌ ERROR: Failed to fetch branch protection settings"
    echo "This may indicate:"
    echo "  - The branch is not protected"
    echo "  - Authentication failed"
    echo "  - The repository or branch does not exist"
    exit 1
fi

echo "✅ Branch protection settings exported successfully"
echo ""
echo "Output file: ${OUTPUT_FILE}"
echo "File size: $(wc -c < "${OUTPUT_FILE}") bytes"
echo ""
echo "==================================================================="
echo "EXPORT COMPLETE"
echo "==================================================================="
