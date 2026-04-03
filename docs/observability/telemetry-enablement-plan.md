# Telemetry Enablement Plan (D28)

Plan originally tracked re-enabling production telemetry (previously quarantined per [ADR-0008](../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md)). **Production telemetry is enabled as of 2026-04-03** following CORS and configuration verification.

## Current State

- **Production**: Production telemetry enabled as of 2026-04-03. CORS verified: production SWA origin (`purple-water-03205fa03.6.azurestaticapps.net`) is in `cors_origins` list; CSP `connect-src` includes `*.azurewebsites.net`. Frontend `telemetry.ts` default changed from `!IS_PRODUCTION` to `true`.
- **Staging**: Telemetry enabled and operational; CORS issues do not affect staging (same-origin API)
- **Development**: Telemetry enabled with console logging

### Framework Maturity (Independent of Production State)

The telemetry framework is fully implemented and operational in non-production environments:

| Component | Status | Location |
|-----------|--------|----------|
| Frontend telemetry service | Implemented | `frontend/src/services/telemetry.ts` |
| Feature flag gating | Implemented | `telemetry.enabled` flag in DB |
| Backend structured logging | Implemented | `src/infrastructure/middleware/request_logger.py` |
| Correlation ID propagation | Implemented | `X-Request-ID` header chain |
| SLO alerting rules documented | Implemented | `docs/observability/alerting-rules.md` |
| Enablement criteria defined | Implemented | ADR-0008 enablement criteria section |
| Rollout plan documented | Implemented | This document (3-phase plan below) |

The prior blocker (CORS for the production SWA origin and CSP `connect-src` for the API) has been addressed; production telemetry is active.

## CORS Fix Requirements

### Root Cause

The SWA custom domain did not match the CORS `allow_origin_regex` pattern in `src/main.py`. Preflight `OPTIONS` requests failed, causing telemetry `POST` requests to be blocked.

### Fix Steps

| Step | Action | Owner | Status |
|------|--------|-------|--------|
| 1 | Verify SWA custom domain URL matches `allow_origin_regex` | Platform Eng | **Complete** |
| 2 | Update `staticwebapp.config.json` CSP `connect-src` to include API domain | Platform Eng | **Complete** |
| 3 | Test CORS preflight in staging with custom domain | Platform Eng | Pending |
| 4 | Monitor staging telemetry for 2 weeks | Platform Eng | Pending |
| 5 | Enable `TELEMETRY_ENABLED = true` in production config | Platform Eng | **Complete** |

Steps **1** and **2** are satisfied by CORS and CSP configuration; **5** reflects production telemetry being on. Steps **3** and **4** remain on the checklist for extended staging observation where teams still want that gate; production enablement proceeded after direct CORS verification on 2026-04-03.

## Rollout Plan

Production enablement was completed on 2026-04-03 after CORS verification. The phases below describe the original rollout sequence and remain useful for future changes.

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

SLO alerting rules are documented in `docs/observability/alerting-rules.md`. OpenTelemetry-backed alerts remain **Planned** until an OTel dashboard and alert rules are configured.

## Related Documents

- [`docs/adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md`](../adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md) — quarantine decision (amended after production enablement)
- [`docs/slo/performance-slos.md`](../slo/performance-slos.md) — performance SLOs
- [`src/main.py`](../../src/main.py) — CORS configuration
- [`frontend/src/services/telemetry.ts`](../../frontend/src/services/telemetry.ts) — frontend telemetry service
