#!/usr/bin/env bash
# Ensure the API App Service streams request, console, application and audit logs to Log
# Analytics, and say so loudly if it does not.
#
# Until 2026-07-26 neither app-qgp-prod nor qgp-staging-plantexpand had a diagnostic
# setting of any kind, so no request this platform served was recorded anywhere
# queryable. The setting was then applied by hand; this script is what stops it being
# lost again the next time the infrastructure is rebuilt.
#
# Usage:
#   API_WEBAPP_NAME=app-qgp-prod RESOURCE_GROUP=rg-qgp-staging \
#     bash scripts/infra/ensure_api_log_sink.sh
#
# Optional:
#   LOG_WORKSPACE_ID   full workspace resource ID, bypassing lookup
#   LOG_WORKSPACE_RG   resource group to find the workspace in (default: rg-qgp-prod)
#   VERIFY_ONLY=true   check and warn only; make no Azure write call
#
# Never fails the caller. A deploy that cannot write a diagnostic setting is still a
# deploy that shipped working code, and blocking it would be the wrong trade.
set -euo pipefail

API_WEBAPP_NAME="${API_WEBAPP_NAME:?Set API_WEBAPP_NAME to the API App Service name}"
RESOURCE_GROUP="${RESOURCE_GROUP:?Set RESOURCE_GROUP to the App Service resource group}"
VERIFY_ONLY="${VERIFY_ONLY:-false}"

# shellcheck source=scripts/infra/ensure_log_sink.sh
. "$(dirname "${BASH_SOURCE[0]}")/ensure_log_sink.sh"

WORKSPACE_RG="${LOG_WORKSPACE_RG:-$API_LOG_WORKSPACE_RG}"

echo "=== API Log Analytics sink ==="
echo "  app=$API_WEBAPP_NAME rg=$RESOURCE_GROUP workspace_rg=$WORKSPACE_RG verify_only=$VERIFY_ONLY"

if [ "$VERIFY_ONLY" != "true" ]; then
  log_sink_init "$WORKSPACE_RG"
  ensure_log_sink "$API_WEBAPP_NAME" "$RESOURCE_GROUP" "$API_LOG_SETTING_NAME" "$API_LOG_CATEGORIES"
fi

# Read back rather than trusting the write. When ensure_log_sink warned instead of
# succeeding — no permission, no workspace, a conflicting sink already pointed at the
# same destination — this is what turns that into a visible ::warning in the deploy, so
# a silent regression shows up on the run that caused it rather than months later when
# somebody needs the logs and finds nothing.
warn_if_no_log_sink "$API_WEBAPP_NAME" "$RESOURCE_GROUP" AppServiceHTTPLogs \
  "Requests to this API are not being recorded. Re-run scripts/infra/ensure_api_log_sink.sh with Monitoring Contributor on the site."
