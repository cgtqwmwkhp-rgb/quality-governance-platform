# Runbook: Redis Cache Failure

## Alert
- **Source:** Azure Monitor / OpenTelemetry
- **Severity:** Medium
- **Symptom:** Increased latency, /readyz shows redis: unavailable

## Impact

- Rate limiting falls back to in-memory (per-instance, less accurate)
- Response caching disabled, increased database load
- Session data may be lost if using Redis-backed sessions
- Application remains functional in degraded mode

## Diagnosis

1. Check Redis health via application health endpoint:
   ```bash
   curl -s https://app-qgp-prod.azurewebsites.net/readyz?verbose=true | jq '.checks.redis'
   ```

2. Check Azure Cache for Redis status:
   ```bash
   az redis show --name redis-qgp-prod --resource-group rg-qgp-prod --query provisioningState
   ```

3. Check Redis metrics (connections, memory, CPU):
   ```bash
   az monitor metrics list \
     --resource /subscriptions/<sub-id>/resourceGroups/rg-qgp-prod/providers/Microsoft.Cache/Redis/redis-qgp-prod \
     --metric connectedclients,usedmemory,serverLoad \
     --interval PT5M \
     --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)
   ```

4. Check if Redis is OOM (out of memory):
   ```bash
   az redis show --name redis-qgp-prod --resource-group rg-qgp-prod \
     --query "{sku:sku.name, capacity:sku.capacity, maxMemoryPolicy:redisConfiguration.maxmemoryPolicy}"
   ```

## Resolution

### If Redis instance is down:
1. Check Azure status page for regional outages
2. Restart Redis if stuck:
   ```bash
   az redis force-reboot --name redis-qgp-prod --resource-group rg-qgp-prod --reboot-type AllNodes
   ```
3. Application auto-reconnects; no app restart needed

### If Redis is OOM:
1. Flush non-critical caches if safe:
   ```bash
   az redis execute-command --name redis-qgp-prod --resource-group rg-qgp-prod \
     --command "FLUSHDB" --arguments "ASYNC"
   ```
2. Scale up Redis tier if recurring:
   ```bash
   az redis update --name redis-qgp-prod --resource-group rg-qgp-prod --sku Standard --vm-size C1
   ```

### If connection limit reached:
1. Check application connection pool settings
2. Restart application instances to release stale connections:
   ```bash
   az webapp restart --name app-qgp-prod --resource-group rg-qgp-prod
   ```

## Graceful Degradation

The application handles Redis failures gracefully:
- **Rate limiting:** Falls back to in-memory per-instance limiting
- **Caching:** Bypassed; requests go directly to the database
- **No user-facing errors:** Endpoints continue working, only slower

Cache auto-warms when Redis reconnects; no manual intervention required.

## Escalation
- **L1:** Monitor degradation, confirm auto-recovery
- **L2:** If Redis is down > 15 minutes, page infrastructure team
- **L3:** If database is overloaded due to cache loss, scale database and page backend lead
