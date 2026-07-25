#!/usr/bin/env bash
# Provision Celery worker + beat App Service sites sharing the API plan.
# Usage:
#   ENV=staging API_WEBAPP=app-qgp-staging RG=rg-qgp-staging ./scripts/infra/provision-celery-workers.sh
#   ENV=production API_WEBAPP=app-qgp-prod RG=rg-qgp-staging ./scripts/infra/provision-celery-workers.sh
set -euo pipefail

ENV_NAME="${ENV:-staging}"
API_WEBAPP="${API_WEBAPP:?Set API_WEBAPP to the existing API App Service name}"
RG="${RG:?Set RG to the resource group}"
LOCATION="${LOCATION:-uksouth}"
WORKER_NAME="${WORKER_NAME:-${API_WEBAPP}-worker}"
BEAT_NAME="${BEAT_NAME:-${API_WEBAPP}-beat}"

echo "=== Provision Celery worker/beat ==="
echo "  env=$ENV_NAME api=$API_WEBAPP rg=$RG"
echo "  worker=$WORKER_NAME beat=$BEAT_NAME"

PLAN_ID=$(az webapp show --name "$API_WEBAPP" --resource-group "$RG" --query appServicePlanId -o tsv)
echo "  plan=$PLAN_ID"

create_site() {
  local name="$1"
  local role="$2"
  if az webapp show --name "$name" --resource-group "$RG" &>/dev/null; then
    echo "✓ $name already exists"
    return 0
  fi
  echo "→ Creating $name ($role)..."
  az webapp create \
    --name "$name" \
    --resource-group "$RG" \
    --plan "$PLAN_ID" \
    --deployment-container-image-name "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest" \
    --output none
  az webapp config set \
    --name "$name" \
    --resource-group "$RG" \
    --always-on true \
    --generic-configurations '{"healthCheckPath":"/healthz"}' \
    --output none
  az webapp update --name "$name" --resource-group "$RG" --https-only true --output none
  echo "✓ created $name"
}

create_site "$WORKER_NAME" worker
create_site "$BEAT_NAME" beat

# Worker and beat pull the API's image with acrUseManagedIdentityCreds, so they need a
# system-assigned identity holding AcrPull. A site missing either keeps running on its
# cached container and only fails the next time it restarts, which makes this very easy
# to miss: prod beat was in exactly that state.
ACR_HOST=$(az webapp config appsettings list --name "$API_WEBAPP" --resource-group "$RG" \
  --query "[?name=='DOCKER_REGISTRY_SERVER_URL'].value | [0]" -o tsv 2>/dev/null || true)
ACR_HOST="${ACR_HOST#https://}"
ACR_REGISTRY="${ACR_NAME:-${ACR_HOST%%.azurecr.io}}"

grant_acr_pull() {
  local name="$1"
  local principal
  principal=$(az webapp identity assign --name "$name" --resource-group "$RG" --query principalId -o tsv)
  echo "  $name identity: $principal"

  if [ -z "$ACR_REGISTRY" ]; then
    echo "  ⚠️  Could not resolve the registry from $API_WEBAPP and ACR_NAME is unset —"
    echo "     grant AcrPull manually or $name will fail to pull on its next restart."
    return 0
  fi

  local acr_id
  acr_id=$(az acr show --name "$ACR_REGISTRY" --query id -o tsv)
  if az role assignment create \
      --assignee-object-id "$principal" \
      --assignee-principal-type ServicePrincipal \
      --role AcrPull \
      --scope "$acr_id" \
      --output none 2>/dev/null; then
    echo "  ✓ AcrPull granted on $ACR_REGISTRY"
  else
    echo "  ✓ AcrPull already present on $ACR_REGISTRY"
  fi

  az webapp config set --name "$name" --resource-group "$RG" \
    --generic-configurations '{"acrUseManagedIdentityCreds": true}' --output none
}

echo ""
echo "=== Managed identity + AcrPull ==="
grant_acr_pull "$WORKER_NAME"
grant_acr_pull "$BEAT_NAME"

# Worker and beat have no HTTP surface, so their container stdout is the only account of
# what they did. /home/LogFiles capture cannot be relied on for that: the prod worker's
# containerStream.log stopped mid-day and never resumed across ~44 restarts, leaving the
# app with no record at all while it was in fact running tasks normally. A diagnostic
# setting streams the same stdout to Log Analytics instead, which survives restarts and
# redeploys and is queryable (AppServiceConsoleLogs). Platform logs come along because
# container pull/start failures are invisible in stdout by definition.
ensure_log_sink() {
  local name="$1"
  local site_id="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG/providers/Microsoft.Web/sites/$name"

  if [ -z "$WORKSPACE_ID" ]; then
    echo "  ⚠️  No Log Analytics workspace found in $LOG_WORKSPACE_RG and LOG_WORKSPACE_ID is unset —"
    echo "     $name will have no durable log sink. Set LOG_WORKSPACE_ID and re-run."
    return 0
  fi

  if az monitor diagnostic-settings create \
      --name celery-logs \
      --resource "$site_id" \
      --workspace "$WORKSPACE_ID" \
      --logs '[{"category":"AppServiceConsoleLogs","enabled":true},{"category":"AppServicePlatformLogs","enabled":true}]' \
      --output none 2>/dev/null; then
    echo "  ✓ $name streams console + platform logs to ${WORKSPACE_ID##*/}"
  else
    echo "  ⚠️  Could not set the diagnostic setting on $name — grant Monitoring Contributor"
    echo "     on the site and read on the workspace, then re-run."
  fi
}

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
# Production's App Service resources live in rg-qgp-staging, so the workspace is not
# necessarily in the same group as the sites: prefer the environment's own workspace.
LOG_WORKSPACE_RG="${LOG_WORKSPACE_RG:-$([ "$ENV_NAME" = "production" ] && echo rg-qgp-prod || echo "$RG")}"
WORKSPACE_ID="${LOG_WORKSPACE_ID:-$(az monitor log-analytics workspace list \
  --resource-group "$LOG_WORKSPACE_RG" --query "[0].id" -o tsv 2>/dev/null || true)}"

echo ""
echo "=== Log Analytics sink ==="
ensure_log_sink "$WORKER_NAME"
ensure_log_sink "$BEAT_NAME"

echo ""
echo "Next: merge feat/wcs-celery-worker-beat-deploy and let deploy-staging/production"
echo "update container image + startup-file for worker/beat, then run:"
echo "  CELERY_BROKER_URL=\$REDIS_URL python scripts/celery/smoke_inspect_ping.py"
