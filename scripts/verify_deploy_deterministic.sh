#!/usr/bin/env bash
# verify_deploy_deterministic.sh - Deterministic deploy verification with stability gate
#
# Addresses: Azure App Service container swap latency causing false failures
# Pattern: Poll with exponential backoff + require N consecutive confirmations
#
# Usage:
#   ./scripts/verify_deploy_deterministic.sh \
#     --url https://app.azurewebsites.net \
#     --expected-sha abc123 \
#     --output /tmp/evidence.json
#
# Exit codes:
#   0 - Verification passed (SHA matches with stability confirmation)
#   1 - Verification failed (timeout or SHA mismatch after max attempts)
#   2 - Invalid arguments

set -euo pipefail

# Defaults
MAX_ATTEMPTS=30
INITIAL_INTERVAL=5
MAX_INTERVAL=30
TOTAL_TIMEOUT=600
STABILITY_REQUIRED=3  # Consecutive matching responses required
META_ENDPOINT="/api/v1/meta/version"
HEALTH_ENDPOINT="/healthz"

# Parse arguments
APP_URL=""
EXPECTED_SHA=""
OUTPUT_FILE=""
ENVIRONMENT="unknown"

while [[ $# -gt 0 ]]; do
  case $1 in
    --url) APP_URL="$2"; shift 2 ;;
    --expected-sha) EXPECTED_SHA="$2"; shift 2 ;;
    --output) OUTPUT_FILE="$2"; shift 2 ;;
    --environment) ENVIRONMENT="$2"; shift 2 ;;
    --max-attempts) MAX_ATTEMPTS="$2"; shift 2 ;;
    --timeout) TOTAL_TIMEOUT="$2"; shift 2 ;;
    --stability) STABILITY_REQUIRED="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 2 ;;
  esac
done

if [[ -z "$APP_URL" || -z "$EXPECTED_SHA" ]]; then
  echo "Usage: $0 --url <url> --expected-sha <sha> [--output <file>] [--environment <env>]"
  exit 2
fi

APP_URL="${APP_URL%/}"  # Remove trailing slash

# Helper function for HTTP requests
get_http() {
  local url="$1"
  local timeout="${2:-15}"
  local output_file="${3:-/dev/null}"
  local status
  status=$(curl -s -o "$output_file" -w "%{http_code}" --max-time "$timeout" "$url" 2>/dev/null || echo "000")
  echo "$status"
}

echo "============================================================"
echo "DETERMINISTIC DEPLOY VERIFICATION"
echo "============================================================"
echo "Target URL:        $APP_URL"
echo "Expected SHA:      $EXPECTED_SHA"
echo "Max Attempts:      $MAX_ATTEMPTS"
echo "Total Timeout:     ${TOTAL_TIMEOUT}s"
echo "Stability Gate:    $STABILITY_REQUIRED consecutive matches required"
echo "Timestamp:         $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================================"
echo ""

# Initialize tracking
START_TIME=$(date +%s)
ATTEMPT=0
INTERVAL=$INITIAL_INTERVAL
STABILITY_COUNT=0
LAST_SHA=""
VERIFICATION_RESULT="FAIL"
HEALTH_RESULT="UNKNOWN"
FINAL_SHA=""

# Phase 1: SHA Stability Verification
echo "### Phase 1: SHA Stability Verification"
echo "Waiting for build_sha to match expected with $STABILITY_REQUIRED consecutive confirmations..."
echo ""

while [[ $ATTEMPT -lt $MAX_ATTEMPTS ]]; do
  ATTEMPT=$((ATTEMPT + 1))
  ELAPSED=$(($(date +%s) - START_TIME))
  
  if [[ $ELAPSED -ge $TOTAL_TIMEOUT ]]; then
    echo "❌ TIMEOUT: Verification exceeded ${TOTAL_TIMEOUT}s limit"
    break
  fi
  
  META_STATUS=$(get_http "${APP_URL}${META_ENDPOINT}" 15 /tmp/meta_response.json)
  
  if [[ "$META_STATUS" == "200" ]]; then
    CURRENT_SHA=$(python3 -c 'import json; print(json.load(open("/tmp/meta_response.json")).get("build_sha",""))' 2>/dev/null || echo "")
    
    if [[ "$CURRENT_SHA" == "$EXPECTED_SHA" ]]; then
      STABILITY_COUNT=$((STABILITY_COUNT + 1))
      echo "[$(date -u +%H:%M:%S)] Attempt $ATTEMPT: ✓ SHA matches (stability: $STABILITY_COUNT/$STABILITY_REQUIRED)"
      
      if [[ $STABILITY_COUNT -ge $STABILITY_REQUIRED ]]; then
        echo ""
        echo "✅ STABILITY GATE PASSED: $STABILITY_COUNT consecutive matches"
        VERIFICATION_RESULT="PASS"
        FINAL_SHA="$CURRENT_SHA"
        break
      fi
    else
      # Reset stability counter on mismatch
      if [[ $STABILITY_COUNT -gt 0 ]]; then
        echo "[$(date -u +%H:%M:%S)] Attempt $ATTEMPT: ⚠ SHA changed to '$CURRENT_SHA' - resetting stability counter"
      else
        echo "[$(date -u +%H:%M:%S)] Attempt $ATTEMPT: ⏳ SHA='$CURRENT_SHA' != expected (elapsed: ${ELAPSED}s)"
      fi
      STABILITY_COUNT=0
    fi
    LAST_SHA="$CURRENT_SHA"
  elif [[ "$META_STATUS" == "000" ]]; then
    echo "[$(date -u +%H:%M:%S)] Attempt $ATTEMPT: ⏳ Connection timeout (elapsed: ${ELAPSED}s)"
    STABILITY_COUNT=0
  elif [[ "$META_STATUS" == "502" || "$META_STATUS" == "503" ]]; then
    echo "[$(date -u +%H:%M:%S)] Attempt $ATTEMPT: ⏳ Service restarting (HTTP $META_STATUS, elapsed: ${ELAPSED}s)"
    STABILITY_COUNT=0
  else
    echo "[$(date -u +%H:%M:%S)] Attempt $ATTEMPT: ⚠ HTTP $META_STATUS (elapsed: ${ELAPSED}s)"
    STABILITY_COUNT=0
  fi
  
  # Don't sleep after final attempt or if we've passed
  if [[ $ATTEMPT -lt $MAX_ATTEMPTS && "$VERIFICATION_RESULT" != "PASS" ]]; then
    sleep $INTERVAL
    # Exponential backoff with cap
    INTERVAL=$((INTERVAL * 2))
    if [[ $INTERVAL -gt $MAX_INTERVAL ]]; then
      INTERVAL=$MAX_INTERVAL
    fi
  fi
done

TOTAL_ELAPSED=$(($(date +%s) - START_TIME))

# Phase 2: Health Check (only if SHA verified)
echo ""
echo "### Phase 2: Health Check"
if [[ "$VERIFICATION_RESULT" == "PASS" ]]; then
  HEALTH_STATUS=$(get_http "${APP_URL}${HEALTH_ENDPOINT}" 10)
  if [[ "$HEALTH_STATUS" == "200" ]]; then
    echo "✅ Health check passed"
    HEALTH_RESULT="PASS"
  else
    echo "❌ Health check failed: HTTP $HEALTH_STATUS"
    HEALTH_RESULT="FAIL"
    VERIFICATION_RESULT="FAIL"
  fi
else
  echo "⏭️  Skipped (SHA verification failed)"
  HEALTH_RESULT="SKIPPED"
fi

# Generate evidence
echo ""
echo "### Evidence Summary"
echo "============================================================"
echo "Result:            $VERIFICATION_RESULT"
echo "Expected SHA:      $EXPECTED_SHA"
echo "Final SHA:         ${FINAL_SHA:-$LAST_SHA}"
echo "Stability Count:   $STABILITY_COUNT"
echo "Health Status:     $HEALTH_RESULT"
echo "Total Attempts:    $ATTEMPT"
echo "Total Time:        ${TOTAL_ELAPSED}s"
echo "============================================================"

# Write JSON evidence if output file specified
if [[ -n "$OUTPUT_FILE" ]]; then
  mkdir -p "$(dirname "$OUTPUT_FILE")"
  cat > "$OUTPUT_FILE" << EOF
{
  "verification_result": "$VERIFICATION_RESULT",
  "expected_sha": "$EXPECTED_SHA",
  "final_sha": "${FINAL_SHA:-$LAST_SHA}",
  "sha_match": $([ "$FINAL_SHA" == "$EXPECTED_SHA" ] && echo "true" || echo "false"),
  "stability_confirmations": $STABILITY_COUNT,
  "stability_required": $STABILITY_REQUIRED,
  "health_status": "$HEALTH_RESULT",
  "attempts": $ATTEMPT,
  "max_attempts": $MAX_ATTEMPTS,
  "elapsed_seconds": $TOTAL_ELAPSED,
  "timeout_seconds": $TOTAL_TIMEOUT,
  "environment": "$ENVIRONMENT",
  "app_url": "$APP_URL",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
  echo ""
  echo "📄 Evidence written to: $OUTPUT_FILE"
fi

# Exit with appropriate code
if [[ "$VERIFICATION_RESULT" == "PASS" && "$HEALTH_RESULT" == "PASS" ]]; then
  echo ""
  echo "🎉 VERIFICATION PASSED"
  exit 0
else
  echo ""
  echo "❌ VERIFICATION FAILED"
  if [[ -n "$LAST_SHA" && "$LAST_SHA" != "$EXPECTED_SHA" ]]; then
    echo "   Last observed SHA: $LAST_SHA"
    echo "   Expected SHA:      $EXPECTED_SHA"
  fi
  exit 1
fi
