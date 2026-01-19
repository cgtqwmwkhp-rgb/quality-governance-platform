# Production Deployment Runbook

**Status**: READY FOR EXECUTION  
**Last Updated**: 2026-01-19  
**Estimated Time**: 2-3 hours (first-time setup)

---

## Prerequisites Checklist

- [ ] Azure subscription with Owner/Contributor access
- [ ] GitHub repository admin access
- [ ] Azure CLI installed and authenticated (`az login`)
- [ ] Staging environment verified working

---

## Phase 1: Azure Resource Provisioning (45 min)

### Step 1.1: Create Production Resource Group

```bash
# Set variables
LOCATION="westeurope"
RG_NAME="rg-qgp-prod"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Create resource group
az group create \
  --name $RG_NAME \
  --location $LOCATION \
  --tags Environment=Production Application=QGP

# Verify
az group show --name $RG_NAME --query "{name:name, location:location, state:properties.provisioningState}"
```

**Evidence**: Screenshot or output showing resource group created

### Step 1.2: Create Azure Container Registry (if not shared with staging)

```bash
ACR_NAME="acrqgpprod"  # Must be globally unique, lowercase, alphanumeric

# Create ACR
az acr create \
  --resource-group $RG_NAME \
  --name $ACR_NAME \
  --sku Standard \
  --admin-enabled true

# Get ACR credentials (for GitHub secrets)
az acr credential show --name $ACR_NAME --query "{username:username, password:passwords[0].value}"
```

**Alternative**: Use existing staging ACR if appropriate for your security model

### Step 1.3: Create Azure Key Vault

```bash
KV_NAME="kv-qgp-prod"

# Create Key Vault
az keyvault create \
  --resource-group $RG_NAME \
  --name $KV_NAME \
  --location $LOCATION \
  --enable-rbac-authorization false

# Add secrets (replace values!)
az keyvault secret set --vault-name $KV_NAME --name "DATABASE-URL" \
  --value "postgresql+asyncpg://user:password@prod-db-server:5432/quality_governance"

az keyvault secret set --vault-name $KV_NAME --name "SECRET-KEY" \
  --value "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

az keyvault secret set --vault-name $KV_NAME --name "JWT-SECRET-KEY" \
  --value "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

# Verify secrets exist
az keyvault secret list --vault-name $KV_NAME --query "[].name" -o table
```

**Evidence**: Secret names listed (not values!)

### Step 1.4: Create Production Database

Option A: Azure Database for PostgreSQL Flexible Server

```bash
DB_SERVER="qgp-prod-db"
DB_ADMIN="qgpadmin"
DB_PASSWORD="<GENERATE_STRONG_PASSWORD>"

az postgres flexible-server create \
  --resource-group $RG_NAME \
  --name $DB_SERVER \
  --location $LOCATION \
  --admin-user $DB_ADMIN \
  --admin-password "$DB_PASSWORD" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --version 16 \
  --high-availability Disabled

# Create database
az postgres flexible-server db create \
  --resource-group $RG_NAME \
  --server-name $DB_SERVER \
  --database-name quality_governance

# Allow Azure services
az postgres flexible-server firewall-rule create \
  --resource-group $RG_NAME \
  --name $DB_SERVER \
  --rule-name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

### Step 1.5: Create Azure Web App

```bash
APP_NAME="app-qgp-prod"  # Will be https://app-qgp-prod.azurewebsites.net
APP_PLAN="plan-qgp-prod"

# Create App Service Plan (Linux)
az appservice plan create \
  --resource-group $RG_NAME \
  --name $APP_PLAN \
  --sku P1V2 \
  --is-linux

# Create Web App for Containers
az webapp create \
  --resource-group $RG_NAME \
  --plan $APP_PLAN \
  --name $APP_NAME \
  --deployment-container-image-name mcr.microsoft.com/appsvc/staticsite:latest

# Configure for ACR
az webapp config container set \
  --resource-group $RG_NAME \
  --name $APP_NAME \
  --docker-custom-image-name "${ACR_NAME}.azurecr.io/quality-governance-platform:latest" \
  --docker-registry-server-url "https://${ACR_NAME}.azurecr.io"

# Enable managed identity for Key Vault access
az webapp identity assign \
  --resource-group $RG_NAME \
  --name $APP_NAME

# Get identity principal ID
IDENTITY_ID=$(az webapp identity show --resource-group $RG_NAME --name $APP_NAME --query principalId -o tsv)

# Grant Key Vault access
az keyvault set-policy \
  --name $KV_NAME \
  --object-id $IDENTITY_ID \
  --secret-permissions get list
```

**Evidence**: Web App URL accessible (even if showing default page)

---

## Phase 2: Service Principal for GitHub Actions (20 min)

### Step 2.1: Create Service Principal

```bash
SP_NAME="sp-github-qgp-prod"

# Create SP with Contributor role on resource group
az ad sp create-for-rbac \
  --name $SP_NAME \
  --role Contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_NAME \
  --sdk-auth

# IMPORTANT: Save the JSON output - this is AZURE_PROD_CREDENTIALS
```

**Output Format** (save this securely):
```json
{
  "clientId": "xxx",
  "clientSecret": "xxx",
  "subscriptionId": "xxx",
  "tenantId": "xxx",
  ...
}
```

### Step 2.2: Grant Additional Permissions

```bash
SP_APP_ID=$(az ad sp list --display-name $SP_NAME --query "[0].appId" -o tsv)

# Grant ACR push/pull
az role assignment create \
  --assignee $SP_APP_ID \
  --role AcrPush \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_NAME/providers/Microsoft.ContainerRegistry/registries/$ACR_NAME

# Grant Key Vault secrets access
az keyvault set-policy \
  --name $KV_NAME \
  --spn $SP_APP_ID \
  --secret-permissions get list
```

---

## Phase 3: GitHub Configuration (15 min)

### Step 3.1: Add Repository Secrets

Go to: `https://github.com/<org>/<repo>/settings/secrets/actions`

Add these secrets:

| Secret Name | Value | Source |
|-------------|-------|--------|
| `PROD_ACR_NAME` | `acrqgpprod` | Step 1.2 |
| `PROD_AZURE_WEBAPP_NAME` | `app-qgp-prod` | Step 1.5 |
| `AZURE_PROD_CREDENTIALS` | Full JSON from Step 2.1 | Service Principal output |

### Step 3.2: Create GitHub Environment

Go to: `https://github.com/<org>/<repo>/settings/environments`

1. Click **New environment**
2. Name: `production`
3. Configure protection rules:
   - [x] Required reviewers: Add 1-2 team leads
   - [x] Wait timer: 5 minutes (optional cooldown)
   - [ ] Deployment branches: Only `main` branch

### Step 3.3: Verify Workflow References Environment

The `deploy-production.yml` already includes:
```yaml
environment:
  name: production
  url: https://${{ secrets.PROD_AZURE_WEBAPP_NAME }}.azurewebsites.net
```

---

## Phase 4: Pre-Deployment Verification (30 min)

### Step 4.1: Verify Staging Health

```bash
STAGING_URL="https://<staging-app-name>.azurewebsites.net"

# Health check
curl -s "$STAGING_URL/healthz" | jq .

# Readiness check  
curl -s "$STAGING_URL/readyz" | jq .

# API docs
curl -s -o /dev/null -w "%{http_code}" "$STAGING_URL/openapi.json"
```

**Expected**: All return 200 OK

### Step 4.2: Run Integration Tests Against Staging (Optional)

```bash
# If you have API tests that can run against staging
STAGING_URL="https://<staging-app-name>.azurewebsites.net" \
  pytest tests/integration/test_health.py -v
```

### Step 4.3: Document Current State

```markdown
## Pre-Deployment Verification
- [ ] Staging health check: PASS
- [ ] Staging readiness check: PASS
- [ ] Latest staging deployment: <commit SHA>
- [ ] CI status on main: GREEN
- [ ] Last staging deployment time: <timestamp>
```

---

## Phase 5: Production Deployment (15 min)

### Option A: Manual Dispatch (Recommended for First Deploy)

1. Go to: `https://github.com/<org>/<repo>/actions/workflows/deploy-production.yml`
2. Click **Run workflow**
3. Select branch: `main`
4. Check: `✓ Confirm staging has been verified`
5. Enter reason: `Initial production deployment after staging verification`
6. Click **Run workflow**
7. Wait for reviewer approval (if configured)

### Option B: Release Tag

```bash
# Create and push a release tag
git tag -a v1.0.0 -m "Production release v1.0.0"
git push origin v1.0.0

# Or use GitHub Releases UI:
# https://github.com/<org>/<repo>/releases/new
```

---

## Phase 6: Post-Deployment Verification (15 min)

### Step 6.1: Health Checks

```bash
PROD_URL="https://app-qgp-prod.azurewebsites.net"

# Health check
curl -s "$PROD_URL/healthz" | jq .

# Readiness check (includes DB)
curl -s "$PROD_URL/readyz" | jq .

# API docs
curl -s "$PROD_URL/openapi.json" | head -20
```

### Step 6.2: Smoke Tests

```bash
# Root page
curl -s -o /dev/null -w "%{http_code}" "$PROD_URL/"

# Auth endpoints (should return 401/422 without credentials)
curl -s -o /dev/null -w "%{http_code}" "$PROD_URL/api/v1/auth/me"

# API listing (if public)
curl -s -o /dev/null -w "%{http_code}" "$PROD_URL/api/v1/incidents"
```

### Step 6.3: Document Deployment

```markdown
## Deployment Record
- Deployed at: <timestamp>
- Deployed by: <username>
- Commit: <SHA>
- Image: <ACR image tag>
- Verification:
  - [x] Health check: PASS
  - [x] Readiness check: PASS
  - [x] Smoke tests: PASS
```

---

## Rollback Procedure

If issues are detected post-deployment:

### Immediate Rollback (< 5 min)

```bash
# Get previous image tag
az webapp config container show \
  --resource-group rg-qgp-prod \
  --name app-qgp-prod

# Rollback to previous image
az webapp config container set \
  --resource-group rg-qgp-prod \
  --name app-qgp-prod \
  --docker-custom-image-name "${ACR_NAME}.azurecr.io/quality-governance-platform:<previous-tag>"

# Restart
az webapp restart --resource-group rg-qgp-prod --name app-qgp-prod
```

### Database Rollback (if migrations were run)

```bash
# SSH into the app or run via Container Instance
alembic downgrade -1
```

---

## Appendix: Quick Reference

### Secrets Summary

| Secret | GitHub Secret Name | Azure Source |
|--------|-------------------|--------------|
| ACR Name | `PROD_ACR_NAME` | Container Registry name |
| Web App Name | `PROD_AZURE_WEBAPP_NAME` | App Service name |
| Service Principal | `AZURE_PROD_CREDENTIALS` | `az ad sp create-for-rbac --sdk-auth` output |

### URLs

| Environment | URL |
|-------------|-----|
| Staging | https://${AZURE_WEBAPP_NAME}.azurewebsites.net |
| Production | https://app-qgp-prod.azurewebsites.net |

### Commands Cheat Sheet

```bash
# Check app logs
az webapp log tail --resource-group rg-qgp-prod --name app-qgp-prod

# Check app settings
az webapp config appsettings list --resource-group rg-qgp-prod --name app-qgp-prod

# Restart app
az webapp restart --resource-group rg-qgp-prod --name app-qgp-prod

# Scale app
az appservice plan update --resource-group rg-qgp-prod --name plan-qgp-prod --sku P2V2
```

---

*Document Version: 1.0*
