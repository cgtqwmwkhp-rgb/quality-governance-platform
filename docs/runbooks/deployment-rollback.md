# Runbook: Deployment Rollback

## Alert
- **Source:** Post-deployment health checks / Azure Monitor
- **Severity:** Critical
- **Symptom:** New deployment causing 5xx errors, degraded performance, or broken functionality

## When to Rollback

- 5xx error rate exceeds 1% after deployment
- `/readyz` health check returns unhealthy
- Critical user-facing functionality is broken
- P95 latency exceeds 2x baseline

## Pre-Rollback Checklist

1. Confirm the issue started after the latest deployment:
   ```bash
   gh run list --workflow=deploy-production.yml --limit=5
   ```

2. Verify current health status:
   ```bash
   curl -s https://app-qgp-prod.azurewebsites.net/readyz?verbose=true | jq .
   ```

3. Note the current deployment commit SHA for post-incident review:
   ```bash
   az webapp config show --name app-qgp-prod --resource-group rg-qgp-prod --query linuxFxVersion
   ```

## Rollback Procedure

### Option 1: GitHub Actions Rollback (preferred)
1. Trigger the rollback workflow:
   ```bash
   gh workflow run deploy-production.yml -f rollback=true
   ```
2. Monitor the workflow run:
   ```bash
   gh run watch
   ```

### Option 2: Azure Deployment Slot Swap
1. Swap back to the previous slot:
   ```bash
   az webapp deployment slot swap \
     --name app-qgp-prod \
     --resource-group rg-qgp-prod \
     --slot staging \
     --target-slot production
   ```

### Option 3: Manual Container Revert
1. Identify the last known-good image tag from the container registry:
   ```bash
   az acr repository show-tags --name crqgpprod --repository qgp-api --orderby time_desc --top 5
   ```
2. Redeploy with the previous tag:
   ```bash
   az webapp config container set \
     --name app-qgp-prod \
     --resource-group rg-qgp-prod \
     --container-image-name crqgpprod.azurecr.io/qgp-api:<previous-tag>
   ```

## Post-Rollback Verification

1. Verify health endpoint:
   ```bash
   curl -s https://app-qgp-prod.azurewebsites.net/readyz?verbose=true | jq .
   ```

2. Check error rates have returned to baseline:
   ```bash
   az monitor metrics list \
     --resource /subscriptions/<sub-id>/resourceGroups/rg-qgp-prod/providers/Microsoft.Web/sites/app-qgp-prod \
     --metric Http5xx \
     --interval PT1M \
     --start-time $(date -u -v-30M +%Y-%m-%dT%H:%M:%SZ)
   ```

3. Verify critical API endpoints:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" https://app-qgp-prod.azurewebsites.net/api/v1/health
   curl -s -o /dev/null -w "%{http_code}" https://app-qgp-prod.azurewebsites.net/api/v1/incidents
   ```

## Database Migration Rollback

If the failed deployment included database migrations:

1. Check for applied migrations:
   ```bash
   az webapp ssh --name app-qgp-prod --resource-group rg-qgp-prod
   # Inside container:
   alembic history --verbose
   alembic current
   ```

2. Downgrade to the previous migration:
   ```bash
   alembic downgrade -1
   ```

3. **WARNING:** Destructive migrations (column drops, table drops) cannot be safely reverted. Check migration files before downgrading.

## Escalation
- **L1:** On-call engineer performs rollback and verifies health
- **L2:** If rollback fails or involves data migration, page backend team lead
- **L3:** If data integrity is compromised, page CTO and activate DR plan

## Post-Incident

1. Create an incident record in the QGP system
2. Conduct root cause analysis within 24 hours
3. Document findings and update deployment process if needed
4. Link to the failed GitHub Actions run in the incident report
