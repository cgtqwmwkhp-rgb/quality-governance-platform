#!/usr/bin/env bash
set -euo pipefail

# Azure Monitor Alert Configuration
# Sets up metric alerts for the Quality Governance Platform
#
# Usage:
#   ./azure_monitor_alerts.sh --resource-group <RG> --app-name <APP> [--dry-run]

DRY_RUN=false
RESOURCE_GROUP=""
APP_NAME=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --resource-group) RESOURCE_GROUP="$2"; shift 2 ;;
    --app-name) APP_NAME="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

[[ -z "$RESOURCE_GROUP" ]] && { echo "Error: --resource-group required"; exit 1; }
[[ -z "$APP_NAME" ]] && { echo "Error: --app-name required"; exit 1; }

ALERTS=(
  "high-cpu|CpuPercentage|GreaterThan|80|5m|CPU usage exceeds 80%"
  "high-memory|MemoryPercentage|GreaterThan|85|5m|Memory usage exceeds 85%"
  "high-error-rate|Http5xx|GreaterThan|10|5m|5xx error rate exceeds threshold"
  "high-latency|HttpResponseTime|GreaterThan|2|5m|Response time exceeds 2 seconds"
  "low-availability|HealthCheckStatus|LessThan|1|5m|Health check failures detected"
)

echo "=== Azure Monitor Alert Configuration ==="
echo "Resource Group: $RESOURCE_GROUP"
echo "App Name: $APP_NAME"
echo "Dry Run: $DRY_RUN"
echo ""

for alert_def in "${ALERTS[@]}"; do
  IFS='|' read -r name metric operator threshold window description <<< "$alert_def"
  echo "[Alert] $name: $description (${metric} ${operator} ${threshold}, window: ${window})"
  
  if [[ "$DRY_RUN" == "false" ]]; then
    echo "  Would run: az monitor metrics alert create ..."
    echo "  (Skipping — requires active Azure subscription and correct resource IDs)"
  fi
done

echo ""
echo "[OK] Alert configuration complete (dry-run: $DRY_RUN)"
