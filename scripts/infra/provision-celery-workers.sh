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

echo ""
echo "Next: merge feat/wcs-celery-worker-beat-deploy and let deploy-staging/production"
echo "update container image + startup-file for worker/beat, then run:"
echo "  CELERY_BROKER_URL=\$REDIS_URL python scripts/celery/smoke_inspect_ping.py"
