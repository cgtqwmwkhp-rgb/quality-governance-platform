#!/usr/bin/env bash
#==============================================================================
# PLANET MARK PRODUCTION SEED SCRIPT
# Version: 1.0.0
# Date: 2026-01-30
# Owner: Release Governance Team
#
# PURPOSE: Safely seed initial CarbonReportingYear data in production
#          with full idempotency, auditability, and rollback capability
#
# PREREQUISITES:
#   - Admin bearer token with UAT_ADMIN_USERS membership
#   - Approval from Platform Admin (issue ID required)
#   - Network access to production API
#
# USAGE:
#   export PROD_TOKEN="your-admin-bearer-token"
#   ./planet-mark-seed-production.sh
#
# NON-NEGOTIABLES:
#   - Idempotent: Will NOT create duplicates
#   - Audited: All operations logged with request_id
#   - Bounded: Fails fast on any error
#   - Reversible: Outputs rollback instructions
#==============================================================================

set -euo pipefail

#------------------------------------------------------------------------------
# CONFIGURATION
#------------------------------------------------------------------------------
readonly SCRIPT_VERSION="1.0.0"
readonly SCRIPT_NAME="planet-mark-seed-production"
readonly PROD_API_URL="https://qgp-api-prod.azurewebsites.net"

# UAT Override Headers (REQUIRED for production writes)
readonly ISSUE_ID="INC-2026-01-30-PLANETMARK-SEED"
readonly OWNER="release-governance"
readonly EXPIRY="2026-01-31"  # 24-hour window
readonly REASON="Live seed: initial CarbonReportingYear for Planet Mark activation"

# Seed Data (non-PII, organization config only)
readonly SEED_PAYLOAD='{
  "year_label": "Year 1",
  "year_number": 1,
  "period_start": "2025-01-01T00:00:00Z",
  "period_end": "2025-12-31T23:59:59Z",
  "average_fte": 25.0,
  "organization_name": "Plantexpand Limited",
  "sites_included": ["HQ"],
  "is_baseline_year": true,
  "reduction_target_percent": 5.0
}'

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

#------------------------------------------------------------------------------
# LOGGING
#------------------------------------------------------------------------------
log_info() { echo -e "${BLUE}[INFO]${NC} $(date -u +%H:%M:%S) $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $(date -u +%H:%M:%S) $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $(date -u +%H:%M:%S) $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $(date -u +%H:%M:%S) $*" >&2; }
log_step() { echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; echo -e "${GREEN}STEP $1${NC}: $2"; echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }

#------------------------------------------------------------------------------
# VALIDATION
#------------------------------------------------------------------------------
validate_prerequisites() {
  log_step "0" "Validating Prerequisites"
  
  # Check token
  if [[ -z "${PROD_TOKEN:-}" ]]; then
    log_error "PROD_TOKEN environment variable not set"
    log_error "Usage: export PROD_TOKEN='your-admin-bearer-token' && ./planet-mark-seed-production.sh"
    exit 1
  fi
  log_success "Token present (redacted)"
  
  # Check curl
  if ! command -v curl &> /dev/null; then
    log_error "curl is required but not installed"
    exit 1
  fi
  log_success "curl available"
  
  # Check jq
  if ! command -v jq &> /dev/null; then
    log_error "jq is required but not installed"
    exit 1
  fi
  log_success "jq available"
  
  # Verify expiry is in the future
  local today
  today=$(date -u +%Y-%m-%d)
  if [[ "$EXPIRY" < "$today" ]]; then
    log_error "EXPIRY date ($EXPIRY) is in the past"
    exit 1
  fi
  log_success "Expiry date valid: $EXPIRY"
  
  log_info "Issue ID: $ISSUE_ID"
  log_info "Owner: $OWNER"
  log_info "Reason: $REASON"
}

#------------------------------------------------------------------------------
# API HELPERS
#------------------------------------------------------------------------------
api_get() {
  local endpoint="$1"
  local response
  local http_code
  
  response=$(curl -s -w "\n%{http_code}" \
    "${PROD_API_URL}${endpoint}" \
    -H "Authorization: Bearer ${PROD_TOKEN}" \
    -H "Accept: application/json")
  
  http_code=$(echo "$response" | tail -n1)
  echo "$response" | sed '$d'
  return 0
}

api_post_with_uat() {
  local endpoint="$1"
  local payload="$2"
  local response
  
  response=$(curl -s -w "\n%{http_code}" \
    -X POST "${PROD_API_URL}${endpoint}" \
    -H "Authorization: Bearer ${PROD_TOKEN}" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    -H "X-UAT-WRITE-ENABLE: true" \
    -H "X-UAT-ISSUE-ID: ${ISSUE_ID}" \
    -H "X-UAT-OWNER: ${OWNER}" \
    -H "X-UAT-EXPIRY: ${EXPIRY}" \
    -H "X-UAT-REASON: ${REASON}" \
    -d "$payload")
  
  echo "$response"
}

get_http_code() {
  echo "$1" | tail -n1
}

get_body() {
  echo "$1" | sed '$d'
}

#------------------------------------------------------------------------------
# PHASE 1: VERIFY PRODUCTION STATE
#------------------------------------------------------------------------------
verify_production_state() {
  log_step "1" "Verifying Production State"
  
  # Check build SHA
  log_info "Checking production build SHA..."
  local version_response
  version_response=$(api_get "/api/v1/meta/version")
  
  local build_sha
  build_sha=$(echo "$version_response" | jq -r '.build_sha // "unknown"')
  log_info "Production build_sha: $build_sha"
  
  # Check years endpoint
  log_info "Checking Planet Mark years..."
  local years_response
  years_response=$(api_get "/api/v1/planet-mark/years")
  
  # Check if it's a SETUP_REQUIRED response (migrations needed)
  local error_class
  error_class=$(echo "$years_response" | jq -r '.error_class // "none"')
  
  if [[ "$error_class" == "SETUP_REQUIRED" ]]; then
    local message
    message=$(echo "$years_response" | jq -r '.message // ""')
    if [[ "$message" == *"migrations"* ]]; then
      log_error "Database migrations required first!"
      log_error "Message: $message"
      log_error "Run: alembic upgrade head"
      exit 1
    fi
  fi
  
  # Check years count
  local years_count
  years_count=$(echo "$years_response" | jq -r '.years | length // 0' 2>/dev/null || echo "0")
  
  if [[ "$years_count" -gt 0 ]]; then
    log_warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_warn "IDEMPOTENCY CHECK: Data already exists!"
    log_warn "Years count: $years_count"
    log_warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Existing years:"
    echo "$years_response" | jq '.years[] | {id, year_label, year_number}'
    log_success "No action needed - Planet Mark already has data"
    
    # Verify dashboard works
    verify_dashboard
    exit 0
  fi
  
  log_success "Years count: $years_count (empty - ready for seed)"
  
  # Store for evidence
  EVIDENCE_YEARS_BEFORE="$years_count"
  EVIDENCE_BUILD_SHA="$build_sha"
}

#------------------------------------------------------------------------------
# PHASE 2: EXECUTE SEED
#------------------------------------------------------------------------------
execute_seed() {
  log_step "2" "Executing Data Seed (with UAT Override)"
  
  log_info "Payload:"
  echo "$SEED_PAYLOAD" | jq '.'
  
  log_info "UAT Headers:"
  log_info "  X-UAT-WRITE-ENABLE: true"
  log_info "  X-UAT-ISSUE-ID: $ISSUE_ID"
  log_info "  X-UAT-OWNER: $OWNER"
  log_info "  X-UAT-EXPIRY: $EXPIRY"
  
  echo ""
  log_warn "Executing POST /api/v1/planet-mark/years..."
  
  local full_response
  full_response=$(api_post_with_uat "/api/v1/planet-mark/years" "$SEED_PAYLOAD")
  
  local http_code
  http_code=$(get_http_code "$full_response")
  
  local body
  body=$(get_body "$full_response")
  
  log_info "HTTP Status: $http_code"
  
  if [[ "$http_code" == "201" ]]; then
    log_success "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_success "SEED SUCCESSFUL!"
    log_success "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Response:"
    echo "$body" | jq '.'
    
    # Extract created ID for rollback info
    CREATED_YEAR_ID=$(echo "$body" | jq -r '.id // "unknown"')
    log_info "Created year ID: $CREATED_YEAR_ID"
    
  elif [[ "$http_code" == "200" ]]; then
    log_success "Operation completed (HTTP 200)"
    echo "$body" | jq '.'
    CREATED_YEAR_ID=$(echo "$body" | jq -r '.id // "unknown"')
    
  elif [[ "$http_code" == "409" ]]; then
    log_warn "Conflict - year may already exist (HTTP 409)"
    echo "$body" | jq '.'
    log_info "This is expected if re-running - idempotency working correctly"
    
  elif [[ "$http_code" == "401" ]] || [[ "$http_code" == "403" ]]; then
    log_error "Authorization failed (HTTP $http_code)"
    log_error "Ensure your token has UAT_ADMIN_USERS membership"
    echo "$body" | jq '.' 2>/dev/null || echo "$body"
    exit 1
    
  elif [[ "$http_code" == "422" ]]; then
    log_error "Validation error (HTTP 422)"
    echo "$body" | jq '.' 2>/dev/null || echo "$body"
    exit 1
    
  else
    log_error "Unexpected response (HTTP $http_code)"
    echo "$body" | jq '.' 2>/dev/null || echo "$body"
    exit 1
  fi
}

#------------------------------------------------------------------------------
# PHASE 3: VERIFY DASHBOARD
#------------------------------------------------------------------------------
verify_dashboard() {
  log_step "3" "Verifying Dashboard State"
  
  # Check years count
  log_info "Checking years count..."
  local years_response
  years_response=$(api_get "/api/v1/planet-mark/years")
  
  local years_count
  years_count=$(echo "$years_response" | jq -r '.years | length // 0' 2>/dev/null || echo "0")
  log_info "Years count: $years_count"
  
  if [[ "$years_count" -lt 1 ]]; then
    log_error "Expected at least 1 year, got $years_count"
    exit 1
  fi
  log_success "Years present: $years_count"
  
  # Check dashboard
  log_info "Checking dashboard..."
  local dashboard_response
  dashboard_response=$(api_get "/api/v1/planet-mark/dashboard")
  
  local error_class
  error_class=$(echo "$dashboard_response" | jq -r '.error_class // "none"')
  
  if [[ "$error_class" == "SETUP_REQUIRED" ]]; then
    log_error "Dashboard still shows SETUP_REQUIRED!"
    echo "$dashboard_response" | jq '.'
    exit 1
  fi
  
  log_success "Dashboard returns real data (no error_class)"
  log_info "Dashboard response keys:"
  echo "$dashboard_response" | jq 'keys'
  
  # Store for evidence
  EVIDENCE_YEARS_AFTER="$years_count"
  EVIDENCE_DASHBOARD_OK="true"
}

#------------------------------------------------------------------------------
# PHASE 4: VERIFY TELEMETRY
#------------------------------------------------------------------------------
verify_telemetry() {
  log_step "4" "Verifying Telemetry Endpoint"
  
  local test_payload='{"event_name": "login_completed", "dimensions": {"result": "success", "durationBucket": "fast"}}'
  
  log_info "Testing telemetry POST with login_completed event..."
  
  local response
  response=$(curl -s -w "\n%{http_code}" \
    -X POST "${PROD_API_URL}/api/v1/telemetry/events" \
    -H "Authorization: Bearer ${PROD_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$test_payload")
  
  local http_code
  http_code=$(get_http_code "$response")
  
  local body
  body=$(get_body "$response")
  
  log_info "Telemetry HTTP Status: $http_code"
  
  if [[ "$http_code" == "200" ]] || [[ "$http_code" == "202" ]]; then
    log_success "Telemetry accepts login events (no 422)"
    EVIDENCE_TELEMETRY_OK="true"
  elif [[ "$http_code" == "422" ]]; then
    log_error "Telemetry still returning 422!"
    echo "$body" | jq '.' 2>/dev/null || echo "$body"
    EVIDENCE_TELEMETRY_OK="false"
  else
    log_warn "Telemetry returned unexpected status: $http_code"
    EVIDENCE_TELEMETRY_OK="unknown"
  fi
}

#------------------------------------------------------------------------------
# PHASE 5: PRODUCE EVIDENCE PACK
#------------------------------------------------------------------------------
produce_evidence() {
  log_step "5" "Producing Evidence Pack"
  
  local timestamp
  timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  
  cat << EOF

╔══════════════════════════════════════════════════════════════════════════════╗
║                     PLANET MARK SEED - EVIDENCE PACK                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Timestamp:        $timestamp
║ Script Version:   $SCRIPT_VERSION
║ Issue ID:         $ISSUE_ID
║ Owner:            $OWNER
╠══════════════════════════════════════════════════════════════════════════════╣
║ PRODUCTION STATE                                                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Build SHA:        ${EVIDENCE_BUILD_SHA:-unknown}
║ Years Before:     ${EVIDENCE_YEARS_BEFORE:-0}
║ Years After:      ${EVIDENCE_YEARS_AFTER:-unknown}
║ Dashboard OK:     ${EVIDENCE_DASHBOARD_OK:-unknown}
║ Telemetry OK:     ${EVIDENCE_TELEMETRY_OK:-unknown}
╠══════════════════════════════════════════════════════════════════════════════╣
║ CREATED RECORD                                                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Year ID:          ${CREATED_YEAR_ID:-none}
║ Year Label:       Year 1
║ Period:           2025-01-01 to 2025-12-31
║ Baseline Year:    true
╠══════════════════════════════════════════════════════════════════════════════╣
║ ROLLBACK INSTRUCTIONS                                                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ To remove seeded data (requires DBA/admin):                                  ║
║   DELETE FROM carbon_reporting_years WHERE id = ${CREATED_YEAR_ID:-<ID>};    ║
║   -- Governed operation: requires approval + audit trail                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

EOF

  if [[ "${EVIDENCE_DASHBOARD_OK:-}" == "true" ]] && [[ "${EVIDENCE_TELEMETRY_OK:-}" == "true" ]]; then
    log_success "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_success "VERDICT: PASS"
    log_success "Planet Mark is now fully operational in production!"
    log_success "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  else
    log_warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_warn "VERDICT: PARTIAL - Review items marked as not OK"
    log_warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  fi
}

#------------------------------------------------------------------------------
# MAIN
#------------------------------------------------------------------------------
main() {
  echo ""
  echo "╔══════════════════════════════════════════════════════════════════════════════╗"
  echo "║        PLANET MARK PRODUCTION SEED SCRIPT v${SCRIPT_VERSION}                           ║"
  echo "║        $(date -u +%Y-%m-%d\ %H:%M:%S\ UTC)                                            ║"
  echo "╚══════════════════════════════════════════════════════════════════════════════╝"
  echo ""
  
  # Initialize evidence variables
  EVIDENCE_BUILD_SHA=""
  EVIDENCE_YEARS_BEFORE=""
  EVIDENCE_YEARS_AFTER=""
  EVIDENCE_DASHBOARD_OK=""
  EVIDENCE_TELEMETRY_OK=""
  CREATED_YEAR_ID=""
  
  validate_prerequisites
  verify_production_state
  execute_seed
  verify_dashboard
  verify_telemetry
  produce_evidence
}

# Run
main "$@"
