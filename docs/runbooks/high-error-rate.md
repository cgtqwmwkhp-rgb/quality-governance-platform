# Runbook: High Error Rate (5xx > 1%)

## Alert
- **Source:** Azure Monitor / OpenTelemetry
- **Severity:** Critical
- **SLO Impact:** API Availability (target 99.9%)

## Diagnosis

1. Check application logs for the most common error:
   ```bash
   az webapp log tail --name app-qgp-prod --resource-group rg-qgp-prod
   ```

2. Check if recent deployment caused the issue:
   ```bash
   gh run list --workflow=deploy-production.yml --limit=5
   ```

3. Check database connectivity:
   ```bash
   curl -s https://app-qgp-prod.azurewebsites.net/readyz?verbose=true | jq .
   ```

4. Check circuit breaker states:
   - If email/SMS circuit is open, the service is degraded but functional
   - If database is unhealthy, this is the root cause

## Resolution

### If caused by recent deployment:
1. Trigger rollback: `gh workflow run deploy-production.yml -f rollback=true`
2. Verify health: `curl https://app-qgp-prod.azurewebsites.net/readyz`

### If caused by database:
1. Check Azure PostgreSQL status in portal
2. Check connection pool exhaustion in metrics
3. Restart the app service: `az webapp restart --name app-qgp-prod --resource-group rg-qgp-prod`

### If caused by external dependency:
1. Check circuit breaker states via `/readyz?verbose=true`
2. Circuit breakers auto-recover after the recovery timeout (60s for email/SMS, 120s for AI)
3. No manual action needed unless circuit stays open > 10 minutes

## Escalation
- **L1:** On-call engineer checks dashboard and applies runbook
- **L2:** If unresolved after 15 minutes, page backend team lead
- **L3:** If data loss suspected, page CTO and activate DR plan
