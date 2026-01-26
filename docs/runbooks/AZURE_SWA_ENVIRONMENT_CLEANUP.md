# Azure Static Web Apps Environment Cleanup Runbook

## Overview

Azure SWA creates preview/staging environments for each PR. Free tier allows **maximum 3 staging environments**. When this limit is exceeded, new deployments fail with:

```
The content server has rejected the request with: BadRequest
Reason: This Static Web App already has the maximum number of staging environments
```

## Pre-requisites

- Azure CLI installed and authenticated
- Contributor role on Static Web App resource
- Resource details:
  - **App Name**: `purple-water-03205fa03`
  - **Resource Group**: `rg-qgp-prod` (verify in Azure Portal)
  - **Subscription**: (your subscription ID)

## Remediation Steps

### Step 1: List Current Environments

```bash
# Login to Azure (if not already)
az login

# List all environments for the SWA app
az staticwebapp environment list \
  --name purple-water-03205fa03 \
  --resource-group rg-qgp-prod \
  --output table
```

Expected output:
```
Name        Hostname                                                          Status
----------  ----------------------------------------------------------------  --------
default     purple-water-03205fa03.6.azurestaticapps.net                       Ready
85          purple-water-03205fa03-85.6.azurestaticapps.net                    Ready
84          purple-water-03205fa03-84.6.azurestaticapps.net                    Ready
...
```

### Step 2: Identify Safe-to-Delete Environments

**NEVER DELETE**: `default` (this is production)

**SAFE TO DELETE**: Any numbered environment (these are PR preview environments)

Cross-reference with closed PRs:
```bash
gh pr list --state closed --limit 20 --json number,state
```

### Step 3: Delete Stale Environments

```bash
# Delete a specific environment (replace <env-name> with the environment name, e.g., "84")
az staticwebapp environment delete \
  --name purple-water-03205fa03 \
  --resource-group rg-qgp-prod \
  --environment-name <env-name> \
  --yes

# Example: Delete environments for closed PRs
for env in 84 83 82 81 80 79 78; do
  echo "Deleting environment $env..."
  az staticwebapp environment delete \
    --name purple-water-03205fa03 \
    --resource-group rg-qgp-prod \
    --environment-name "$env" \
    --yes 2>/dev/null || echo "Environment $env not found or already deleted"
done
```

### Step 4: Verify Cleanup

```bash
az staticwebapp environment list \
  --name purple-water-03205fa03 \
  --resource-group rg-qgp-prod \
  --output table
```

Should show only `default` (production) or minimal environments.

### Step 5: Re-run Failed Workflow

```bash
# Trigger workflow re-run for PR #85
gh workflow run "Azure Static Web Apps CI/CD" --ref feat/investigations-stage-0.5

# Or manually via GitHub UI:
# https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/workflows/azure-static-web-apps-purple-water-03205fa03.yml
```

### Step 6: Verify Success

```bash
# Check latest workflow run status
gh run list --workflow "Azure Static Web Apps CI/CD" --limit 3
```

## Validation Checklist

- [ ] Environments list shows ≤3 preview environments
- [ ] Production (`default`) environment is intact
- [ ] Azure SWA workflow run is green
- [ ] PR #85 can deploy successfully

## Rollback

If production was accidentally impacted:
1. The production environment cannot be deleted via CLI (protected)
2. If issues occur, push to main triggers automatic redeploy
3. Previous deployments are available in the Deployments history in Azure Portal

## Prevention

See: `docs/runbooks/AZURE_SWA_GOVERNANCE.md` for automated cleanup policy.
