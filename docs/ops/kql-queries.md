# Operational KQL Queries

**Platform:** Quality Governance Platform (QGP)
**Last Updated:** 2026-04-03

Common KQL queries for Azure Application Insights / Log Analytics. Use these in the Azure Portal query editor, Workbooks, or as the basis for scheduled alert rules.

---

## 1. Error Rate by Endpoint

Identify which API endpoints are producing the most failures over the last 24 hours.

```kql
requests
| where timestamp > ago(24h)
| summarize
    total = count(),
    failed = countif(success == false),
    error_pct = round(100.0 * countif(success == false) / count(), 2)
  by name
| where failed > 0
| order by error_pct desc
| take 20
```

---

## 2. Slow Requests (p95 by Endpoint)

Find the slowest endpoints by 95th percentile response time over the last 6 hours.

```kql
requests
| where timestamp > ago(6h)
| summarize
    p50 = percentile(duration, 50),
    p95 = percentile(duration, 95),
    p99 = percentile(duration, 99),
    req_count = count()
  by name
| where req_count > 10
| order by p95 desc
| take 20
```

---

## 3. Authentication Failures

Track failed authentication attempts (401/403 responses) for security monitoring.

```kql
requests
| where timestamp > ago(24h)
| where resultCode in ("401", "403")
| summarize
    failure_count = count(),
    distinct_ips = dcount(client_IP)
  by name, resultCode, bin(timestamp, 1h)
| order by timestamp desc, failure_count desc
```

### 3.1 Brute-Force Detection

Flag IPs with excessive auth failures in a short window.

```kql
requests
| where timestamp > ago(1h)
| where resultCode == "401"
| summarize attempt_count = count() by client_IP
| where attempt_count > 20
| order by attempt_count desc
```

---

## 4. Deployment Verification

Confirm a new deployment is healthy by comparing error rates and latency before and after deployment.

```kql
let deployment_time = datetime(2026-04-03T12:00:00Z);  // replace with actual deployment timestamp
let window = 30m;
requests
| where timestamp between ((deployment_time - window) .. (deployment_time + window))
| summarize
    total = count(),
    failed = countif(success == false),
    error_pct = round(100.0 * countif(success == false) / count(), 2),
    p50 = percentile(duration, 50),
    p95 = percentile(duration, 95)
  by phase = iff(timestamp < deployment_time, "before", "after")
```

### 4.1 New Exception Types Post-Deploy

```kql
let deployment_time = datetime(2026-04-03T12:00:00Z);  // replace with actual
exceptions
| where timestamp > deployment_time
| where timestamp < deployment_time + 2h
| summarize count() by type, outerMessage
| order by count_ desc
| take 20
```

---

## 5. Connection Pool Exhaustion

Detect database connection pool pressure before it causes outages.

```kql
traces
| where timestamp > ago(6h)
| where message has "pool" and (message has "overflow" or message has "exhausted" or message has "timeout")
| summarize count() by bin(timestamp, 5m), message
| order by timestamp desc
```

### 5.1 SQL Dependency Failures

```kql
dependencies
| where timestamp > ago(6h)
| where type == "SQL"
| where success == false
| summarize
    failure_count = count(),
    distinct_targets = dcount(target)
  by bin(timestamp, 5m)
| order by timestamp desc
```

### 5.2 Connection Pool Metrics (Custom)

If custom metrics are emitted for pool stats:

```kql
customMetrics
| where timestamp > ago(6h)
| where name startswith "db.pool"
| summarize avg(value), max(value) by name, bin(timestamp, 5m)
| order by timestamp desc
```

---

## 6. Redis / Idempotency Monitoring

Track Redis availability and fail-open events.

```kql
traces
| where timestamp > ago(24h)
| where message has "Idempotency" and message has "Redis unavailable"
| summarize fail_open_count = count() by bin(timestamp, 5m)
| order by timestamp desc
```

### 6.1 Redis Dependency Health

```kql
dependencies
| where timestamp > ago(6h)
| where type == "Redis" or target has "redis"
| summarize
    total = count(),
    failed = countif(success == false),
    p95_ms = percentile(duration, 95)
  by bin(timestamp, 15m)
| order by timestamp desc
```

---

## 7. Throughput & Traffic Patterns

### 7.1 Requests per Minute (Last 4h)

```kql
requests
| where timestamp > ago(4h)
| summarize rpm = count() by bin(timestamp, 1m)
| render timechart
```

### 7.2 Traffic by Tenant

```kql
requests
| where timestamp > ago(24h)
| extend tenant_id = tostring(customDimensions["tenant_id"])
| summarize request_count = count() by tenant_id
| order by request_count desc
```

---

## 8. Health Check Monitoring

```kql
requests
| where timestamp > ago(1h)
| where name has "healthz" or name has "health"
| summarize
    total = count(),
    failed = countif(success == false),
    avg_duration = avg(duration)
  by bin(timestamp, 5m)
| order by timestamp desc
```

---

## Related Documents

- [`docs/observability/alerting-rules.md`](../observability/alerting-rules.md) — SLO alert rules
- [`docs/observability/dashboards/setup-guide.md`](../observability/dashboards/setup-guide.md) — Application Insights setup
- [`docs/ops/INCIDENT_RESPONSE_RUNBOOK.md`](INCIDENT_RESPONSE_RUNBOOK.md) — incident response procedures
