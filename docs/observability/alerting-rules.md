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

## Planned Alerts (Post-Telemetry Enablement)

Production telemetry is **enabled** as of 2026-04-03 (see [ADR-0008](../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md) and [Telemetry Enablement Plan](telemetry-enablement-plan.md)). The rules below remain **Planned (requires OTel dashboard setup)** until OpenTelemetry metrics are wired to dashboards and alert definitions.

| Alert | Metric Source | Condition | Severity | Action | Status |
|-------|--------------|-----------|----------|--------|--------|
| API CRUD p95 > 200ms | OpenTelemetry `api.response_time_ms` | Sustained 15 min | High | Page on-call | Planned (requires OTel dashboard setup) |
| API CRUD p99 > 500ms | OpenTelemetry `api.response_time_ms` | Sustained 15 min | Critical | Page on-call | Planned (requires OTel dashboard setup) |
| API CRUD p50 > 100ms | OpenTelemetry `api.response_time_ms` | Sustained 1 hour | Warning | Create ticket | Planned (requires OTel dashboard setup) |
| DB indexed p95 > 50ms | OpenTelemetry `db.query_time_ms` | Sustained 15 min | Warning | Investigate | Planned (requires OTel dashboard setup) |
| DB complex p99 > 200ms | OpenTelemetry `db.query_time_ms` | Sustained 15 min | Warning | Investigate | Planned (requires OTel dashboard setup) |
| Error rate > 1% | OpenTelemetry error counter | 5 min window | High | Page on-call | Planned (requires OTel dashboard setup) |
| Throughput drop | OpenTelemetry request counter | < 10 req/s for 10 min (during business hours) | Warning | Investigate | Planned (requires OTel dashboard setup) |

## Alert Routing

| Severity | Channel | SLA |
|----------|---------|-----|
| Critical | Email + PagerDuty (future) | Acknowledge within 15 min |
| High | Email | Acknowledge within 1 hour |
| Warning | Email | Review within 1 business day |

## Implementation Status

Production telemetry is enabled; client and API telemetry traffic are no longer quarantined for CORS reasons (see [ADR-0008](../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md)). OpenTelemetry-based alerts in the table above can be configured as soon as the OTel dashboard and metric-backed alert rules are in place.

## Related Documents

- [`docs/slo/performance-slos.md`](../slo/performance-slos.md) — SLO definitions
- [`docs/observability/telemetry-enablement-plan.md`](telemetry-enablement-plan.md) — enablement plan
- [`docs/adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md`](../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md) — quarantine ADR
