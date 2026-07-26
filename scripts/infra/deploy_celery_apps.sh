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

# shellcheck source=scripts/infra/ensure_log_sink.sh
. "$(dirname "${BASH_SOURCE[0]}")/ensure_log_sink.sh"

REDIS_URL_VAL="${REDIS_URL:-${CELERY_BROKER_URL:-}}"
if [ -z "$REDIS_URL_VAL" ]; then
  echo "❌ REDIS_URL / CELERY_BROKER_URL required for Celery apps"
  exit 1
fi

# A non-production environment sharing production's broker is not a cosmetic problem: its
# worker competes for prod tasks, looks the job id up in its own database, finds nothing,
# and the prod row stays pending forever. Prod library documents were stuck in "processing"
# for exactly this reason while kv-qgp-staging's REDIS-URL pointed at redis-qgp-prod.
if [ "$APP_ENV" != "production" ] && printf '%s' "$REDIS_URL_VAL" | grep -q 'redis-qgp-prod'; then
  echo "❌ $APP_ENV Celery apps are pointed at the production Redis broker (redis-qgp-prod)."
  echo "   Point REDIS-URL in this environment's Key Vault at its own cache instead."
  exit 1
fi

# The worker downloads uploaded documents from Blob Storage to index them. Without these
# it accepts index jobs and then fails every one with StorageNotConfiguredError, leaving
# documents stuck in "processing" with no signal at deploy time. Fail the deploy instead.
STORAGE_CONN_VAL="${AZURE_STORAGE_CONNECTION_STRING:-}"
STORAGE_CONTAINER_VAL="${AZURE_STORAGE_CONTAINER_NAME:-evidence-assets}"
if [ -z "$STORAGE_CONN_VAL" ] && { [ "$APP_ENV" = "production" ] || [ "$APP_ENV" = "staging" ]; }; then
  echo "❌ AZURE_STORAGE_CONNECTION_STRING required for Celery apps in $APP_ENV"
  echo "   Library indexing cannot read uploaded files without it."
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
  if [ -n "$STORAGE_CONN_VAL" ]; then
    settings+=(
      AZURE_STORAGE_CONNECTION_STRING="$STORAGE_CONN_VAL"
      AZURE_STORAGE_CONTAINER_NAME="$STORAGE_CONTAINER_VAL"
    )
  fi
  # Optional SMTP — only wire when present (Key Vault / pipeline env). Never invent credentials.
  for key in EMAIL_ENABLED SMTP_HOST SMTP_PORT SMTP_USER SMTP_PASSWORD FROM_EMAIL FROM_NAME; do
    if [ -n "${!key:-}" ]; then
      settings+=("${key}=${!key}")
    fi
  done

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

  # The restart above is exactly when stdout capture to /home/LogFiles has been observed to
  # die and stay dead, so warn if this app has no diagnostic setting to fall back on. Only
  # a warning: an unobservable worker is still a working worker, and provisioning owns the
  # fix (provision-celery-workers.sh). Read-only, so it cannot fail the deploy.
  warn_if_no_log_sink "$name" "$RESOURCE_GROUP" AppServiceConsoleLogs \
    "Its Celery output may be unreadable after this restart. Re-run scripts/infra/provision-celery-workers.sh."
}

deploy_one "$WORKER_WEBAPP_NAME" worker "bash scripts/celery/start_worker.sh"
deploy_one "$BEAT_WEBAPP_NAME" beat "bash scripts/celery/start_beat.sh"
