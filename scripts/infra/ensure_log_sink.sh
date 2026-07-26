#!/usr/bin/env bash
# shellcheck disable=SC2034  # the category/name constants below are for sourcing callers
# Shared Log Analytics diagnostic-setting helper for the qgp App Services.
#
# A diagnostic setting is a resource-level Azure setting, not application config, so it
# survives restarts and redeploys — but it also lives nowhere in the repo unless something
# like this puts it there. #1290 added this for the Celery worker and beat after the prod
# worker went silent for a day; the two API apps had no diagnostic setting of any kind
# until 2026-07-26, so nothing recorded which requests the platform served.
#
# Source it and call the functions:
#   . scripts/infra/ensure_log_sink.sh
#   log_sink_init "$API_LOG_WORKSPACE_RG"
#   ensure_log_sink app-qgp-prod rg-qgp-staging "$API_LOG_SETTING_NAME" "$API_LOG_CATEGORIES"
#
# Or run it directly for a single app:
#   bash scripts/infra/ensure_log_sink.sh <site> <site_rg> <setting_name> <categories> <workspace_rg>
#
# Everything here warns rather than fails. An unobservable app is still a working app, and
# neither provisioning nor a deploy should be blocked because the service principal is
# missing Monitoring Contributor.

# The two category sets are deliberately different and must stay that way.
#
# Worker and beat have no HTTP surface, so AppServiceHTTPLogs on them would record nothing
# but the platform's own AlwaysOn pings. What they need is platform logs, because a failed
# container pull is invisible in stdout by definition — that is the class of failure that
# hid prod beat's missing AcrPull.
#
# The API apps are the opposite. AppServiceHTTPLogs is the whole point for them: it is the
# only record of which request hit which endpoint, and so the only basis for an audit
# trail of what the platform was asked to do with personal data. AppServiceAuditLogs
# covers access to the management surfaces (SCM/FTP), which HTTP logs do not see.
#
# NOTE (data protection): AppServiceHTTPLogs records the raw query string in CsUriQuery.
# Before adding an app here, check what its endpoints accept as query parameters — see
# docs/runbooks/API_LOG_SINK.md, which lists the query parameters on this API that carry
# a credential or personal data.
CELERY_LOG_CATEGORIES='[{"category":"AppServiceConsoleLogs","enabled":true},{"category":"AppServicePlatformLogs","enabled":true}]'
API_LOG_CATEGORIES='[{"category":"AppServiceHTTPLogs","enabled":true},{"category":"AppServiceConsoleLogs","enabled":true},{"category":"AppServiceAppLogs","enabled":true},{"category":"AppServiceAuditLogs","enabled":true}]'

# Setting names are per-role so the API and Celery settings can be reasoned about, and
# rolled back, separately.
CELERY_LOG_SETTING_NAME="celery-logs"
API_LOG_SETTING_NAME="qgp-api-logs"

# Which workspace an app streams to is not derivable from where the app lives: production
# App Service resources sit in rg-qgp-staging, and the API apps in *both* environments
# currently stream to the production workspace while the Celery apps split per
# environment. Callers therefore state the workspace group rather than have it inferred.
API_LOG_WORKSPACE_RG="rg-qgp-prod"

# Set by log_sink_init. Resolving these is two network calls, so it is done once per run
# rather than per app — and deliberately not inside a command substitution, which would
# discard the assignment into a subshell.
LOG_SINK_SUBSCRIPTION_ID=""
LOG_SINK_WORKSPACE_ID=""

# log_sink_init_subscription
#
# Enough on its own for the read-only checks, which need no workspace.
log_sink_init_subscription() {
  if [ -z "$LOG_SINK_SUBSCRIPTION_ID" ]; then
    LOG_SINK_SUBSCRIPTION_ID=$(az account show --query id -o tsv 2>/dev/null || true)
  fi
}

# log_sink_init <workspace_resource_group>
#
# LOG_WORKSPACE_ID overrides the lookup entirely, which is how a new environment or a
# one-off redirect is handled without editing this file.
log_sink_init() {
  local workspace_rg="$1"

  log_sink_init_subscription

  if [ -n "${LOG_WORKSPACE_ID:-}" ]; then
    LOG_SINK_WORKSPACE_ID="$LOG_WORKSPACE_ID"
    return 0
  fi

  LOG_SINK_WORKSPACE_ID=$(az monitor log-analytics workspace list \
    --resource-group "$workspace_rg" --query "[0].id" -o tsv 2>/dev/null || true)

  if [ -z "$LOG_SINK_WORKSPACE_ID" ]; then
    echo "  ⚠️  No Log Analytics workspace found in $workspace_rg and LOG_WORKSPACE_ID is unset."
  fi
}

# ensure_log_sink <site_name> <site_rg> <setting_name> <categories_json>
#
# Call log_sink_init first. Idempotent: `az monitor diagnostic-settings create` is a PUT
# against Microsoft.Insights/diagnosticSettings/<setting_name>, so re-running it with the
# same name, workspace and categories re-sends an identical body and the setting comes
# back unchanged. Running this twice, or against an app already configured by hand, is a
# no-op rather than an error.
ensure_log_sink() {
  local name="$1"
  local site_rg="$2"
  local setting_name="$3"
  local categories="$4"
  local site_id

  if [ -z "$LOG_SINK_SUBSCRIPTION_ID" ]; then
    echo "  ⚠️  Not logged in to Azure — cannot set '$setting_name' on $name."
    return 0
  fi

  if [ -z "$LOG_SINK_WORKSPACE_ID" ]; then
    echo "  ⚠️  No workspace resolved — $name will have no durable log sink."
    echo "     Set LOG_WORKSPACE_ID and re-run."
    return 0
  fi

  site_id="/subscriptions/${LOG_SINK_SUBSCRIPTION_ID}/resourceGroups/${site_rg}/providers/Microsoft.Web/sites/${name}"

  if az monitor diagnostic-settings create \
      --name "$setting_name" \
      --resource "$site_id" \
      --workspace "$LOG_SINK_WORKSPACE_ID" \
      --logs "$categories" \
      --output none 2>/dev/null; then
    echo "  ✓ $name streams '$setting_name' to ${LOG_SINK_WORKSPACE_ID##*/}"
  else
    # Also reached when a differently-named setting on this resource already targets the
    # same workspace — Azure rejects a second sink pointed at one destination.
    echo "  ⚠️  Could not set '$setting_name' on $name — grant Monitoring Contributor on the"
    echo "     site and read on the workspace, then re-run. Check for a conflicting setting:"
    echo "     az monitor diagnostic-settings list --resource $site_id"
  fi
}

# log_sink_setting_for_category <site_name> <site_rg> <category>
#
# Prints the name of a diagnostic setting on the site that has <category> enabled, or
# nothing. Read-only, so it is safe from a deploy and needs no write permission.
log_sink_setting_for_category() {
  local name="$1"
  local site_rg="$2"
  local category="$3"
  local site_id

  [ -n "$LOG_SINK_SUBSCRIPTION_ID" ] || return 0

  site_id="/subscriptions/${LOG_SINK_SUBSCRIPTION_ID}/resourceGroups/${site_rg}/providers/Microsoft.Web/sites/${name}"

  # The `to_string(...)` wrapper matters: an earlier version of this query in
  # deploy_celery_apps.sh compared against a `value[]` shape the CLI does not return and
  # reported NONE for every app, which is exactly the false negative this check exists
  # to catch.
  az monitor diagnostic-settings list \
    --resource "$site_id" \
    --query "[?contains(to_string(logs[?enabled].category), '${category}')] | [0].name" \
    -o tsv 2>/dev/null || true
}

# warn_if_no_log_sink <site_name> <site_rg> <category> <remediation>
#
# Emits a GitHub Actions warning when the category is not being collected. Always returns
# 0 — a missing log sink must never fail a deploy.
warn_if_no_log_sink() {
  local name="$1"
  local site_rg="$2"
  local category="$3"
  local remediation="$4"
  local found

  # Resolve outside the substitution below, which would otherwise throw the cached value
  # away in a subshell and re-query Azure on every call.
  log_sink_init_subscription
  found=$(log_sink_setting_for_category "$name" "$site_rg" "$category")

  if [ -n "$found" ]; then
    echo "  ✓ $name collects $category via '$found'"
    return 0
  fi

  echo "::warning title=Missing $category on $name::No diagnostic setting on $name collects ${category}. ${remediation}"
  echo "  ⚠️  $name has no $category diagnostic setting — what it serves is not recorded"
  echo "     anywhere queryable. $remediation"
}

# Direct invocation: ensure_log_sink.sh <site> <site_rg> <setting_name> <categories> <workspace_rg>
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  set -euo pipefail
  if [ "$#" -ne 5 ]; then
    echo "usage: $0 <site_name> <site_rg> <setting_name> <categories_json> <workspace_rg>" >&2
    exit 2
  fi
  log_sink_init "$5"
  ensure_log_sink "$1" "$2" "$3" "$4"
fi
