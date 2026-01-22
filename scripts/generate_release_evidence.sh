#!/bin/bash
# =============================================================================
# Release Evidence Generator
# Enterprise-grade deployment verification and evidence collection
# =============================================================================

set -euo pipefail

# Configuration
ENVIRONMENT="${1:-staging}"
APP_URL="${2:-http://localhost:8000}"
COMMIT_SHA="${3:-unknown}"
EVIDENCE_FILE="release-evidence-${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S).md"

echo "=== RELEASE EVIDENCE GENERATION ==="
echo "Environment: $ENVIRONMENT"
echo "App URL: $APP_URL"
echo "Commit: $COMMIT_SHA"
echo "Output: $EVIDENCE_FILE"
echo ""

# Initialize evidence file
cat > "$EVIDENCE_FILE" << EOF
# Release Evidence Report

| Field | Value |
|-------|-------|
| **Environment** | $ENVIRONMENT |
| **Timestamp** | $(date -u +"%Y-%m-%dT%H:%M:%SZ") |
| **Commit SHA** | \`$COMMIT_SHA\` |
| **Generator** | release-evidence v1.0 |

---

## Verification Results

EOF

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

# Helper function to record test result
record_result() {
    local test_name="$1"
    local status="$2"
    local details="$3"
    
    if [ "$status" = "PASS" ]; then
        echo "| $test_name | ✅ PASS | $details |" >> "$EVIDENCE_FILE"
        PASS_COUNT=$((PASS_COUNT + 1))
    elif [ "$status" = "FAIL" ]; then
        echo "| $test_name | ❌ FAIL | $details |" >> "$EVIDENCE_FILE"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    else
        echo "| $test_name | ⚠️ WARN | $details |" >> "$EVIDENCE_FILE"
        WARN_COUNT=$((WARN_COUNT + 1))
    fi
}

echo "| Test | Status | Details |" >> "$EVIDENCE_FILE"
echo "|------|--------|---------|" >> "$EVIDENCE_FILE"

# =============================================================================
# Test 1: Health Check
# =============================================================================
echo "Testing: Health endpoint (/healthz)..."
HEALTH_RESPONSE=$(curl -s --max-time 30 "$APP_URL/healthz" 2>/dev/null || echo '{"error":"connection_failed"}')
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 "$APP_URL/healthz" 2>/dev/null || echo "000")

if [ "$HEALTH_STATUS" = "200" ] && echo "$HEALTH_RESPONSE" | grep -q '"status"'; then
    record_result "Health Check" "PASS" "HTTP $HEALTH_STATUS - status field present"
else
    record_result "Health Check" "FAIL" "HTTP $HEALTH_STATUS"
fi

# =============================================================================
# Test 2: Readiness Check
# =============================================================================
echo "Testing: Readiness endpoint (/readyz)..."
READY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 "$APP_URL/readyz" 2>/dev/null || echo "000")

if [ "$READY_STATUS" = "200" ]; then
    record_result "Readiness Check" "PASS" "HTTP $READY_STATUS"
else
    record_result "Readiness Check" "WARN" "HTTP $READY_STATUS (may be starting)"
fi

# =============================================================================
# Test 3: Auth Enforcement
# =============================================================================
echo "Testing: Auth enforcement (protected endpoint)..."
AUTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 "$APP_URL/api/v1/incidents/" 2>/dev/null || echo "000")

if [ "$AUTH_STATUS" = "401" ]; then
    record_result "Auth Enforcement" "PASS" "HTTP $AUTH_STATUS - correctly rejects unauthenticated"
elif [ "$AUTH_STATUS" = "403" ]; then
    record_result "Auth Enforcement" "PASS" "HTTP $AUTH_STATUS - correctly rejects unauthorized"
else
    record_result "Auth Enforcement" "FAIL" "HTTP $AUTH_STATUS - expected 401/403"
fi

# =============================================================================
# Test 4: Rate Limiting Headers
# =============================================================================
echo "Testing: Rate limiting headers..."
RATE_HEADERS=$(curl -sI --max-time 30 "$APP_URL/api/v1/incidents/" 2>&1 | grep -i "x-ratelimit" || echo "")

if [ -n "$RATE_HEADERS" ]; then
    # Sanitize headers (remove any sensitive values, keep only header names)
    SANITIZED=$(echo "$RATE_HEADERS" | sed 's/:.*/:***/' | tr '\n' ' ')
    record_result "Rate Limit Headers" "PASS" "Headers present: $SANITIZED"
else
    record_result "Rate Limit Headers" "WARN" "No x-ratelimit headers found"
fi

# =============================================================================
# Test 5: Security Headers
# =============================================================================
echo "Testing: Security headers..."
SEC_HEADERS=$(curl -sI --max-time 30 "$APP_URL/healthz" 2>&1)

XFRAME=$(echo "$SEC_HEADERS" | grep -i "x-frame-options" | head -1 || echo "")
XCONTENT=$(echo "$SEC_HEADERS" | grep -i "x-content-type-options" | head -1 || echo "")

if [ -n "$XFRAME" ] && [ -n "$XCONTENT" ]; then
    record_result "Security Headers" "PASS" "X-Frame-Options + X-Content-Type-Options present"
else
    record_result "Security Headers" "WARN" "Some security headers missing"
fi

# =============================================================================
# Test 6: OpenAPI Spec Available
# =============================================================================
echo "Testing: OpenAPI specification..."
OPENAPI_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 "$APP_URL/openapi.json" 2>/dev/null || echo "000")

if [ "$OPENAPI_STATUS" = "200" ]; then
    record_result "OpenAPI Spec" "PASS" "HTTP $OPENAPI_STATUS - spec accessible"
else
    record_result "OpenAPI Spec" "WARN" "HTTP $OPENAPI_STATUS"
fi

# =============================================================================
# Test 7: Portal Endpoint (Public)
# =============================================================================
echo "Testing: Portal endpoint (public)..."
PORTAL_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 "$APP_URL/api/v1/portal/reports/" -X POST -H "Content-Type: application/json" -d '{}' 2>/dev/null || echo "000")

if [ "$PORTAL_STATUS" = "422" ]; then
    record_result "Portal Endpoint" "PASS" "HTTP $PORTAL_STATUS - validation working"
elif [ "$PORTAL_STATUS" = "201" ] || [ "$PORTAL_STATUS" = "200" ]; then
    record_result "Portal Endpoint" "PASS" "HTTP $PORTAL_STATUS - endpoint accessible"
else
    record_result "Portal Endpoint" "WARN" "HTTP $PORTAL_STATUS"
fi

# =============================================================================
# Summary
# =============================================================================
echo "" >> "$EVIDENCE_FILE"
echo "---" >> "$EVIDENCE_FILE"
echo "" >> "$EVIDENCE_FILE"
echo "## Summary" >> "$EVIDENCE_FILE"
echo "" >> "$EVIDENCE_FILE"
echo "| Metric | Count |" >> "$EVIDENCE_FILE"
echo "|--------|-------|" >> "$EVIDENCE_FILE"
echo "| Passed | $PASS_COUNT |" >> "$EVIDENCE_FILE"
echo "| Failed | $FAIL_COUNT |" >> "$EVIDENCE_FILE"
echo "| Warnings | $WARN_COUNT |" >> "$EVIDENCE_FILE"
echo "" >> "$EVIDENCE_FILE"

if [ $FAIL_COUNT -eq 0 ]; then
    echo "**Overall Status:** ✅ RELEASE APPROVED" >> "$EVIDENCE_FILE"
    echo ""
    echo "✅ Release evidence generated: $EVIDENCE_FILE"
    echo "   Passed: $PASS_COUNT, Failed: $FAIL_COUNT, Warnings: $WARN_COUNT"
    exit 0
else
    echo "**Overall Status:** ❌ RELEASE BLOCKED" >> "$EVIDENCE_FILE"
    echo ""
    echo "❌ Release evidence shows failures: $EVIDENCE_FILE"
    echo "   Passed: $PASS_COUNT, Failed: $FAIL_COUNT, Warnings: $WARN_COUNT"
    exit 1
fi
