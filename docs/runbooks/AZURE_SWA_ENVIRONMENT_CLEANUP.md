# Azure Static Web Apps Environment Cleanup Runbook

> **SAFETY FIRST**: This runbook NEVER uses hardcoded environment names. All deletions are based on ACTUAL environment names returned by Azure.

## Overview

Azure SWA creates preview/staging environments for each PR. Free tier allows **maximum 3 staging environments**. When this limit is exceeded, new deployments fail with:

```
The content server has rejected the request with: BadRequest
Reason: This Static Web App already has the maximum number of staging environments
```

## Pre-requisites

- Azure CLI installed and authenticated (`az login`)
- Contributor role on Static Web App resource
- Resource details:
  - **App Name**: `purple-water-03205fa03`
  - **Resource Group**: `rg-qgp-prod`

---

## SAFE Cleanup Procedure

### Step 1: List ALL Environments

```bash
# Login to Azure (if not already)
az login

# Set variables
SWA_APP_NAME="purple-water-03205fa03"
RESOURCE_GROUP="rg-qgp-prod"

# List ALL environments - OBSERVE THE OUTPUT CAREFULLY
az staticwebapp environment list \
  --name "$SWA_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --output table
```

**Expected output example:**
```
Name        Hostname                                                    Status
----------  ----------------------------------------------------------  --------
default     purple-water-03205fa03.6.azurestaticapps.net                Ready
85          purple-water-03205fa03-85.6.azurestaticapps.net             Ready
84          purple-water-03205fa03-84.6.azurestaticapps.net             Ready
83          purple-water-03205fa03-83.6.azurestaticapps.net             Ready
```

### Step 2: Identify Production Environment

**CRITICAL**: Production is typically named `default`. Verify by checking:
- It has the main hostname (no PR number suffix)
- It matches the production URL: `purple-water-03205fa03.6.azurestaticapps.net`

```bash
# Get the production environment name (should be 'default')
PRODUCTION_ENV=$(az staticwebapp environment list \
  --name "$SWA_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[?contains(hostname, '.azurestaticapps.net') && !contains(hostname, '-')].name" \
  --output tsv)

echo "Production environment identified: $PRODUCTION_ENV"
# Expected: "default"
```

### Step 3: DRY-RUN - List Environments to Delete

**NEVER delete without reviewing this list first!**

```bash
# Get list of ALL non-production environments
# These are safe to delete (they are PR preview environments)
NON_PROD_ENVS=$(az staticwebapp environment list \
  --name "$SWA_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[?name!='default'].name" \
  --output tsv)

echo "=========================================="
echo "DRY-RUN: Environments that WOULD be deleted:"
echo "=========================================="
for env in $NON_PROD_ENVS; do
  echo "  - $env"
done
echo "=========================================="
echo "Production (PROTECTED, will NOT be deleted): $PRODUCTION_ENV"
echo "=========================================="
echo ""
echo "Review the list above. If correct, proceed to Step 4."
echo "If 'default' appears in the delete list, STOP IMMEDIATELY."
```

### Step 4: Delete Non-Production Environments (CONFIRMED)

**Only proceed after reviewing the dry-run output!**

```bash
# SAFE DELETE: Only deletes environments that:
# 1. Are NOT named 'default'
# 2. Were explicitly listed in Step 3

for env in $NON_PROD_ENVS; do
  # Safety guard: NEVER delete 'default'
  if [ "$env" == "default" ]; then
    echo "ERROR: Attempted to delete production! Aborting."
    exit 1
  fi
  
  echo "Deleting environment: $env"
  az staticwebapp environment delete \
    --name "$SWA_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment-name "$env" \
    --yes 2>/dev/null && echo "  ✅ Deleted: $env" || echo "  ⚠️ Failed or not found: $env"
done
```

### Step 5: Verify Only Production Remains

```bash
echo ""
echo "=========================================="
echo "VERIFICATION: Current environments"
echo "=========================================="
az staticwebapp environment list \
  --name "$SWA_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --output table

# Count should be 1 (production only)
COUNT=$(az staticwebapp environment list \
  --name "$SWA_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "length(@)" \
  --output tsv)

if [ "$COUNT" -eq 1 ]; then
  echo "✅ SUCCESS: Only production environment remains"
else
  echo "⚠️ WARNING: $COUNT environments remain. Review the list above."
fi
```

### Step 6: Re-run PR #85 SWA Workflow

```bash
# Trigger workflow re-run
gh workflow run "Azure Static Web Apps CI/CD" --repo cgtqwmwkhp-rgb/quality-governance-platform --ref feat/investigations-stage-0.5

# Or via GitHub UI:
# https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/workflows/azure-static-web-apps-purple-water-03205fa03.yml
```

### Step 7: Verify Success

```bash
# Wait ~2 minutes, then check
gh run list --workflow "Azure Static Web Apps CI/CD" --repo cgtqwmwkhp-rgb/quality-governance-platform --limit 3
```

Expected: Latest run shows `conclusion: success` ✅

---

## Complete Safe Script (Copy-Paste Ready)

```bash
#!/bin/bash
# SAFE Azure SWA Environment Cleanup Script
# This script NEVER uses hardcoded environment names

set -e

SWA_APP_NAME="purple-water-03205fa03"
RESOURCE_GROUP="rg-qgp-prod"
DRY_RUN="${1:-true}"  # Default: dry-run mode

echo "=============================================="
echo "Azure SWA Environment Cleanup"
echo "App: $SWA_APP_NAME"
echo "Resource Group: $RESOURCE_GROUP"
echo "Mode: $([ "$DRY_RUN" == "true" ] && echo 'DRY-RUN' || echo 'EXECUTE')"
echo "=============================================="
echo ""

# Step 1: List all environments
echo "📋 Current environments:"
az staticwebapp environment list \
  --name "$SWA_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --output table

# Step 2: Identify production
PRODUCTION_ENV="default"
echo ""
echo "🔒 Production environment: $PRODUCTION_ENV (PROTECTED)"

# Step 3: Get non-production environments
NON_PROD_ENVS=$(az staticwebapp environment list \
  --name "$SWA_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[?name!='default'].name" \
  --output tsv)

if [ -z "$NON_PROD_ENVS" ]; then
  echo "✅ No preview environments to clean up."
  exit 0
fi

echo ""
echo "🧹 Preview environments to delete:"
for env in $NON_PROD_ENVS; do
  echo "  - $env"
done

# Step 4: Delete or dry-run
echo ""
if [ "$DRY_RUN" == "true" ]; then
  echo "⚠️  DRY-RUN MODE: No changes made."
  echo "To execute: $0 false"
else
  echo "🚀 EXECUTING CLEANUP..."
  for env in $NON_PROD_ENVS; do
    # Safety: Never delete 'default'
    if [ "$env" == "default" ]; then
      echo "❌ ABORT: Cannot delete production!"
      exit 1
    fi
    
    echo "  Deleting: $env"
    az staticwebapp environment delete \
      --name "$SWA_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --environment-name "$env" \
      --yes 2>/dev/null && echo "    ✅ Done" || echo "    ⚠️ Failed/NotFound"
  done
  
  echo ""
  echo "📋 Final state:"
  az staticwebapp environment list \
    --name "$SWA_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output table
fi
```

**Usage:**
```bash
# Dry-run (default, safe)
./cleanup-swa-envs.sh

# Execute cleanup
./cleanup-swa-envs.sh false
```

---

## Azure Portal Alternative

1. Navigate to: **Azure Portal** → **Static Web Apps** → **purple-water-03205fa03**
2. Click **Environments** in the left menu
3. You will see:
   - `Production` or `default` → **DO NOT DELETE**
   - Other entries (PR numbers like 85, 84, 83) → Safe to delete
4. For each non-production environment:
   - Click the row
   - Click **Delete**
   - Confirm deletion
5. Verify only Production remains
6. Re-run GitHub workflow

---

## Rollback / Safety

- Production environment (`default`) is protected by Azure and typically cannot be deleted via this method
- Even if attempted, the CLI requires the environment to be explicitly named
- If issues occur, pushing to `main` triggers automatic redeploy to production

---

## Validation Checklist

- [ ] `az staticwebapp environment list` shows actual environment names (not assumptions)
- [ ] Production (`default`) identified and excluded
- [ ] Dry-run reviewed before execution
- [ ] Only environments from list output are deleted
- [ ] Final environment count = 1 (production only)
- [ ] PR #85 SWA workflow re-run is green

---

## Prevention

See: `docs/runbooks/AZURE_SWA_GOVERNANCE.md` for automated cleanup policy.
