#!/usr/bin/env bash
# Deploy/update Celery worker + beat App Service containers (same image as API).
# Safe no-op when sites are not provisioned yet (exit 0 with warning).
#
# Required env:
#   RESOURCE_GROUP, API_WEBAPP_NAME, IMAGE_DIGEST_REF
#   REDIS_URL (or CELERY_BROKER_URL)
# Optional:
#   WORKER_WEBAPP_NAME (default: ${API_WEBAPP_NAME}-worker)
#   BEAT_WEBAPP_NAME (default: ${API_WEBAPP_NAME}-beat)
#   APP_ENV, BUILD_SHA, DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY, ...
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:?}"
API_WEBAPP_NAME="${API_WEBAPP_NAME:?}"
IMAGE_DIGEST_REF="${IMAGE_DIGEST_REF:?}"
WORKER_WEBAPP_NAME="${WORKER_WEBAPP_NAME:-${API_WEBAPP_NAME}-worker}"
BEAT_WEBAPP_NAME="${BEAT_WEBAPP_NAME:-${API_WEBAPP_NAME}-beat}"
APP_ENV="${APP_ENV:-staging}"
BUILD_SHA="${BUILD_SHA:-unknown}"

REDIS_URL_VAL="${REDIS_URL:-${CELERY_BROKER_URL:-}}"
if [ -z "$REDIS_URL_VAL" ]; then
  echo "❌ REDIS_URL / CELERY_BROKER_URL required for Celery apps"
  exit 1
fi

deploy_one() {
  local name="$1"
  local role="$2"
  local startup="$3"

  if ! az webapp show --name "$name" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
    echo "⚠️  $name not found in $RESOURCE_GROUP — skip ($role)."
    echo "   Provision with: API_WEBAPP=$API_WEBAPP_NAME RG=$RESOURCE_GROUP ./scripts/infra/provision-celery-workers.sh"
    return 0
  fi

  echo "🚀 Deploying Celery $role → $name"
  az webapp config container set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$name" \
    --container-image-name "$IMAGE_DIGEST_REF" \
    --output none

  # Minimal settings — reuse Redis + identity secrets already required by API.
  local settings=(
    APP_ENV="$APP_ENV"
    BUILD_SHA="$BUILD_SHA"
    BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    WEBSITES_PORT="8000"
    CELERY_ROLE="$role"
    CELERY_BROKER_URL="$REDIS_URL_VAL"
    CELERY_RESULT_BACKEND="$REDIS_URL_VAL"
    REDIS_URL="$REDIS_URL_VAL"
  )
  if [ -n "${DATABASE_URL:-}" ]; then
    settings+=(DATABASE_URL="$DATABASE_URL")
  fi
  if [ -n "${SECRET_KEY:-}" ]; then
    settings+=(SECRET_KEY="$SECRET_KEY")
  fi
  if [ -n "${JWT_SECRET_KEY:-}" ]; then
    settings+=(JWT_SECRET_KEY="$JWT_SECRET_KEY")
  fi

  az webapp config appsettings set \
    --name "$name" \
    --resource-group "$RESOURCE_GROUP" \
    --settings "${settings[@]}" \
    --output none

  az webapp config set \
    --name "$name" \
    --resource-group "$RESOURCE_GROUP" \
    --startup-file "$startup" \
    --always-on true \
    --generic-configurations '{"healthCheckPath":"/healthz"}' \
    --output none

  az webapp restart --name "$name" --resource-group "$RESOURCE_GROUP" --output none
  echo "✅ Celery $role updated"
}

deploy_one "$WORKER_WEBAPP_NAME" worker "bash scripts/celery/start_worker.sh"
deploy_one "$BEAT_WEBAPP_NAME" beat "bash scripts/celery/start_beat.sh"
