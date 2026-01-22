#!/bin/bash
# =============================================================================
# Regression Guard: Prevent email-filter query params in portal code
# =============================================================================
# This script fails if portal frontend code uses email-based query filters
# which could enable email enumeration attacks.
#
# Blocked patterns:
#   - reporter_email= in fetch URLs
#   - complainant_email= in fetch URLs
#
# Safe alternative: Use /portal/my-reports/ endpoint (server-side identity)
# =============================================================================

set -e

PORTAL_DIR="frontend/src"
EXIT_CODE=0

echo "Checking portal code for email-filter query params..."

# Check for reporter_email query param usage
if grep -rn "reporter_email=" "$PORTAL_DIR" --include="*.tsx" --include="*.ts" | grep -v "test" | grep -v ".spec."; then
    echo ""
    echo "ERROR: Found reporter_email query param usage in portal code."
    echo "This is a security issue - email enumeration is possible."
    echo "Use /portal/my-reports/ endpoint instead (server-side identity lookup)."
    EXIT_CODE=1
fi

# Check for complainant_email query param usage
if grep -rn "complainant_email=" "$PORTAL_DIR" --include="*.tsx" --include="*.ts" | grep -v "test" | grep -v ".spec."; then
    echo ""
    echo "ERROR: Found complainant_email query param usage in portal code."
    echo "This is a security issue - email enumeration is possible."
    echo "Use /portal/my-reports/ endpoint instead (server-side identity lookup)."
    EXIT_CODE=1
fi

if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ No email-filter query params found in portal code."
else
    echo ""
    echo "FAILED: Email-filter regression detected."
    exit 1
fi

exit 0
