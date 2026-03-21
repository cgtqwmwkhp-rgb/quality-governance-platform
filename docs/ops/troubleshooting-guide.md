# Troubleshooting Guide (D32 — Supportability & Operability)

Operational troubleshooting for the Quality Governance Platform: symptoms, likely causes, and resolutions.

## Diagnostic Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/healthz` | **Liveness** — process is up; use for kube/App Service liveness probes. |
| `/readyz` | **Readiness** — full dependency check (e.g., DB, Redis); fails if the app cannot serve traffic safely. |
| `/api/v1/meta/version` | **Build info** — deployed SHA, version labels; compare with GitHub Actions output. |
| `/metrics/resources` | **Runtime stats** — memory, CPU-ish signals, worker/thread hints as exposed by the app. |

## Common Issues Table

| # | Symptom | Likely Cause | Resolution |
|---|---------|--------------|------------|
| 1 | `503` on all routes | App not ready; dependency down | Check `/readyz`; fix DB/Redis; restart after dependency healthy |
| 2 | `503` intermittent | Pool exhaustion; slow DB | Increase pool size cautiously; kill long queries; optimize hot paths |
| 3 | High API latency | N+1 queries; missing indexes | Profile SQL; add indexes; cache read-heavy data in Redis |
| 4 | `401` / `403` spikes | Token expiry; misconfigured auth | Verify IdP status; check clock skew; roll keys if rotation failed |
| 5 | `500` on specific route | Recent deploy; bad input validation | Roll back or hotfix; check logs for stack trace |
| 6 | Celery tasks not running | Workers down; Redis unreachable | Restart workers; verify Redis URL and network |
| 7 | Tasks stuck in queue | Poison message; deadlock in task | Inspect failed task logs; requeue with fix; use DLQ if configured |
| 8 | Redis connection errors | Firewall; TLS; wrong port | Validate VNet/private link; connection string; cert chain |
| 9 | Redis OOM / evictions | Memory pressure; large keys | Increase tier; TTL on cache keys; audit key patterns |
|10 | DB “too many connections” | Pool leak; too many replicas | Fix leak; right-size pool; limit concurrent workers |
|11 | Migration fails mid-run | Lock timeout; incompatible schema | Stop traffic if needed; restore from backup; fix migration; re-run |
|12 | Frontend blank after deploy | Service worker serving stale bundle | Hard refresh; unregister SW; verify cache headers |
|13 | API works in browser, not SPA | CORS misconfiguration | Align `Access-Control-*` with app origin; preflight checks |
|14 | SHA mismatch / wrong version | Wrong slot; cached image | Verify GitHub Actions artifact; redeploy; check `/api/v1/meta/version` |
|15 | Health check fails in Azure | Probe path or auth | Point probe to `/healthz` or `/readyz` as designed; exclude from auth |
|16 | Blob upload failures | SAS expiry; network; ACL | Regenerate SAS; check storage firewall; verify container permissions |
|17 | PAMS / external API timeouts | Circuit open; vendor outage | See disaster recovery graceful degradation; retry after vendor OK |

## Log Aggregation

- **Platform**: Azure Monitor workspace (Log Analytics) — application logs, metrics, and diagnostics from App Service / containers.
- **Format**: **Structured JSON logs** — include `timestamp`, `level`, `message`, `request_id`, `user_id` (when safe), `service`, and `exception` fields where applicable.

### KQL query examples

**Errors in the last hour:**

```kusto
AppTraces
| where TimeGenerated > ago(1h)
| where SeverityLevel >= 3 or Message contains "ERROR"
| project TimeGenerated, Message, Properties
| order by TimeGenerated desc
```

**Filter by request correlation:**

```kusto
AppTraces
| where Properties.request_id == "<paste-request-id>"
| order by TimeGenerated asc
```

Adjust table names (`AppTraces`, `AppExceptions`, custom_CL) to match your workspace schema and diagnostic settings.

## Database Troubleshooting

### Slow queries

- Use PostgreSQL `pg_stat_statements` (if enabled) or Azure Query Store equivalents.
- Capture `EXPLAIN (ANALYZE, BUFFERS)` in a non-prod replica first.
- Add indexes or rewrite queries; avoid full table scans on hot paths.

### Connection pool exhaustion

- Correlate app worker count × pool size with DB `max_connections`.
- Look for connections not returned to the pool (missing context manager, long transactions).
- Temporarily reduce concurrency or scale DB tier only as a stopgap.

### Migration failures

- **Do not** re-run blindly: read the error, check which step applied.
- Restore to a known good state if the DB is inconsistent (PITR per disaster recovery plan).
- Fix forward with a new migration after analysis; test on staging.

## Redis Troubleshooting

### Connection issues

- Test from a jump box or `az redis` connectivity; verify DNS and private endpoint.
- Confirm TLS and password rotation in Key Vault / app settings.

### Memory pressure

- Inspect `used_memory`, eviction counters, and large keys (`MEMORY USAGE` / sampling).
- Shorten TTLs, shard hot keys, or scale the cache SKU.

### Key eviction

- If policy is `allkeys-lru`, expect cold cache after pressure — warm caches or increase memory.
- Ensure session or critical keys use appropriate TTL and fallbacks.

## Frontend Troubleshooting

### Service Worker issues

- Verify SW scope and skipWaiting behavior after deploys.
- Document a “clear site data” path for support; version the SW cache name.

### Cache invalidation

- Use content-hashed asset names; set `Cache-Control` for HTML vs. static assets.
- Purge CDN if fronted by Azure Front Door / CDN.

### CORS errors

- Match `Access-Control-Allow-Origin` to allowed app origins; allow needed methods and headers.
- Ensure credentials mode matches cookie/`Authorization` usage.

## Deployment Troubleshooting

### SHA mismatch

- Compare `/api/v1/meta/version` with the GitHub Actions run artifact and container digest.
- Redeploy the intended image; check slot swap did not leave old code on production.

### Migration errors

- See **Database Troubleshooting** → Migration failures; coordinate with DBA.

### Health check failures

- Confirm probe URL (`/healthz` vs `/readyz`) matches the intent.
- Ensure health endpoints are not behind auth middleware that returns `401` to the probe.
