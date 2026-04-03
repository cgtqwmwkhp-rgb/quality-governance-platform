# SLO Alerting Rules (D28)

Alerting configuration for Service Level Objectives. Rules align with targets in `docs/slo/performance-slos.md`.

## Active Alerts (Currently Enforced)

These alerts are operational and firing in production:

| Alert | Source | Condition | Severity | Notification | Status |
|-------|--------|-----------|----------|--------------|--------|
| Health check failure | Azure App Service | `/healthz` returns non-200 | Critical | Azure Alert → email | **Active** |
| Database connection exhaustion | Application logs | Pool connections > 80% | High | Log alert | **Active** |
| Monthly budget > 80% | Azure Cost Management | Spend > £144 | Warning | Email | **Active** |
| Monthly budget > 100% | Azure Cost Management | Spend > £180 | Critical | Email | **Active** |
| CI quality gate failure | GitHub Actions | `all-checks` job fails | High | GitHub notification | **Active** |
| Lockfile drift | CI `lockfile-check` | Lockfile stale | Medium | CI failure | **Active** |

## Ready to Activate Alerts (Post-Telemetry Enablement)

Production telemetry is **enabled** as of 2026-04-03 (see [ADR-0008](../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md) and [Telemetry Enablement Plan](telemetry-enablement-plan.md)). The rules below are **Ready to Activate** — KQL queries are defined and can be wired to Azure Monitor alert rules. See `docs/observability/dashboards/setup-guide.md` for configuration steps.

| Alert | Metric Source | Condition | Severity | Action | Status | KQL Snippet |
|-------|--------------|-----------|----------|--------|--------|-------------|
| API CRUD p95 > 200ms | Application Insights `requests` | Sustained 15 min | High | Page on-call | **Ready to Activate** | `requests \| summarize percentile(duration, 95) by bin(timestamp, 15m) \| where percentile_duration_95 > 200` |
| API CRUD p99 > 500ms | Application Insights `requests` | Sustained 15 min | Critical | Page on-call | **Ready to Activate** | `requests \| summarize percentile(duration, 99) by bin(timestamp, 15m) \| where percentile_duration_99 > 500` |
| API CRUD p50 > 100ms | Application Insights `requests` | Sustained 1 hour | Warning | Create ticket | **Ready to Activate** | `requests \| summarize percentile(duration, 50) by bin(timestamp, 1h) \| where percentile_duration_50 > 100` |
| DB indexed p95 > 50ms | Application Insights `dependencies` | Sustained 15 min | Warning | Investigate | **Ready to Activate** | `dependencies \| where type == "SQL" \| summarize percentile(duration, 95) by bin(timestamp, 15m) \| where percentile_duration_95 > 50` |
| DB complex p99 > 200ms | Application Insights `dependencies` | Sustained 15 min | Warning | Investigate | **Ready to Activate** | `dependencies \| where type == "SQL" \| summarize percentile(duration, 99) by bin(timestamp, 15m) \| where percentile_duration_99 > 200` |
| Error rate > 1% | Application Insights `requests` | 5 min window | High | Page on-call | **Ready to Activate** | `requests \| summarize total=count(), failed=countif(success == false) by bin(timestamp, 5m) \| extend error_pct=100.0*failed/total \| where error_pct > 1` |
| Throughput drop | Application Insights `requests` | < 10 req/s for 10 min (during business hours) | Warning | Investigate | **Ready to Activate** | `requests \| summarize req_count=count() by bin(timestamp, 10m) \| where req_count < 6000 and hourofday(timestamp) between (8 .. 18)` |

## Alert Routing

| Severity | Channel | SLA |
|----------|---------|-----|
| Critical | Email + PagerDuty (future) | Acknowledge within 15 min |
| High | Email | Acknowledge within 1 hour |
| Warning | Email | Review within 1 business day |

## Implementation Status

Production telemetry is enabled; client and API telemetry traffic are no longer quarantined for CORS reasons (see [ADR-0008](../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md)). OpenTelemetry-based alerts in the table above are **Ready to Activate** and can be configured via Azure Monitor scheduled query rules using the KQL snippets provided.

## Related Documents

- [`docs/slo/performance-slos.md`](../slo/performance-slos.md) — SLO definitions
- [`docs/observability/telemetry-enablement-plan.md`](telemetry-enablement-plan.md) — enablement plan
- [`docs/observability/dashboards/setup-guide.md`](dashboards/setup-guide.md) — Application Insights setup guide
- [`docs/adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md`](../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md) — quarantine ADR
