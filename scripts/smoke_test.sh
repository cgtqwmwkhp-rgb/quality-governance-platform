#!/bin/bash
#
# Smoke Test Script for Quality Governance Platform
# 
# Usage:
#   ./scripts/smoke_test.sh <environment_url>
#   ./scripts/smoke_test.sh https://app-qgp-staging.azurewebsites.net
#   ./scripts/smoke_test.sh https://app-qgp-prod.azurewebsites.net
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default URL (can be overridden by argument)
BASE_URL="${1:-http://localhost:8000}"

# Remove trailing slash
BASE_URL="${BASE_URL%/}"

echo ""
echo "=============================================="
echo "  QGP Smoke Test Suite"
echo "=============================================="
echo ""
echo "Target: $BASE_URL"
echo "Time: $(date)"
echo ""

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Test function
test_endpoint() {
    local name="$1"
    local endpoint="$2"
    local expected_status="$3"
    local method="${4:-GET}"
    local data="${5:-}"
    
    printf "  %-40s " "$name"
    
    if [ "$method" = "POST" ] && [ -n "$data" ]; then
        RESPONSE=$(curl -s -o /dev/null -w "%{http_code}|%{time_total}" \
            -X POST \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$BASE_URL$endpoint" 2>/dev/null || echo "000|0")
    else
        RESPONSE=$(curl -s -o /dev/null -w "%{http_code}|%{time_total}" \
            "$BASE_URL$endpoint" 2>/dev/null || echo "000|0")
    fi
    
    STATUS=$(echo $RESPONSE | cut -d'|' -f1)
    TIME=$(echo $RESPONSE | cut -d'|' -f2)
    
    if [ "$STATUS" = "$expected_status" ]; then
        echo -e "${GREEN}PASS${NC} (${STATUS}, ${TIME}s)"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}FAIL${NC} (expected ${expected_status}, got ${STATUS})"
        ((FAILED++))
        return 1
    fi
}

test_endpoint_contains() {
    local name="$1"
    local endpoint="$2"
    local expected_content="$3"
    
    printf "  %-40s " "$name"
    
    RESPONSE=$(curl -s "$BASE_URL$endpoint" 2>/dev/null || echo "")
    
    if echo "$RESPONSE" | grep -q "$expected_content"; then
        echo -e "${GREEN}PASS${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}FAIL${NC} (expected content not found)"
        ((FAILED++))
        return 1
    fi
}

# ============================================================================
# HEALTH CHECKS
# ============================================================================

echo "--- Health Checks ---"
echo ""

test_endpoint "Root endpoint" "/" "200"
test_endpoint "Health check (/healthz)" "/healthz" "200"
test_endpoint "Readiness check (/readyz)" "/readyz" "200"
test_endpoint "Legacy health (/health)" "/health" "200"

echo ""

# ============================================================================
# API DOCUMENTATION
# ============================================================================

echo "--- API Documentation ---"
echo ""

test_endpoint "OpenAPI JSON" "/openapi.json" "200"
test_endpoint "Swagger UI" "/docs" "200"
test_endpoint "ReDoc" "/redoc" "200"

echo ""

# ============================================================================
# AUTHENTICATION (Expected: 401/422 without credentials)
# ============================================================================

echo "--- Authentication Endpoints ---"
echo ""

test_endpoint "GET /auth/me (no auth)" "/api/v1/auth/me" "401"
test_endpoint "POST /auth/login (no body)" "/api/v1/auth/login" "422" "POST"

echo ""

# ============================================================================
# PROTECTED ENDPOINTS (Expected: 401 without auth)
# ============================================================================

echo "--- Protected Endpoints (401 expected) ---"
echo ""

test_endpoint "Incidents list" "/api/v1/incidents" "401"
test_endpoint "Complaints list" "/api/v1/complaints" "401"
test_endpoint "Risks list" "/api/v1/risks" "401"
test_endpoint "Policies list" "/api/v1/policies" "401"
test_endpoint "Standards list" "/api/v1/standards" "401"
test_endpoint "Audits templates" "/api/v1/audits/templates" "401"
test_endpoint "RTAs list" "/api/v1/rtas" "401"
test_endpoint "Users list" "/api/v1/users" "401"

echo ""

# ============================================================================
# CONTENT VALIDATION
# ============================================================================

echo "--- Content Validation ---"
echo ""

test_endpoint_contains "Health response format" "/healthz" "status"
test_endpoint_contains "OpenAPI title" "/openapi.json" "Quality Governance Platform"

echo ""

# ============================================================================
# RESPONSE TIME CHECK
# ============================================================================

echo "--- Response Time Check ---"
echo ""

printf "  %-40s " "Health endpoint latency"
LATENCY=$(curl -s -o /dev/null -w "%{time_total}" "$BASE_URL/healthz" 2>/dev/null || echo "999")

if (( $(echo "$LATENCY < 1.0" | bc -l) )); then
    echo -e "${GREEN}PASS${NC} (${LATENCY}s < 1.0s)"
    ((PASSED++))
elif (( $(echo "$LATENCY < 2.0" | bc -l) )); then
    echo -e "${YELLOW}WARN${NC} (${LATENCY}s - acceptable but slow)"
    ((WARNINGS++))
else
    echo -e "${RED}FAIL${NC} (${LATENCY}s - too slow)"
    ((FAILED++))
fi

echo ""

# ============================================================================
# SUMMARY
# ============================================================================

echo "=============================================="
echo "  RESULTS"
echo "=============================================="
echo ""
echo -e "  Passed:   ${GREEN}$PASSED${NC}"
echo -e "  Warnings: ${YELLOW}$WARNINGS${NC}"
echo -e "  Failed:   ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ ALL SMOKE TESTS PASSED${NC}"
    echo ""
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    echo ""
    exit 1
fi
