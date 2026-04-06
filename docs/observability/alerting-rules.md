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

## OTel-Based Alerts (Active)

Production telemetry is **enabled** as of 2026-04-03 (see [ADR-0008](../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md) and [Telemetry Enablement Plan](telemetry-enablement-plan.md)). The following alerts are now **Active** and configured via Azure Monitor alert rules backed by OpenTelemetry metrics.

| Alert | Metric Source | Condition | Severity | Action | Status |
|-------|--------------|-----------|----------|--------|--------|
| API CRUD p95 > 200ms | OpenTelemetry `api.response_time_ms` | p95 > 200ms sustained 15 min | High | Page on-call | **Active** |
| API CRUD p99 > 500ms | OpenTelemetry `api.response_time_ms` | p99 > 500ms sustained 15 min | Critical | Page on-call | **Active** |
| API CRUD p50 > 100ms | OpenTelemetry `api.response_time_ms` | p50 > 100ms sustained 1 hour | Warning | Create ticket | **Active** |
| DB indexed p95 > 50ms | OpenTelemetry `db.query_time_ms` | p95 > 50ms sustained 15 min | Warning | Investigate | **Active** |
| DB complex p99 > 200ms | OpenTelemetry `db.query_time_ms` | p99 > 200ms sustained 15 min | Warning | Investigate | **Active** |
| Error rate > 1% | OpenTelemetry error counter | > 1% errors in 5 min window | High | Page on-call | **Active** |
| Throughput drop | OpenTelemetry request counter | < 10 req/s for 10 min (during business hours) | Warning | Investigate | **Active** |

## Alert Routing

| Severity | Channel | SLA |
|----------|---------|-----|
| Critical | Email + PagerDuty (future) | Acknowledge within 15 min |
| High | Email | Acknowledge within 1 hour |
| Warning | Email | Review within 1 business day |

## Implementation Status

Production telemetry is enabled; client and API telemetry traffic are no longer quarantined for CORS reasons (see [ADR-0008](../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md)). All OTel-based alerts are now **Active** and configured via Azure Monitor alert rules.

## Alerting-as-Code

All alert rules above are codified as an Azure ARM template at [`scripts/infra/alert-rules.json`](../../scripts/infra/alert-rules.json). Deploy with:

```bash
az deployment group create \
  --resource-group <rg> \
  --template-file scripts/infra/alert-rules.json \
  --parameters appInsightsResourceId=<id> appServiceResourceId=<id> actionGroupId=<id>
```

## Related Documents

- [`scripts/infra/alert-rules.json`](../../scripts/infra/alert-rules.json) — ARM template (alerting-as-code)
- [`docs/slo/performance-slos.md`](../slo/performance-slos.md) — SLO definitions
- [`docs/observability/telemetry-enablement-plan.md`](telemetry-enablement-plan.md) — enablement plan
- [`docs/adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md`](../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md) — quarantine ADR
