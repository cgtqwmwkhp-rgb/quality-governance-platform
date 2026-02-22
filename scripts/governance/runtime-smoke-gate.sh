#!/usr/bin/env bash
# =============================================================================
# Runtime Smoke Gate - Critical Endpoint Verification
# =============================================================================
# This script verifies critical endpoints after deployment.
# Critical endpoints returning 5xx will FAIL the deploy unless:
#   1. An allowlist entry exists for the endpoint
#   2. The entry includes the status code in allowed_status_codes
#   3. The entry's expiry_date has not passed
#   4. For status 500: additional policy restrictions apply (see below)
#
# ALLOWLIST POLICY FOR STATUS 500:
#   - reason MUST contain "KNOWN_BUG_TEMPORARY"
#   - expiry_date MUST be within 48 hours of today (UTC)
#   - incident_doc field MUST be present and point to docs/evidence/INC-*.md
#
# Usage:
#   ./runtime-smoke-gate.sh <base_url> <expected_sha> [frontend_origin]
#   ./runtime-smoke-gate.sh --self-test    # Run self-tests (no network)
#
# Exit codes:
#   0 - All checks passed (or self-test passed)
#   1 - One or more critical checks failed
#   2 - Configuration error (missing args, invalid allowlist)
#   3 - Self-test failed
# =============================================================================

set -euo pipefail

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ALLOWLIST_FILE="${ALLOWLIST_FILE:-${REPO_ROOT}/docs/evidence/runtime_smoke_allowlist.json}"
TODAY="${TODAY_OVERRIDE:-$(date -u +%Y-%m-%d)}"
MAX_500_EXPIRY_HOURS=48

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
# Utility Functions
# =============================================================================

# Calculate days between two dates (YYYY-MM-DD format)
# Returns 0 if dates are equal, positive if date2 > date1
days_between() {
  local date1="$1"
  local date2="$2"
  
  # Convert to seconds since epoch (works on both Linux and macOS)
  local sec1 sec2
  if date --version >/dev/null 2>&1; then
    # GNU date (Linux)
    sec1=$(date -d "$date1" +%s 2>/dev/null || echo "0")
    sec2=$(date -d "$date2" +%s 2>/dev/null || echo "0")
  else
    # BSD date (macOS)
    sec1=$(date -j -f "%Y-%m-%d" "$date1" +%s 2>/dev/null || echo "0")
    sec2=$(date -j -f "%Y-%m-%d" "$date2" +%s 2>/dev/null || echo "0")
  fi
  
  local diff=$(( (sec2 - sec1) / 86400 ))
  echo "$diff"
}

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

# Validate allowlist entry for status 500 policy
# Returns 0 if valid, 1 if policy violated
validate_500_policy() {
  local entry="$1"
  local endpoint="$2"
  
  local reason issue_id expiry_date incident_doc
  reason=$(echo "$entry" | jq -r '.reason // ""')
  issue_id=$(echo "$entry" | jq -r '.issue_id // ""')
  expiry_date=$(echo "$entry" | jq -r '.expiry_date // ""')
  incident_doc=$(echo "$entry" | jq -r '.incident_doc // ""')
  
  # Check 1: reason must contain KNOWN_BUG_TEMPORARY
  if [[ "$reason" != *"KNOWN_BUG_TEMPORARY"* ]]; then
    echo "POLICY_VIOLATION: Status 500 allowlist for $endpoint requires reason containing 'KNOWN_BUG_TEMPORARY'"
    echo "  Got: $reason"
    return 1
  fi
  
  # Check 2: incident_doc must be present
  if [ -z "$incident_doc" ] || [ "$incident_doc" = "null" ]; then
    echo "POLICY_VIOLATION: Status 500 allowlist for $endpoint requires 'incident_doc' field"
    echo "  Example: docs/evidence/INC-2026-01-30-CORS.md"
    return 1
  fi
  
  # Check 3: incident_doc must match pattern
  if [[ ! "$incident_doc" =~ ^docs/evidence/INC-.*\.md$ ]]; then
    echo "POLICY_VIOLATION: incident_doc must match pattern docs/evidence/INC-*.md"
    echo "  Got: $incident_doc"
    return 1
  fi
  
  # Check 4: expiry must be within 48 hours
  local days_until_expiry
  days_until_expiry=$(days_between "$TODAY" "$expiry_date")
  
  if [ "$days_until_expiry" -gt 2 ]; then
    echo "POLICY_VIOLATION: Status 500 allowlist expiry must be within 48 hours (2 days)"
    echo "  Today: $TODAY, Expiry: $expiry_date ($days_until_expiry days away)"
    return 1
  fi
  
  return 0
}

# Check if an endpoint/status combo is allowlisted and not expired
# Sets ALLOWLIST_RESULT with message
is_allowlisted() {
  local endpoint="$1"
  local status_code="$2"
  local allowlist
  allowlist=$(load_allowlist)
  
  ALLOWLIST_RESULT=""
  
  # Find matching entry
  local entry
  entry=$(echo "$allowlist" | jq -c --arg ep "$endpoint" --argjson sc "$status_code" \
    '.[] | select(.endpoint == $ep and (.allowed_status_codes | contains([$sc])))' | head -1)
  
  if [ -z "$entry" ]; then
    ALLOWLIST_RESULT="NOT_FOUND: No allowlist entry for $endpoint with status $status_code"
    return 1
  fi
  
  # Check expiry
  local expiry_date
  expiry_date=$(echo "$entry" | jq -r '.expiry_date')
  
  if [[ "$TODAY" > "$expiry_date" ]]; then
    local issue_id
    issue_id=$(echo "$entry" | jq -r '.issue_id')
    ALLOWLIST_RESULT="EXPIRED: Allowlist entry for $endpoint ($issue_id) expired on $expiry_date"
    return 1
  fi
  
  # For status 500, enforce additional policy
  if [ "$status_code" -eq 500 ]; then
    local policy_output
    if ! policy_output=$(validate_500_policy "$entry" "$endpoint"); then
      ALLOWLIST_RESULT="$policy_output"
      return 1
    fi
  fi
  
  # Valid allowlist entry
  local issue_id owner reason
  issue_id=$(echo "$entry" | jq -r '.issue_id')
  owner=$(echo "$entry" | jq -r '.owner')
  reason=$(echo "$entry" | jq -r '.reason')
  ALLOWLIST_RESULT="ALLOWLISTED: $endpoint → $status_code (Issue: $issue_id, Owner: $owner, Expires: $expiry_date)
  Reason: $reason"
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
  
  local start_time end_time
  start_time=$(date +%s%3N 2>/dev/null || date +%s)
  body=$(curl -sS --max-time 10 "$url" 2>/dev/null || echo '{"error":"curl_failed"}')
  status=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")
  end_time=$(date +%s%3N 2>/dev/null || date +%s)
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
      echo "$ALLOWLIST_RESULT"
      echo -e "${YELLOW}⚠️ ALLOWLISTED (non-blocking)${NC}"
      WARNINGS=$((WARNINGS + 1))
      return 0
    else
      echo "$ALLOWLIST_RESULT"
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
# Self-Test Mode
# =============================================================================

run_self_tests() {
  echo "=============================================="
  echo "🧪 Runtime Smoke Gate - Self-Test Mode"
  echo "=============================================="
  echo ""
  
  local test_failures=0
  local test_passes=0
  local temp_dir
  temp_dir=$(mktemp -d)
  
  # --- Test 1: Empty allowlist returns not found ---
  echo "Test 1: Empty allowlist returns NOT_FOUND"
  echo '{"entries":[]}' > "$temp_dir/empty.json"
  ALLOWLIST_FILE="$temp_dir/empty.json"
  
  if is_allowlisted "/api/v1/test" 500; then
    echo -e "${RED}FAIL: Should not be allowlisted${NC}"
    test_failures=$((test_failures + 1))
  else
    if [[ "$ALLOWLIST_RESULT" == *"NOT_FOUND"* ]]; then
      echo -e "${GREEN}PASS${NC}"
      test_passes=$((test_passes + 1))
    else
      echo -e "${RED}FAIL: Wrong result: $ALLOWLIST_RESULT${NC}"
      test_failures=$((test_failures + 1))
    fi
  fi
  echo ""
  
  # --- Test 2: Expired entry is rejected ---
  echo "Test 2: Expired allowlist entry is rejected"
  cat > "$temp_dir/expired.json" << 'ALLOWLIST'
{
  "entries": [{
    "issue_id": "INC-TEST-001",
    "owner": "test",
    "expiry_date": "2020-01-01",
    "reason": "KNOWN_BUG_TEMPORARY: test",
    "endpoint": "/api/v1/test",
    "allowed_status_codes": [503],
    "incident_doc": "docs/evidence/INC-TEST.md"
  }]
}
ALLOWLIST
  ALLOWLIST_FILE="$temp_dir/expired.json"
  
  if is_allowlisted "/api/v1/test" 503; then
    echo -e "${RED}FAIL: Expired entry should be rejected${NC}"
    test_failures=$((test_failures + 1))
  else
    if [[ "$ALLOWLIST_RESULT" == *"EXPIRED"* ]]; then
      echo -e "${GREEN}PASS${NC}"
      test_passes=$((test_passes + 1))
    else
      echo -e "${RED}FAIL: Wrong result: $ALLOWLIST_RESULT${NC}"
      test_failures=$((test_failures + 1))
    fi
  fi
  echo ""
  
  # --- Test 3: Valid 503 entry is allowed ---
  echo "Test 3: Valid 503 entry is allowed (no 500 policy)"
  local future_date
  future_date=$(date -u -v+7d +%Y-%m-%d 2>/dev/null || date -u -d "+7 days" +%Y-%m-%d)
  cat > "$temp_dir/valid503.json" << ALLOWLIST
{
  "entries": [{
    "issue_id": "INC-TEST-002",
    "owner": "test",
    "expiry_date": "$future_date",
    "reason": "Service temporarily unavailable during migration",
    "endpoint": "/api/v1/test",
    "allowed_status_codes": [503]
  }]
}
ALLOWLIST
  ALLOWLIST_FILE="$temp_dir/valid503.json"
  
  if is_allowlisted "/api/v1/test" 503; then
    if [[ "$ALLOWLIST_RESULT" == *"ALLOWLISTED"* ]]; then
      echo -e "${GREEN}PASS${NC}"
      test_passes=$((test_passes + 1))
    else
      echo -e "${RED}FAIL: Wrong result: $ALLOWLIST_RESULT${NC}"
      test_failures=$((test_failures + 1))
    fi
  else
    echo -e "${RED}FAIL: Valid entry should be allowed${NC}"
    test_failures=$((test_failures + 1))
  fi
  echo ""
  
  # --- Test 4: 500 without KNOWN_BUG_TEMPORARY is rejected ---
  echo "Test 4: 500 without KNOWN_BUG_TEMPORARY is rejected"
  local tomorrow
  tomorrow=$(date -u -v+1d +%Y-%m-%d 2>/dev/null || date -u -d "+1 day" +%Y-%m-%d)
  cat > "$temp_dir/500_no_keyword.json" << ALLOWLIST
{
  "entries": [{
    "issue_id": "INC-TEST-003",
    "owner": "test",
    "expiry_date": "$tomorrow",
    "reason": "Database issue",
    "endpoint": "/api/v1/test",
    "allowed_status_codes": [500],
    "incident_doc": "docs/evidence/INC-TEST.md"
  }]
}
ALLOWLIST
  ALLOWLIST_FILE="$temp_dir/500_no_keyword.json"
  
  if is_allowlisted "/api/v1/test" 500; then
    echo -e "${RED}FAIL: 500 without KNOWN_BUG_TEMPORARY should be rejected${NC}"
    test_failures=$((test_failures + 1))
  else
    if [[ "$ALLOWLIST_RESULT" == *"POLICY_VIOLATION"* ]] && [[ "$ALLOWLIST_RESULT" == *"KNOWN_BUG_TEMPORARY"* ]]; then
      echo -e "${GREEN}PASS${NC}"
      test_passes=$((test_passes + 1))
    else
      echo -e "${RED}FAIL: Wrong result: $ALLOWLIST_RESULT${NC}"
      test_failures=$((test_failures + 1))
    fi
  fi
  echo ""
  
  # --- Test 5: 500 without incident_doc is rejected ---
  echo "Test 5: 500 without incident_doc is rejected"
  cat > "$temp_dir/500_no_doc.json" << ALLOWLIST
{
  "entries": [{
    "issue_id": "INC-TEST-004",
    "owner": "test",
    "expiry_date": "$tomorrow",
    "reason": "KNOWN_BUG_TEMPORARY: test issue",
    "endpoint": "/api/v1/test",
    "allowed_status_codes": [500]
  }]
}
ALLOWLIST
  ALLOWLIST_FILE="$temp_dir/500_no_doc.json"
  
  if is_allowlisted "/api/v1/test" 500; then
    echo -e "${RED}FAIL: 500 without incident_doc should be rejected${NC}"
    test_failures=$((test_failures + 1))
  else
    if [[ "$ALLOWLIST_RESULT" == *"POLICY_VIOLATION"* ]] && [[ "$ALLOWLIST_RESULT" == *"incident_doc"* ]]; then
      echo -e "${GREEN}PASS${NC}"
      test_passes=$((test_passes + 1))
    else
      echo -e "${RED}FAIL: Wrong result: $ALLOWLIST_RESULT${NC}"
      test_failures=$((test_failures + 1))
    fi
  fi
  echo ""
  
  # --- Test 6: 500 with expiry > 48 hours is rejected ---
  echo "Test 6: 500 with expiry > 48 hours is rejected"
  local far_future
  far_future=$(date -u -v+10d +%Y-%m-%d 2>/dev/null || date -u -d "+10 days" +%Y-%m-%d)
  cat > "$temp_dir/500_long_expiry.json" << ALLOWLIST
{
  "entries": [{
    "issue_id": "INC-TEST-005",
    "owner": "test",
    "expiry_date": "$far_future",
    "reason": "KNOWN_BUG_TEMPORARY: test issue",
    "endpoint": "/api/v1/test",
    "allowed_status_codes": [500],
    "incident_doc": "docs/evidence/INC-TEST.md"
  }]
}
ALLOWLIST
  ALLOWLIST_FILE="$temp_dir/500_long_expiry.json"
  
  if is_allowlisted "/api/v1/test" 500; then
    echo -e "${RED}FAIL: 500 with expiry > 48h should be rejected${NC}"
    test_failures=$((test_failures + 1))
  else
    if [[ "$ALLOWLIST_RESULT" == *"POLICY_VIOLATION"* ]] && [[ "$ALLOWLIST_RESULT" == *"48 hours"* ]]; then
      echo -e "${GREEN}PASS${NC}"
      test_passes=$((test_passes + 1))
    else
      echo -e "${RED}FAIL: Wrong result: $ALLOWLIST_RESULT${NC}"
      test_failures=$((test_failures + 1))
    fi
  fi
  echo ""
  
  # --- Test 7: Valid 500 entry with all requirements passes ---
  echo "Test 7: Valid 500 entry with all requirements passes"
  cat > "$temp_dir/500_valid.json" << ALLOWLIST
{
  "entries": [{
    "issue_id": "INC-TEST-006",
    "owner": "test",
    "expiry_date": "$tomorrow",
    "reason": "KNOWN_BUG_TEMPORARY: Database migration in progress",
    "endpoint": "/api/v1/test",
    "allowed_status_codes": [500],
    "incident_doc": "docs/evidence/INC-TEST-006.md"
  }]
}
ALLOWLIST
  ALLOWLIST_FILE="$temp_dir/500_valid.json"
  
  if is_allowlisted "/api/v1/test" 500; then
    if [[ "$ALLOWLIST_RESULT" == *"ALLOWLISTED"* ]]; then
      echo -e "${GREEN}PASS${NC}"
      test_passes=$((test_passes + 1))
    else
      echo -e "${RED}FAIL: Wrong result: $ALLOWLIST_RESULT${NC}"
      test_failures=$((test_failures + 1))
    fi
  else
    echo -e "${RED}FAIL: Valid 500 entry should be allowed: $ALLOWLIST_RESULT${NC}"
    test_failures=$((test_failures + 1))
  fi
  echo ""
  
  # Cleanup
  rm -rf "$temp_dir"
  
  # --- Summary ---
  echo "=============================================="
  echo "🧪 Self-Test Summary"
  echo "=============================================="
  echo "Passed: $test_passes"
  echo "Failed: $test_failures"
  echo ""
  
  if [ "$test_failures" -gt 0 ]; then
    echo -e "${RED}❌ SELF-TEST FAILED${NC}"
    exit 3
  fi
  
  echo -e "${GREEN}✅ ALL SELF-TESTS PASSED${NC}"
  exit 0
}

# =============================================================================
# Main
# =============================================================================

# Check for self-test mode
if [ "${1:-}" = "--self-test" ]; then
  run_self_tests
  exit $?
fi

# --- Arguments ---
BASE_URL="${1:-}"
EXPECTED_SHA="${2:-}"
FRONTEND_ORIGIN="${3:-https://app-qgp-prod.azurestaticapps.net}"

if [ -z "$BASE_URL" ] || [ -z "$EXPECTED_SHA" ]; then
  echo "Usage: $0 <base_url> <expected_sha> [frontend_origin]"
  echo "       $0 --self-test"
  exit 2
fi

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

check_endpoint "UVDB Sections" "/api/v1/uvdb/sections" "401" "true" || true
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
  echo "For status 503 (service unavailable):"
  echo '  {
    "issue_id": "INC-YYYY-MM-DD-DESC",
    "owner": "your-github-username",
    "expiry_date": "YYYY-MM-DD",
    "reason": "Brief explanation",
    "endpoint": "/api/v1/endpoint",
    "allowed_status_codes": [503]
  }'
  echo ""
  echo "For status 500 (STRICT POLICY - requires all of the following):"
  echo '  {
    "issue_id": "INC-YYYY-MM-DD-DESC",
    "owner": "your-github-username",
    "expiry_date": "YYYY-MM-DD",  ← MUST be within 48 hours
    "reason": "KNOWN_BUG_TEMPORARY: ...",  ← MUST contain this keyword
    "endpoint": "/api/v1/endpoint",
    "allowed_status_codes": [500],
    "incident_doc": "docs/evidence/INC-XXX.md"  ← REQUIRED for 500
  }'
  exit 1
fi

echo -e "${GREEN}✅ SMOKE GATE PASSED${NC}"
if [ "$WARNINGS" -gt 0 ]; then
  echo "  (with $WARNINGS warnings)"
fi
exit 0
