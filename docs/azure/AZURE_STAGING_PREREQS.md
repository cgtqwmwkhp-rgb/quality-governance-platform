# Azure Staging Deployment: Prerequisites Checklist

**Purpose**: Verify all prerequisites before executing Azure staging deployment  
**Target Environment**: Staging (non-production)  
**Deployment Script**: `scripts/deploy_azure_staging.sh`  
**Status**: ⏳ PENDING (awaiting Gate 1 evidence)

---

## Overview

This checklist must be completed **before** executing the Azure staging deployment script. All prerequisites must be verified and documented to ensure a safe and successful deployment.

**Estimated Time**: 30-45 minutes (one-time setup)

---

## Prerequisite Categories

1. [Azure Account and Subscription](#1-azure-account-and-subscription)
2. [Azure CLI and Authentication](#2-azure-cli-and-authentication)
3. [Region Selection and Quotas](#3-region-selection-and-quotas)
4. [Resource Naming Conventions](#4-resource-naming-conventions)
5. [Budget Alerts and Cost Management](#5-budget-alerts-and-cost-management)
6. [Required Azure Roles and Permissions](#6-required-azure-roles-and-permissions)
7. [Container Registry and Image Tagging](#7-container-registry-and-image-tagging)
8. [Safety Checks and Guardrails](#8-safety-checks-and-guardrails)

---

## 1. Azure Account and Subscription

### 1.1 Azure Account

- [ ] Azure account created and active
- [ ] Account has access to Azure Portal (https://portal.azure.com)
- [ ] Multi-factor authentication (MFA) enabled (recommended)

**Verification**:
```bash
az login
az account show
```

**Expected Output**:
```json
{
  "id": "<subscription-id>",
  "name": "<subscription-name>",
  "state": "Enabled",
  "tenantId": "<tenant-id>",
  "user": {
    "name": "<user-email>",
    "type": "user"
  }
}
```

### 1.2 Subscription Selection

- [ ] Correct subscription selected for staging deployment
- [ ] Subscription is **not** the production subscription (if production exists)
- [ ] Subscription has sufficient credit or billing enabled

**Verification**:
```bash
az account list --output table
az account set --subscription "<subscription-name-or-id>"
az account show --query name -o tsv
```

**Record**:
- **Subscription Name**: [TO BE FILLED]
- **Subscription ID**: [TO BE FILLED]
- **Tenant ID**: [TO BE FILLED]

---

## 2. Azure CLI and Authentication

### 2.1 Azure CLI Installation

- [ ] Azure CLI installed (version 2.50.0 or later)
- [ ] Azure CLI extensions up to date

**Verification**:
```bash
az --version
az upgrade  # If needed
```

**Expected Output**:
```
azure-cli                         2.50.0
...
```

### 2.2 Authentication

- [ ] Logged in to Azure CLI
- [ ] Correct subscription selected
- [ ] No authentication errors

**Verification**:
```bash
az account show
az group list --output table  # Should not error
```

### 2.3 Docker Installation

- [ ] Docker installed and running (version 20.10+)
- [ ] Docker Compose installed (version 2.0+)
- [ ] Docker daemon is running

**Verification**:
```bash
docker --version
docker compose version
docker ps  # Should not error
```

**Record**:
- **Azure CLI Version**: [TO BE FILLED]
- **Docker Version**: [TO BE FILLED]
- **Docker Compose Version**: [TO BE FILLED]

---

## 3. Region Selection and Quotas

### 3.1 Region Selection

- [ ] Region selected based on requirements (latency, compliance, cost)
- [ ] Region supports all required services (App Service, PostgreSQL Flexible Server, ACR, Key Vault, Application Insights)

**Recommended Regions for Staging**:
- `eastus` (US East)
- `westeurope` (West Europe)
- `southeastasia` (Southeast Asia)

**Verification**:
```bash
# Check if region supports App Service
az appservice list-locations --sku B2 --query "[].name" -o tsv

# Check if region supports PostgreSQL Flexible Server
az postgres flexible-server list-skus --location <region> --query "[].name" -o tsv
```

**Record**:
- **Selected Region**: [TO BE FILLED, e.g., eastus]
- **Reason**: [TO BE FILLED, e.g., lowest latency for US users]

### 3.2 Quota Checks

- [ ] Sufficient quota for App Service (B2 SKU, 1 instance minimum)
- [ ] Sufficient quota for PostgreSQL Flexible Server (B1ms SKU, 1 instance minimum)
- [ ] Sufficient quota for Container Registry (Basic SKU, 1 registry minimum)

**Verification**:
```bash
# Check App Service quota
az vm list-usage --location <region> --query "[?name.value=='cores'].{Name:name.localizedValue, Current:currentValue, Limit:limit}" -o table

# Check PostgreSQL quota
az postgres flexible-server list-skus --location <region> --query "[?name=='Standard_B1ms'].{Name:name, Tier:tier}" -o table
```

**Record**:
- **App Service Cores Available**: [TO BE FILLED]
- **PostgreSQL Quota Available**: [TO BE FILLED]
- **Any Quota Issues**: [NONE or describe]

---

## 4. Resource Naming Conventions

### 4.1 Naming Standards

All Azure resources must follow a consistent naming convention:

| Resource Type | Naming Pattern | Example |
|---------------|----------------|---------|
| Resource Group | `rg-<app>-<env>` | `rg-qgp-staging` |
| App Service Plan | `plan-<app>-<env>` | `plan-qgp-staging` |
| App Service | `<app>-<env>` | `qgp-staging` |
| PostgreSQL Server | `psql-<app>-<env>` | `psql-qgp-staging` |
| Container Registry | `acr<app><env>` (no hyphens) | `acrqgpstaging` |
| Key Vault | `kv-<app>-<env>` | `kv-qgp-staging` |
| Application Insights | `appi-<app>-<env>` | `appi-qgp-staging` |

**Constraints**:
- **App Service name**: Must be globally unique (DNS name)
- **Container Registry name**: Must be globally unique, alphanumeric only, 5-50 characters
- **Key Vault name**: Must be globally unique, 3-24 characters, alphanumeric and hyphens only

### 4.2 Name Availability Check

- [ ] App Service name is available
- [ ] Container Registry name is available
- [ ] Key Vault name is available

**Verification**:
```bash
# Check App Service name availability
az webapp check-name --name qgp-staging --query nameAvailable -o tsv

# Check Container Registry name availability
az acr check-name --name acrqgpstaging --query nameAvailable -o tsv

# Check Key Vault name availability
az keyvault list --query "[?name=='kv-qgp-staging'].name" -o tsv
# (Should return empty if available)
```

**Record**:
- **Resource Group Name**: [TO BE FILLED, default: rg-qgp-staging]
- **App Service Name**: [TO BE FILLED, default: qgp-staging]
- **Container Registry Name**: [TO BE FILLED, default: acrqgpstaging]
- **Key Vault Name**: [TO BE FILLED, default: kv-qgp-staging]
- **Name Conflicts**: [NONE or describe alternatives]

---

## 5. Budget Alerts and Cost Management

### 5.1 Cost Estimation

**Estimated Monthly Cost for Staging**:

| Service | SKU | Quantity | Est. Cost/Month |
|---------|-----|----------|-----------------|
| App Service | B2 (2 cores, 3.5 GB) | 1 instance | ~$55 |
| PostgreSQL | B1ms (1 vCore, 2 GB) | 1 instance | ~$12 |
| Container Registry | Basic | 1 registry | ~$5 |
| Key Vault | Standard | 1 vault | ~$0.03 |
| Application Insights | Pay-as-you-go | 1 GB/month | ~$2.30 |
| **Total** | | | **~$75-90/month** |

**Note**: Actual costs may vary based on usage, data transfer, and region.

### 5.2 Budget Alert Setup

- [ ] Budget alert configured for staging subscription or resource group
- [ ] Alert threshold set (recommended: $100/month for staging)
- [ ] Alert recipients configured (email or webhook)

**Setup**:
```bash
# Create budget alert (via Azure Portal)
# 1. Go to Cost Management + Billing
# 2. Select Budgets
# 3. Create budget:
#    - Scope: Resource group (rg-qgp-staging)
#    - Amount: $100/month
#    - Alert threshold: 80% ($80)
#    - Alert recipients: <your-email>
```

**Record**:
- **Budget Amount**: [TO BE FILLED, recommended: $100/month]
- **Alert Threshold**: [TO BE FILLED, recommended: 80%]
- **Alert Recipients**: [TO BE FILLED]

### 5.3 Cost Optimization

- [ ] Auto-shutdown configured for App Service (if applicable)
- [ ] Backup retention set to minimum for staging (7 days)
- [ ] Monitoring data retention set to minimum (30 days)

---

## 6. Required Azure Roles and Permissions

### 6.1 Required Roles

The user or service principal executing the deployment script must have the following roles:

| Role | Scope | Purpose |
|------|-------|---------|
| **Contributor** | Subscription or Resource Group | Create and manage resources |
| **User Access Administrator** | Resource Group | Assign managed identity permissions |

**Verification**:
```bash
# Check role assignments
az role assignment list --assignee <user-email-or-object-id> --output table

# Required output should include:
# - Contributor (at subscription or resource group level)
# - User Access Administrator (at resource group level)
```

### 6.2 Service Principal (Optional)

If using a service principal for deployment (e.g., in CI/CD):

- [ ] Service principal created
- [ ] Service principal has Contributor role
- [ ] Service principal has User Access Administrator role
- [ ] Service principal credentials stored securely (GitHub Secrets, Azure Key Vault)

**Creation**:
```bash
# Create service principal
az ad sp create-for-rbac --name "qgp-staging-deployer" \
  --role Contributor \
  --scopes /subscriptions/<subscription-id>/resourceGroups/rg-qgp-staging

# Assign User Access Administrator role
az role assignment create \
  --assignee <service-principal-app-id> \
  --role "User Access Administrator" \
  --scope /subscriptions/<subscription-id>/resourceGroups/rg-qgp-staging
```

**Record**:
- **Deployment Method**: [User or Service Principal]
- **User Email**: [TO BE FILLED if user]
- **Service Principal App ID**: [TO BE FILLED if service principal]
- **Roles Verified**: [YES/NO]

---

## 7. Container Registry and Image Tagging

### 7.1 Image Tagging Policy

**Policy**: All production and staging deployments must use **digest-pinned images** (not tags).

**Rationale**:
- Tags are mutable (can be overwritten)
- Digests are immutable (content-addressable)
- Digest pinning ensures exact image version is deployed

**Format**:
- ❌ **Bad**: `acrqgpstaging.azurecr.io/quality-governance-platform:latest`
- ❌ **Bad**: `acrqgpstaging.azurecr.io/quality-governance-platform:v1.0.0`
- ✅ **Good**: `acrqgpstaging.azurecr.io/quality-governance-platform@sha256:abc123...`

### 7.2 Image Build and Push

- [ ] Docker image built locally or in CI
- [ ] Image tagged with Git commit SHA (for traceability)
- [ ] Image pushed to Azure Container Registry
- [ ] Image digest recorded for deployment

**Commands**:
```bash
# Build image
docker build -t quality-governance-platform:$(git rev-parse --short HEAD) .

# Tag for ACR
docker tag quality-governance-platform:$(git rev-parse --short HEAD) \
  acrqgpstaging.azurecr.io/quality-governance-platform:$(git rev-parse --short HEAD)

# Push to ACR
az acr login --name acrqgpstaging
docker push acrqgpstaging.azurecr.io/quality-governance-platform:$(git rev-parse --short HEAD)

# Get image digest
az acr repository show --name acrqgpstaging \
  --image quality-governance-platform:$(git rev-parse --short HEAD) \
  --query digest -o tsv
```

**Record**:
- **Git Commit SHA**: [TO BE FILLED]
- **Image Tag**: [TO BE FILLED, e.g., 749cd4c]
- **Image Digest**: [TO BE FILLED, e.g., sha256:abc123...]
- **ACR URL**: [TO BE FILLED, e.g., acrqgpstaging.azurecr.io]

---

## 8. Safety Checks and Guardrails

### 8.1 Pre-Deployment Checklist

- [ ] **Gate 1 Met**: D0 rehearsal execution evidence committed (BLOCKER)
- [ ] **Correct Subscription**: Verified not production subscription
- [ ] **Correct Region**: Verified region selection
- [ ] **Name Availability**: All resource names available
- [ ] **Quota Availability**: Sufficient quota for all resources
- [ ] **Budget Alert**: Budget alert configured
- [ ] **Permissions**: User has required roles
- [ ] **Image Digest**: Image digest recorded (not tag)
- [ ] **Backup Plan**: Rollback procedure reviewed
- [ ] **Secrets**: No secrets in repository (verified)

### 8.2 Deployment Dry Run

- [ ] Review deployment script (`scripts/deploy_azure_staging.sh`)
- [ ] Understand each step (12 steps total)
- [ ] Identify potential failure points
- [ ] Prepare troubleshooting resources

**Script Steps**:
1. Prerequisites check (Azure CLI, Docker)
2. Azure login and subscription verification
3. Resource group creation
4. Azure Container Registry creation
5. Docker image build and push
6. PostgreSQL Flexible Server creation
7. Azure Key Vault creation
8. Secret generation and storage
9. App Service Plan creation
10. Web App creation with container deployment
11. Managed identity configuration
12. Application settings configuration

### 8.3 Rollback Readiness

- [ ] Previous image digest recorded (if redeployment)
- [ ] Database backup strategy understood
- [ ] Rollback procedure reviewed (`docs/AZURE_STAGING_BLUEPRINT.md`)
- [ ] Rollback time estimate: ~5-10 minutes

**Rollback Commands** (for reference):
```bash
# Redeploy previous image
az webapp config container set --name qgp-staging --resource-group rg-qgp-staging \
  --docker-custom-image-name acrqgpstaging.azurecr.io/quality-governance-platform@sha256:<previous-digest>

# Restart app
az webapp restart --name qgp-staging --resource-group rg-qgp-staging
```

### 8.4 DNS and Custom Domain

- [ ] **Out of Scope for Staging**: Custom domain is not required for staging
- [ ] Default Azure domain is acceptable: `qgp-staging.azurewebsites.net`
- [ ] HTTPS is enforced (Azure-managed certificate)

---

## Prerequisite Completion Summary

**Overall Status**: [PENDING/READY]

**Checklist Summary**:
- [ ] 1. Azure Account and Subscription (2/2 items)
- [ ] 2. Azure CLI and Authentication (3/3 items)
- [ ] 3. Region Selection and Quotas (2/2 items)
- [ ] 4. Resource Naming Conventions (2/2 items)
- [ ] 5. Budget Alerts and Cost Management (3/3 items)
- [ ] 6. Required Azure Roles and Permissions (2/2 items)
- [ ] 7. Container Registry and Image Tagging (2/2 items)
- [ ] 8. Safety Checks and Guardrails (4/4 items)

**Total Items**: 20/20

**Blockers**:
- ⏳ **Gate 1**: D0 rehearsal execution evidence not yet committed (BLOCKER)
- [Add any other blockers here]

**Ready for Deployment**: [YES/NO]

---

## Next Steps

### If Prerequisites Are Met

1. ✅ All checklist items completed
2. ✅ Gate 1 evidence committed
3. ➡️ Execute deployment script: `./scripts/deploy_azure_staging.sh`
4. ➡️ Proceed to Phase 4: Post-deploy verification

### If Prerequisites Are Not Met

1. ⏳ Complete remaining checklist items
2. ⏳ Wait for Gate 1 evidence (D0 rehearsal execution)
3. ⏳ Resolve any blockers
4. ⏳ Re-verify checklist before deployment

---

## References

- **Deployment Script**: `scripts/deploy_azure_staging.sh`
- **Azure Staging Blueprint**: `docs/AZURE_STAGING_BLUEPRINT.md`
- **Deployment Runbook**: `docs/DEPLOYMENT_RUNBOOK.md`
- **Gate 1 Requirements**: `docs/evidence/GATE_1_EVIDENCE_REQUIREMENTS.md`
- **D0 Rehearsal Runbook**: `docs/runbooks/D0_REHEARSAL_RUNBOOK.md`

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-05  
**Maintained By**: Platform Team
