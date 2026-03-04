#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Set PSEUDONYMIZATION_PEPPER in Azure Key Vaults (staging + production)
# Run this script from YOUR OWN TERMINAL (not Cursor) with az CLI authenticated.
#
# Prerequisites:
#   az login
#   az account show  (verify correct subscription)
# ============================================================================

PEPPER=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
echo "Generated PSEUDONYMIZATION_PEPPER (${#PEPPER} chars)"

echo ""
echo "=== Step 1/4: Setting pepper in STAGING Key Vault ==="
az keyvault secret set \
  --vault-name kv-qgp-staging \
  --name PSEUDONYMIZATION-PEPPER \
  --value "$PEPPER" \
  --output none \
  && echo "  OK: kv-qgp-staging/PSEUDONYMIZATION-PEPPER set" \
  || echo "  FAILED: Could not set secret in kv-qgp-staging"

echo ""
echo "=== Step 2/4: Setting pepper in PRODUCTION Key Vault ==="
az keyvault secret set \
  --vault-name kv-qgp-prod \
  --name PSEUDONYMIZATION-PEPPER \
  --value "$PEPPER" \
  --output none \
  && echo "  OK: kv-qgp-prod/PSEUDONYMIZATION-PEPPER set" \
  || echo "  FAILED: Could not set secret in kv-qgp-prod"

echo ""
echo "=== Step 3/4: Verifying secrets exist ==="
STAGING_EXISTS=$(az keyvault secret show --vault-name kv-qgp-staging --name PSEUDONYMIZATION-PEPPER --query "name" -o tsv 2>/dev/null || echo "MISSING")
PROD_EXISTS=$(az keyvault secret show --vault-name kv-qgp-prod --name PSEUDONYMIZATION-PEPPER --query "name" -o tsv 2>/dev/null || echo "MISSING")
echo "  Staging:    $STAGING_EXISTS"
echo "  Production: $PROD_EXISTS"

if [[ "$STAGING_EXISTS" == "MISSING" || "$PROD_EXISTS" == "MISSING" ]]; then
  echo ""
  echo "ERROR: One or both secrets failed to set. Check Key Vault access policies."
  exit 1
fi

echo ""
echo "=== Step 4/4: Summary ==="
echo "  Both Key Vaults now have PSEUDONYMIZATION-PEPPER."
echo "  The deploy workflows will read this secret and inject it as an app setting."
echo "  Next: push the workflow changes to trigger a new deployment."
echo ""
echo "  IMPORTANT: The same pepper value is used for BOTH environments."
echo "  If you need different peppers per environment, re-run this script"
echo "  with separate values for each vault."
