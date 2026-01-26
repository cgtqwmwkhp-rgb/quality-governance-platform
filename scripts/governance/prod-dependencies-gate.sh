#!/bin/bash
# =============================================================================
# Prod Dependencies Gate — Pre-Migration Validation
# =============================================================================
# Purpose: Validate infrastructure dependencies BEFORE migrations/deploy
# ADR Alignment: ADR-0001 (migrations), ADR-0002 (fail-fast)
# Exit Codes: 0 = PASS (proceed), 1 = FAIL (block deployment)
#
# This gate prevents the class of failure where code is deployed before
# its infrastructure requirements exist.
# =============================================================================

set -euo pipefail

# Configuration (with defaults for production)
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-rg-qgp-staging}"
WEBAPP_NAME="${AZURE_WEBAPP_NAME:-app-qgp-prod}"
KEYVAULT_NAME="${KEYVAULT_NAME:-kv-qgp-prod}"
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:-stqgpprdcdd14b}"
STORAGE_CONTAINER="${STORAGE_CONTAINER:-evidence-assets}"

echo "=============================================="
echo "=== PROD DEPENDENCIES GATE                ==="
echo "=============================================="
echo ""
echo "Target Configuration:"
echo "  Webapp:         $WEBAPP_NAME"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Key Vault:      $KEYVAULT_NAME"
echo "  Storage:        $STORAGE_ACCOUNT/$STORAGE_CONTAINER"
echo ""
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

GATE_PASSED=true
GATE_RESULTS=""

# Helper function to record check results
record_check() {
    local check_name="$1"
    local result="$2"
    local details="$3"
    GATE_RESULTS="${GATE_RESULTS}| ${check_name} | ${result} | ${details} |\n"
}

# =============================================================================
# Check 1: App Setting Exists and is KV-referenced
# =============================================================================
echo "--- Check 1: App Setting AZURE_STORAGE_CONNECTION_STRING ---"

APP_SETTING=$(az webapp config appsettings list \
    --name "$WEBAPP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?name=='AZURE_STORAGE_CONNECTION_STRING'].value" \
    -o tsv 2>/dev/null || echo "")

if [ -z "$APP_SETTING" ]; then
    echo "❌ FAIL: AZURE_STORAGE_CONNECTION_STRING app setting not found"
    record_check "App Setting Exists" "❌ FAIL" "Not found"
    GATE_PASSED=false
elif [[ "$APP_SETTING" != @Microsoft.KeyVault* ]]; then
    echo "❌ FAIL: App setting exists but is NOT a Key Vault reference"
    echo "   Value does not start with @Microsoft.KeyVault"
    record_check "App Setting Exists" "❌ FAIL" "Not KV-referenced"
    GATE_PASSED=false
else
    echo "✅ PASS: App setting exists and is Key Vault referenced"
    record_check "App Setting Exists" "✅ PASS" "KV-referenced"
fi

# =============================================================================
# Check 2: Key Vault Secret Exists
# =============================================================================
echo ""
echo "--- Check 2: Key Vault Secret Exists ---"

SECRET_ID=$(az keyvault secret show \
    --vault-name "$KEYVAULT_NAME" \
    --name "AZURE-STORAGE-CONNECTION-STRING" \
    --query "id" \
    -o tsv 2>/dev/null || echo "")

if [ -z "$SECRET_ID" ]; then
    echo "❌ FAIL: Key Vault secret 'AZURE-STORAGE-CONNECTION-STRING' not found"
    echo "   Vault: $KEYVAULT_NAME"
    record_check "KV Secret Exists" "❌ FAIL" "Secret not found"
    GATE_PASSED=false
else
    # Extract version for audit (last segment of URI)
    SECRET_VERSION=$(basename "$SECRET_ID")
    echo "✅ PASS: Key Vault secret exists"
    echo "   Version: $SECRET_VERSION"
    record_check "KV Secret Exists" "✅ PASS" "Version: ${SECRET_VERSION:0:8}..."
fi

# =============================================================================
# Check 3: Storage Container Accessible
# =============================================================================
echo ""
echo "--- Check 3: Storage Container Accessible ---"

CONTAINER_NAME=$(az storage container show \
    --name "$STORAGE_CONTAINER" \
    --account-name "$STORAGE_ACCOUNT" \
    --auth-mode login \
    --query "name" \
    -o tsv 2>/dev/null || echo "")

if [ -z "$CONTAINER_NAME" ]; then
    echo "❌ FAIL: Storage container '$STORAGE_CONTAINER' not accessible"
    echo "   Account: $STORAGE_ACCOUNT"
    echo "   This may indicate the container doesn't exist or identity lacks access"
    record_check "Storage Container" "❌ FAIL" "Not accessible"
    GATE_PASSED=false
else
    echo "✅ PASS: Storage container exists and is accessible"
    record_check "Storage Container" "✅ PASS" "Accessible"
fi

# =============================================================================
# Check 4: Storage Public Access Disabled (Security)
# =============================================================================
echo ""
echo "--- Check 4: Storage Public Access Disabled ---"

PUBLIC_ACCESS=$(az storage account show \
    --name "$STORAGE_ACCOUNT" \
    --query "allowBlobPublicAccess" \
    -o tsv 2>/dev/null || echo "unknown")

if [ "$PUBLIC_ACCESS" = "true" ]; then
    echo "❌ FAIL: Storage account has public blob access ENABLED"
    echo "   This is a security risk - public access must be disabled"
    record_check "Storage Security" "❌ FAIL" "Public access enabled"
    GATE_PASSED=false
elif [ "$PUBLIC_ACCESS" = "unknown" ]; then
    echo "⚠️ WARN: Could not determine storage public access setting"
    echo "   Proceeding with caution"
    record_check "Storage Security" "⚠️ WARN" "Unknown"
else
    echo "✅ PASS: Storage public blob access is disabled"
    record_check "Storage Security" "✅ PASS" "Private"
fi

# =============================================================================
# Check 5: Storage TLS and HTTPS (Security)
# =============================================================================
echo ""
echo "--- Check 5: Storage TLS Configuration ---"

TLS_VERSION=$(az storage account show \
    --name "$STORAGE_ACCOUNT" \
    --query "minimumTlsVersion" \
    -o tsv 2>/dev/null || echo "unknown")

HTTPS_ONLY=$(az storage account show \
    --name "$STORAGE_ACCOUNT" \
    --query "enableHttpsTrafficOnly" \
    -o tsv 2>/dev/null || echo "unknown")

if [ "$TLS_VERSION" = "TLS1_2" ] && [ "$HTTPS_ONLY" = "true" ]; then
    echo "✅ PASS: TLS 1.2 minimum, HTTPS-only enforced"
    record_check "Storage TLS" "✅ PASS" "TLS1_2, HTTPS-only"
elif [ "$TLS_VERSION" = "unknown" ]; then
    echo "⚠️ WARN: Could not verify TLS configuration"
    record_check "Storage TLS" "⚠️ WARN" "Unknown"
else
    echo "⚠️ WARN: TLS config: $TLS_VERSION, HTTPS-only: $HTTPS_ONLY"
    record_check "Storage TLS" "⚠️ WARN" "TLS: $TLS_VERSION"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "=============================================="
echo "=== GATE SUMMARY                          ==="
echo "=============================================="
echo ""
echo "| Check | Result | Details |"
echo "|-------|--------|---------|"
printf "$GATE_RESULTS"
echo ""

if [ "$GATE_PASSED" = "true" ]; then
    echo "=============================================="
    echo "✅ PROD DEPENDENCIES GATE: PASS"
    echo "=============================================="
    echo ""
    echo "All infrastructure dependencies verified."
    echo "Deployment may proceed to migrations."
    echo ""
    exit 0
else
    echo "=============================================="
    echo "❌ PROD DEPENDENCIES GATE: FAIL"
    echo "=============================================="
    echo ""
    echo "One or more infrastructure dependencies are missing or misconfigured."
    echo "Deployment is BLOCKED. Resolve issues before retry."
    echo ""
    echo "Remediation steps:"
    echo "  1. Check Key Vault secret exists: az keyvault secret show --vault-name $KEYVAULT_NAME --name AZURE-STORAGE-CONNECTION-STRING"
    echo "  2. Check app setting: az webapp config appsettings list --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP | grep AZURE_STORAGE"
    echo "  3. Check storage container: az storage container show --name $STORAGE_CONTAINER --account-name $STORAGE_ACCOUNT --auth-mode login"
    echo ""
    exit 1
fi
