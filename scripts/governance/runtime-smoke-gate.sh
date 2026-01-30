#!/usr/bin/env bash
# =============================================================================
# Runtime Smoke Gate - Critical Endpoint Verification
# =============================================================================
# This script verifies critical endpoints after deployment.
# Critical endpoints returning 5xx will FAIL the deploy unless:
#   1. An allowlist entry exists for the endpoint
#   2. The entry includes the status code in allowed_status_codes
#   3. The entry's expiry_date has not passed
#
# Usage: ./runtime-smoke-gate.sh <base_url> <expected_sha> <frontend_origin>
# Exit codes:
#   0 - All checks passed
#   1 - One or more critical checks failed
#   2 - Configuration error (missing args, invalid allowlist)
# =============================================================================

set -euo pipefail

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ALLOWLIST_FILE="${REPO_ROOT}/docs/evidence/runtime_smoke_allowlist.json"
TODAY=$(date -u +%Y-%m-%d)

# --- Arguments ---
BASE_URL="${1:-}"
EXPECTED_SHA="${2:-}"
FRONTEND_ORIGIN="${3:-https://app-qgp-prod.azurestaticapps.net}"

if [ -z "$BASE_URL" ] || [ -z "$EXPECTED_SHA" ]; then
  echo "Usage: $0 <base_url> <expected_sha> [frontend_origin]"
  exit 2
fi

# --- Counters ---
FAILURES=0
WARNINGS=0
CHECKS_PASSED=0

# --- Colors for output ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# =============================================================================
# Allowlist Functions
# =============================================================================

load_allowlist() {
  if [ ! -f "$ALLOWLIST_FILE" ]; then
    echo "[]"
    return
  fi
  jq -c '.entries // []' "$ALLOWLIST_FILE" 2>/dev/null || echo "[]"
}

# Check if an endpoint/status combo is allowlisted and not expired
is_allowlisted() {
  local endpoint="$1"
  local status_code="$2"
  local allowlist
  allowlist=$(load_allowlist)
  
  # Find matching entry
  local entry
  entry=$(echo "$allowlist" | jq -c --arg ep "$endpoint" --argjson sc "$status_code" \
    '.[] | select(.endpoint == $ep and (.allowed_status_codes | contains([$sc])))')
  
  if [ -z "$entry" ]; then
    return 1  # Not allowlisted
  fi
  
  # Check expiry
  local expiry_date
  expiry_date=$(echo "$entry" | jq -r '.expiry_date')
  
  if [[ "$TODAY" > "$expiry_date" ]]; then
    local issue_id
    issue_id=$(echo "$entry" | jq -r '.issue_id')
    echo "EXPIRED: Allowlist entry for $endpoint ($issue_id) expired on $expiry_date"
    return 1  # Expired
  fi
  
  # Valid allowlist entry
  local issue_id owner reason
  issue_id=$(echo "$entry" | jq -r '.issue_id')
  owner=$(echo "$entry" | jq -r '.owner')
  reason=$(echo "$entry" | jq -r '.reason')
  echo "ALLOWLISTED: $endpoint → $status_code (Issue: $issue_id, Owner: $owner, Expires: $expiry_date)"
  echo "  Reason: $reason"
  return 0
}

# =============================================================================
# Check Functions
# =============================================================================

check_endpoint() {
  local name="$1"
  local endpoint="$2"
  local expected_status="${3:-200}"
  local is_critical="${4:-true}"
  
  local url="${BASE_URL}${endpoint}"
  local status body latency_ms
  
  local start_time=$(date +%s%3N)
  body=$(curl -sS --max-time 10 "$url" 2>/dev/null || echo '{"error":"curl_failed"}')
  status=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")
  local end_time=$(date +%s%3N)
  latency_ms=$((end_time - start_time))
  
  echo "--- $name ---"
  echo "Endpoint: $endpoint"
  echo "Status: $status (expected: $expected_status)"
  echo "Latency: ${latency_ms}ms"
  
  if [ "$status" = "$expected_status" ]; then
    echo -e "${GREEN}✅ PASS${NC}"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
    return 0
  fi
  
  # Check if it's a 5xx error
  if [[ "$status" =~ ^5[0-9][0-9]$ ]]; then
    # Check allowlist
    if is_allowlisted "$endpoint" "$status"; then
      echo -e "${YELLOW}⚠️ ALLOWLISTED (non-blocking)${NC}"
      WARNINGS=$((WARNINGS + 1))
      return 0
    fi
    
    if [ "$is_critical" = "true" ]; then
      echo -e "${RED}❌ CRITICAL FAILURE: 5xx on critical endpoint${NC}"
      echo "Response: $(echo "$body" | head -c 300)"
      FAILURES=$((FAILURES + 1))
      return 1
    fi
  fi
  
  # Non-5xx failure (e.g., 404, 422)
  if [ "$is_critical" = "true" ]; then
    echo -e "${RED}❌ FAIL: Unexpected status $status${NC}"
    FAILURES=$((FAILURES + 1))
    return 1
  else
    echo -e "${YELLOW}⚠️ WARNING: Status $status (non-critical)${NC}"
    WARNINGS=$((WARNINGS + 1))
    return 0
  fi
}

check_cors_preflight() {
  local endpoint="$1"
  local origin="$2"
  
  local url="${BASE_URL}${endpoint}"
  local headers status acao_header
  
  headers=$(curl -sS -X OPTIONS "$url" \
    -H "Origin: $origin" \
    -H "Access-Control-Request-Method: GET" \
    -H "Access-Control-Request-Headers: Authorization" \
    --max-time 10 \
    -D - -o /dev/null 2>/dev/null || echo "CURL_FAILED")
  
  status=$(echo "$headers" | head -1 | grep -oE "[0-9]{3}" || echo "000")
  acao_header=$(echo "$headers" | grep -i "access-control-allow-origin" | cut -d: -f2- | tr -d '[:space:]' || echo "missing")
  
  echo "--- CORS Preflight: $endpoint ---"
  echo "Origin: $origin"
  echo "Status: $status"
  echo "ACAO Header: $acao_header"
  
  if [ "$acao_header" = "$origin" ]; then
    echo -e "${GREEN}✅ CORS PASS${NC}"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
    return 0
  elif [ "$acao_header" != "missing" ]; then
    echo -e "${YELLOW}⚠️ CORS MISMATCH: Expected $origin, got $acao_header${NC}"
    WARNINGS=$((WARNINGS + 1))
    return 0
  else
    echo -e "${RED}❌ CORS FAIL: No Access-Control-Allow-Origin header${NC}"
    FAILURES=$((FAILURES + 1))
    return 1
  fi
}

check_build_sha() {
  local version_body
  version_body=$(curl -sS --max-time 10 "${BASE_URL}/api/v1/meta/version" 2>/dev/null || echo '{}')
  local deployed_sha
  deployed_sha=$(echo "$version_body" | jq -r '.build_sha // "unknown"')
  
  echo "--- Build SHA Verification ---"
  echo "Expected: $EXPECTED_SHA"
  echo "Deployed: $deployed_sha"
  
  if [ "$deployed_sha" = "$EXPECTED_SHA" ]; then
    echo -e "${GREEN}✅ SHA MATCH${NC}"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
    return 0
  else
    echo -e "${RED}❌ SHA MISMATCH${NC}"
    FAILURES=$((FAILURES + 1))
    return 1
  fi
}

# =============================================================================
# Main
# =============================================================================

echo "=============================================="
echo "🔥 Runtime Smoke Gate - Critical Verification"
echo "=============================================="
echo "Base URL: $BASE_URL"
echo "Expected SHA: $EXPECTED_SHA"
echo "Frontend Origin: $FRONTEND_ORIGIN"
echo "Date: $TODAY"
echo ""

# Load and validate allowlist
if [ -f "$ALLOWLIST_FILE" ]; then
  ENTRY_COUNT=$(jq '.entries | length' "$ALLOWLIST_FILE" 2>/dev/null || echo "0")
  echo "Allowlist entries: $ENTRY_COUNT"
  
  # Show any active entries
  if [ "$ENTRY_COUNT" -gt 0 ]; then
    echo "Active allowlist entries:"
    jq -r '.entries[] | "  - \(.endpoint): \(.allowed_status_codes | join(",")) (expires: \(.expiry_date), issue: \(.issue_id))"' "$ALLOWLIST_FILE" 2>/dev/null || true
  fi
else
  echo "No allowlist file found (all 5xx errors will fail)"
fi
echo ""

# --- Critical Checks ---
echo "=== CRITICAL ENDPOINT CHECKS ==="
echo ""

check_build_sha || true
echo ""

check_endpoint "Health Check" "/health" "200" "true" || true
echo ""

check_endpoint "Readiness Check" "/readyz" "200" "true" || true
echo ""

check_endpoint "UVDB Sections" "/api/v1/uvdb/sections" "200" "true" || true
echo ""

check_endpoint "PlanetMark Dashboard" "/api/v1/planet-mark/dashboard" "200" "true" || true
echo ""

check_endpoint "PlanetMark ISO Mapping" "/api/v1/planet-mark/iso14001-mapping" "200" "true" || true
echo ""

# --- CORS Checks ---
echo "=== CORS VERIFICATION ==="
echo ""

check_cors_preflight "/api/v1/meta/version" "$FRONTEND_ORIGIN" || true
echo ""

# Also check the auto-generated SWA origin
check_cors_preflight "/api/v1/meta/version" "https://purple-water-03205fa03.6.azurestaticapps.net" || true
echo ""

# --- Summary ---
echo "=============================================="
echo "🔥 Runtime Smoke Gate Summary"
echo "=============================================="
echo "Checks Passed: $CHECKS_PASSED"
echo "Warnings: $WARNINGS"
echo "Failures: $FAILURES"
echo ""

if [ "$FAILURES" -gt 0 ]; then
  echo -e "${RED}❌ SMOKE GATE FAILED: $FAILURES critical check(s) failed${NC}"
  echo ""
  echo "To temporarily allow a failing endpoint, add an entry to:"
  echo "  $ALLOWLIST_FILE"
  echo ""
  echo "Example entry:"
  echo '  {
    "issue_id": "INC-YYYY-MM-DD-DESC",
    "owner": "your-github-username",
    "expiry_date": "YYYY-MM-DD",
    "reason": "Brief explanation of why this is temporarily allowed",
    "endpoint": "/api/v1/endpoint",
    "allowed_status_codes": [500]
  }'
  exit 1
fi

echo -e "${GREEN}✅ SMOKE GATE PASSED${NC}"
if [ "$WARNINGS" -gt 0 ]; then
  echo "  (with $WARNINGS warnings)"
fi
exit 0
