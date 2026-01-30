# ADR-0004: Azure Container Apps Staging Infrastructure

## Status

**PENDING** - Infrastructure not yet provisioned

## Context

The ETL Contract Probe has been configured to validate API contracts against Azure Container Apps (ACA) staging environment at:
- URL: `https://qgp-staging.icytree-89d41650.uksouth.azurecontainerapps.io`

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
| Container App Environment | `icytree-89d41650` | Already exists |
| Container App | `qgp-staging` | **NEEDS CREATION** |
| Container Registry | (existing ACR) | Push access |
| Managed Identity | System-assigned | Key Vault access |

### Container App Configuration

```bash
az containerapp create \
  --name qgp-staging \
  --resource-group rg-qgp-staging \
  --environment icytree-89d41650 \
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

## Action Items

- [ ] Provision Container App `qgp-staging` in Azure Portal or via IaC
- [ ] Configure ingress and health probes
- [ ] Create `deploy-staging-aca.yml` workflow
- [ ] Update `environment_endpoints.json` to confirm ACA URL
- [ ] Run contract probe to confirm `VERIFIED` outcome
- [ ] Deprecate App Service staging deployment

## Related Documents

- [ADR-0003: SWA Gating Exception](ADR-0003-SWA-GATING-EXCEPTION.md)
- [Environment Endpoints](../evidence/environment_endpoints.json)
- [ETL Contract Probe](../../scripts/etl/contract_probe.py)
