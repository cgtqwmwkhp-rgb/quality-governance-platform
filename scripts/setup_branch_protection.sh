#!/usr/bin/env bash
set -euo pipefail

REPO="cgtqwmwkhp-rgb/quality-governance-platform"
BRANCH="main"

echo "Setting up branch protection for $REPO ($BRANCH)..."

gh api \
  --method PUT \
  "/repos/$REPO/branches/$BRANCH/protection" \
  --input - <<EOF
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Code Quality",
      "Unit Tests",
      "Integration Tests",
      "Build Check",
      "Security Scan"
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF

echo "Branch protection configured successfully!"
echo ""
echo "Protection rules applied:"
echo "  - Required status checks (strict): Code Quality, Unit Tests, Integration Tests, Build, Security"
echo "  - Required PR reviews: 1 approver, stale reviews dismissed"
echo "  - Linear history required (squash/rebase only)"
echo "  - Force pushes disabled"
echo "  - Branch deletion disabled"
