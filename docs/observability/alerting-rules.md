# SLO Alerting Rules (D28)

Alerting configuration for Service Level Objectives. Rules align with targets in `docs/slo/performance-slos.md`.

## Active Alerts

| Alert | Source | Condition | Severity | Notification |
|-------|--------|-----------|----------|--------------|
| Health check failure | Azure App Service | `/healthz` returns non-200 | Critical | Azure Alert → email |
| Database connection exhaustion | Application logs | Pool connections > 80% | High | Log alert |
| Monthly budget > 80% | Azure Cost Management | Spend > £144 | Warning | Email |
| Monthly budget > 100% | Azure Cost Management | Spend > £180 | Critical | Email |

## Planned Alerts (Post-Telemetry Enablement)

| Alert | Metric Source | Condition | Severity | Action |
|-------|--------------|-----------|----------|--------|
| API CRUD p95 > 200ms | OpenTelemetry `api.response_time_ms` | Sustained 15 min | High | Page on-call |
| API CRUD p99 > 500ms | OpenTelemetry `api.response_time_ms` | Sustained 15 min | Critical | Page on-call |
| API CRUD p50 > 100ms | OpenTelemetry `api.response_time_ms` | Sustained 1 hour | Warning | Create ticket |
| DB indexed p95 > 50ms | OpenTelemetry `db.query_time_ms` | Sustained 15 min | Warning | Investigate |
| DB complex p99 > 200ms | OpenTelemetry `db.query_time_ms` | Sustained 15 min | Warning | Investigate |
| Error rate > 1% | OpenTelemetry error counter | 5 min window | High | Page on-call |
| Throughput drop | OpenTelemetry request counter | < 10 req/s for 10 min (during business hours) | Warning | Investigate |

## Alert Routing

| Severity | Channel | SLA |
|----------|---------|-----|
| Critical | Email + PagerDuty (future) | Acknowledge within 15 min |
| High | Email | Acknowledge within 1 hour |
| Warning | Email | Review within 1 business day |

## Implementation Status

Telemetry is currently quarantined in production (see [ADR-0008](../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md)). Planned alerts will be activated once telemetry is re-enabled per the [Telemetry Enablement Plan](telemetry-enablement-plan.md).

## Related Documents

- [`docs/slo/performance-slos.md`](../slo/performance-slos.md) — SLO definitions
- [`docs/observability/telemetry-enablement-plan.md`](telemetry-enablement-plan.md) — enablement plan
- [`docs/adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md`](../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md) — quarantine ADR
