# Telemetry Enablement Plan (D28)

Plan to re-enable production telemetry, currently quarantined per [ADR-0008](../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md).

## Current State

- **Production**: Telemetry disabled (`TELEMETRY_ENABLED = false`)
- **Staging**: Telemetry enabled, monitoring for CORS issues
- **Development**: Telemetry enabled with console logging

## CORS Fix Requirements

### Root Cause

The SWA custom domain does not match the CORS `allow_origin_regex` pattern in `src/main.py`. Preflight `OPTIONS` requests fail, causing telemetry `POST` requests to be blocked.

### Fix Steps

| Step | Action | Owner | Status |
|------|--------|-------|--------|
| 1 | Verify SWA custom domain URL matches `allow_origin_regex` | Platform Eng | Pending |
| 2 | Update `staticwebapp.config.json` CSP `connect-src` to include API domain | Platform Eng | Pending |
| 3 | Test CORS preflight in staging with custom domain | Platform Eng | Pending |
| 4 | Monitor staging telemetry for 2 weeks | Platform Eng | Pending |
| 5 | Enable `TELEMETRY_ENABLED = true` in production config | Platform Eng | Pending |

## Rollout Plan

### Phase 1: Staging Verification (Week 1-2)

1. Deploy CORS fix to staging.
2. Enable telemetry in staging with custom domain.
3. Monitor for 2 weeks:
   - No CORS errors in browser console
   - Telemetry events arriving in backend logs
   - No user-facing impact

### Phase 2: Production Canary (Week 3)

1. Enable telemetry for 10% of production sessions via feature flag.
2. Monitor for 1 week:
   - Error rate in telemetry endpoint < 0.1%
   - No increase in user-reported issues
   - Telemetry data completeness > 95%

### Phase 3: Full Production Enable (Week 4)

1. Enable telemetry for all production sessions.
2. Remove quarantine flag from ADR-0008.
3. Update monitoring dashboards.

## SLO Alerting Implementation

### Current Alerting

| Alert | Source | Status |
|-------|--------|--------|
| Budget alerts (cost) | Azure Cost Management | Active |
| Health check failures | Azure App Service | Active |
| Database connection errors | Application logs | Active |

### Planned Alerting

| Alert | Source | Threshold | Status |
|-------|--------|-----------|--------|
| API p95 > 200ms sustained | OpenTelemetry metrics | 15 min window | Planned |
| API p99 > 500ms sustained | OpenTelemetry metrics | 15 min window | Planned |
| Error rate > 1% | OpenTelemetry metrics | 5 min window | Planned |
| Telemetry event drop rate > 5% | Backend logs | 1 hour window | Planned |

### Alerting Documentation

SLO alerting rules will be documented in `docs/observability/alerting-rules.md` once telemetry is re-enabled and OpenTelemetry metrics are flowing.

## Related Documents

- [`docs/adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md`](../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md) — quarantine decision
- [`docs/slo/performance-slos.md`](../slo/performance-slos.md) — performance SLOs
- [`src/main.py`](../../src/main.py) — CORS configuration
- [`frontend/src/services/telemetry.ts`](../../frontend/src/services/telemetry.ts) — frontend telemetry service
