# ADR-0005: Azure Container Apps Staging Infrastructure

## Status

**ACCEPTED** - ACA staging fully provisioned and verified (2026-01-30)

## Context

The ETL Contract Probe has been configured to validate API contracts against Azure Container Apps (ACA) staging environment at:
- URL: `https://qgp-staging.ashymushroom-85447e68.uksouth.azurecontainerapps.io`

However, the current `deploy-staging.yml` workflow deploys to Azure App Service (Web App), not Azure Container Apps. The ACA Container App `qgp-staging` either does not exist or has no active revisions.

### Current Error

When probing the ACA URL, Azure returns:
```
Error 404 - This Container App is stopped or does not exist.
The Container App you have attempted to reach is currently stopped or does not exist.
```

This is an Azure ingress-level error, not an application-level 404.

## Decision

### Short-term (PENDING)

Until ACA staging infrastructure is provisioned:

1. The contract probe will report `UNAVAILABLE` with clear messaging: "Container App does not exist or is stopped"
2. The probe remains non-blocking in ADVISORY mode for PRs
3. The staging deployment continues to use Azure App Service

### Long-term (REQUIRED)

To achieve full ACA-only staging:

1. **Provision Azure Container Apps Environment** (if not exists)
2. **Create Container App `qgp-staging`** with:
   - Ingress: External, port 8000
   - Min replicas: 1
   - Max replicas: 3
   - Health probes: `/healthz` (liveness), `/readyz` (readiness)
3. **Create `deploy-staging-aca.yml`** workflow that:
   - Builds and pushes image to ACR
   - Deploys to Container App using `az containerapp update`
   - Runs contract probe in REQUIRED mode
4. **Deprecate** App Service staging after ACA is verified

## Infrastructure Requirements

### Azure Resources Needed

| Resource | Name | Configuration |
|----------|------|---------------|
| Container App Environment | `qgp-staging-env` | Already exists |
| Container App | `qgp-staging` | **NEEDS CREATION** |
| Container Registry | (existing ACR) | Push access |
| Managed Identity | System-assigned | Key Vault access |

### Container App Configuration

```bash
az containerapp create \
  --name qgp-staging \
  --resource-group rg-qgp-staging \
  --environment qgp-staging-env \
  --image <acr>.azurecr.io/quality-governance-platform:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --env-vars DATABASE_URL=secretref:database-url \
  --secrets database-url=keyvaultref:<keyvault-uri>/secrets/DATABASE-URL,identityref:<identity-id>
```

## Consequences

### Until ACA is provisioned

- Contract probe reports `UNAVAILABLE` (truthful)
- No false claims of verification
- Staging API continues to work via App Service (if needed for development)

### After ACA is provisioned

- Contract probe reports `VERIFIED`
- Full ACA-only staging achieved
- Consistent platform between staging and production

## Completed Actions

- [x] **Provision Container App `qgp-staging`** - Provisioned 2026-01-30
- [x] **Create ACA environment `qgp-staging-env`** - Provisioned 2026-01-30
- [x] **Update `deploy-staging.yml` workflow** - Uses ACA, not App Service
- [x] **Update `environment_endpoints.json`** - Points to ACA FQDN
- [x] **Contract probe returns `VERIFIED`** - All 7 endpoints passed
- [ ] Deprecate App Service staging deployment (optional cleanup)

## Infrastructure Details

### Azure Container Apps

| Resource | Value |
|----------|-------|
| **Container App** | `qgp-staging` |
| **Environment** | `qgp-staging-env` |
| **Resource Group** | `rg-qgp-staging` |
| **Region** | UK South |
| **FQDN** | `qgp-staging.ashymushroom-85447e68.uksouth.azurecontainerapps.io` |
| **Static IP** | `20.49.128.134` |

### Configuration

| Setting | Value |
|---------|-------|
| **Target Port** | 8000 |
| **Min Replicas** | 1 |
| **Max Replicas** | 3 |
| **CPU** | 0.5 |
| **Memory** | 1.0Gi |
| **Identity** | System-assigned managed identity |
| **Registry** | `acrqgpplantexpand.azurecr.io` |

### Secrets (from Key Vault `kv-qgp-staging`)

| ACA Secret | Key Vault Secret |
|------------|------------------|
| `database-url` | `DATABASE-URL` |
| `secret-key` | `SECRET-KEY` |
| `jwt-secret-key` | `JWT-SECRET-KEY` |

## Contract Probe Verification

```
Outcome:           VERIFIED
Reachable:         True
Endpoints Checked: 7
Endpoints Passed:  7
Message:           Target staging VERIFIED. All 7 contract checks passed.

Endpoint Details:
  ✅ health_legacy:   200 (74ms)
  ✅ identity:        200 (73ms)
  ✅ healthz:         200 (69ms)
  ✅ readyz:          200 (81ms)
  ✅ incidents_auth:  401 (69ms) - auth enforced
  ✅ complaints_auth: 401 (75ms) - auth enforced
  ✅ rtas_auth:       401 (76ms) - auth enforced
```

## Related Documents

- [ADR-0003: SWA Gating Exception](ADR-0003-SWA-GATING-EXCEPTION.md)
- [Environment Endpoints](../evidence/environment_endpoints.json)
- [ETL Contract Probe](../../scripts/etl/contract_probe.py)
