#!/usr/bin/env bash
# Wire SMTP into QGP Key Vault + App Settings.
# NEVER invent secrets — export real values before running.
#
# Usage (staging):
#   export SMTP_USER='noreply@plantexpand.com'
#   export SMTP_PASSWORD='...'          # app password / mailbox secret
#   export FROM_EMAIL='noreply@plantexpand.com'
#   export FROM_NAME='QGP Notifications'   # optional
#   ./scripts/ops/wire_smtp.sh staging
#
# Usage (prod):
#   ./scripts/ops/wire_smtp.sh prod
#
# Success checks (after restart settles):
#   curl -sS "$BASE/readyz" | jq '{email_configured,email}'
#   python scripts/smoke/check_email_config.py --from-readyz /tmp/readyz.json
set -euo pipefail

ENV="${1:-}"
if [[ "$ENV" != "staging" && "$ENV" != "prod" ]]; then
  echo "usage: $0 staging|prod" >&2
  exit 2
fi

: "${SMTP_USER:?export SMTP_USER}"
: "${SMTP_PASSWORD:?export SMTP_PASSWORD}"
: "${FROM_EMAIL:?export FROM_EMAIL}"

SMTP_HOST="${SMTP_HOST:-smtp.office365.com}"
SMTP_PORT="${SMTP_PORT:-587}"
FROM_NAME="${FROM_NAME:-QGP Notifications}"
EMAIL_ENABLED="${EMAIL_ENABLED:-true}"

if [[ "$ENV" == "staging" ]]; then
  VAULT="kv-qgp-staging"
  RG="rg-qgp-staging"
  APPS=(qgp-staging-plantexpand qgp-staging-plantexpand-worker)
  BASE_URL="https://qgp-staging-plantexpand.azurewebsites.net"
else
  VAULT="kv-qgp-prod"
  # Prod API/worker currently live in rg-qgp-staging (verified 2026-07-12)
  RG="rg-qgp-staging"
  APPS=(app-qgp-prod app-qgp-prod-worker)
  BASE_URL="https://app-qgp-prod.azurewebsites.net"
fi

echo "==> Writing SMTP secrets to Key Vault $VAULT"
# Strip whitespace/newlines — trailing \\n from CLI paste causes Outlook 535 AUTH failures.
az keyvault secret set --vault-name "$VAULT" --name SMTP-USER --value "${SMTP_USER//$'\r'/}" >/dev/null
az keyvault secret set --vault-name "$VAULT" --name SMTP-PASSWORD --value "$(printf '%s' "$SMTP_PASSWORD" | tr -d '\r\n')" >/dev/null
az keyvault secret set --vault-name "$VAULT" --name FROM-EMAIL --value "${FROM_EMAIL//$'\r'/}" >/dev/null
az keyvault secret set --vault-name "$VAULT" --name FROM-NAME --value "${FROM_NAME//$'\r'/}" >/dev/null

SMTP_USER_URI=$(az keyvault secret show --vault-name "$VAULT" --name SMTP-USER --query id -o tsv)
SMTP_PASS_URI=$(az keyvault secret show --vault-name "$VAULT" --name SMTP-PASSWORD --query id -o tsv)
FROM_EMAIL_URI=$(az keyvault secret show --vault-name "$VAULT" --name FROM-EMAIL --query id -o tsv)
FROM_NAME_URI=$(az keyvault secret show --vault-name "$VAULT" --name FROM-NAME --query id -o tsv)

kv_ref() {
  # App Service Key Vault reference — VERSIONLESS (drop /<version> suffix)
  local id="$1"
  local no_trailing="${id%/}"
  local base="${no_trailing%/*}"   # .../secrets/NAME
  echo "@Microsoft.KeyVault(SecretUri=${base}/)"
}

SETTINGS=(
  "EMAIL_ENABLED=${EMAIL_ENABLED}"
  "SMTP_HOST=${SMTP_HOST}"
  "SMTP_PORT=${SMTP_PORT}"
  "SMTP_USER=$(kv_ref "$SMTP_USER_URI")"
  "SMTP_PASSWORD=$(kv_ref "$SMTP_PASS_URI")"
  "FROM_EMAIL=$(kv_ref "$FROM_EMAIL_URI")"
  "FROM_NAME=$(kv_ref "$FROM_NAME_URI")"
)

for APP in "${APPS[@]}"; do
  echo "==> Applying App Settings on $APP ($RG)"
  az webapp config appsettings set --name "$APP" --resource-group "$RG" --settings "${SETTINGS[@]}" >/dev/null
  echo "==> Restarting $APP"
  az webapp restart --name "$APP" --resource-group "$RG" >/dev/null || true
done

echo "==> Waiting 45s for restart..."
sleep 45

READYZ=$(curl -sS --max-time 30 "$BASE_URL/readyz" || true)
printf '%s' "$READYZ" | python3 -c '
import sys, json
raw = sys.stdin.read().strip()
if not raw:
    print("readyz: EMPTY/FAILED")
    raise SystemExit(1)
d = json.loads(raw)
email = d.get("email") or {}
print("email_configured=", d.get("email_configured"))
print("email.status=", email.get("status"))
print("overall.status=", d.get("status"))
'

echo
echo "Next: prove enqueue SUCCESS (workflow notification or Celery send_email)."
echo "Smoke: curl -sS $BASE_URL/readyz > /tmp/readyz.json && python scripts/smoke/check_email_config.py --from-readyz /tmp/readyz.json"
echo "DONE wire $ENV"
