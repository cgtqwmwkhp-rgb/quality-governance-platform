# ADR-0008: Telemetry CORS Quarantine Policy

## Status
**ACCEPTED** - 2026-01-26

## Context
The frontend telemetry service sends events to `/api/v1/telemetry/events` and `/api/v1/telemetry/events/batch`. In some production scenarios, CORS preflight requests may fail due to:
- Origin mismatch with SWA custom domains
- Network transient failures
- Rate limiting

## Decision
Telemetry is **non-blocking everywhere**. Production was **quarantined** (no API sends) until CORS was verified; **as of 2026-04-03** production sends are enabled (see Enablement Criteria note).

### 1. Feature Flag (`TELEMETRY_ENABLED`)
- **Default**: Without a `window` override, API calls are **enabled** in all environments (including production after CORS verification 2026-04-03; previously production defaulted off via `!IS_PRODUCTION`)
- **Override**: Set `window.__TELEMETRY_ENABLED__` to `true` or `false` to force on or off
- **Effect**: When disabled, no API calls are made; events still buffer locally

### 2. Silent Logging (No Console Spam)
- `console.log` for telemetry events **ONLY in development** (localhost)
- **NEVER** `console.error` on failure — all errors caught silently
- Staging and production have zero console output from telemetry

### 3. Frontend Resilience (`frontend/src/services/telemetry.ts`)
- All API calls wrapped in try/catch
- Events buffered to localStorage first
- Buffer bounded to 100 events max
- Flush retries on page visibility change

### 4. CORS Configuration (`src/main.py`)
- `allow_origin_regex=r"^https://[a-z0-9-]+\.[0-9]+\.azurestaticapps\.net$"` covers Azure SWA default hostnames
- `cors_origins` includes localhost variants for development and explicit production SWA origins as required

## Policy
1. Telemetry failures MUST NOT block user workflows
2. Telemetry failures MUST NOT spam console with errors
3. Events are dropped after 100 buffer limit to prevent memory issues
4. Production telemetry required CORS verification before full enablement (verified 2026-04-03; see enablement criteria note below)

## Consequences
- Telemetry data may have been incomplete in production before CORS was verified (2026-04-03)
- No user-facing impact from telemetry failures
- No console spam in any environment
- Operators should monitor Azure Log Analytics for telemetry gaps

## Verification
- `TELEMETRY_ENABLED` follows `frontend/src/services/telemetry.ts` (explicit `window` override or default enabled when not overridden)
- `silentLog()` is a no-op except on localhost
- `sendToBackend()` returns `false` on error, never throws, never logs
- `flushBuffer()` catches all errors, preserves buffer, never logs errors
- `trackExpEvent()` never throws to caller, never spams console

## Testing Proof Plan
1. Open browser DevTools Console on production domain
2. Navigate through all major flows (create investigation, view lists)
3. Filter console for "Telemetry" or "CORS" — should be empty
4. Network tab should show successful telemetry `POST` requests when enabled, without CORS failures

## Enablement Criteria

Production telemetry will be re-enabled when all of the following are met:

| # | Criterion | Status |
|---|-----------|--------|
| 1 | SWA custom domain CORS verified end-to-end | **Complete** |
| 2 | `staticwebapp.config.json` CSP allows telemetry endpoint | **Complete** |
| 3 | Staging telemetry has run for >= 2 weeks without errors | **Superseded** |
| 4 | SLO alerting rules documented in `docs/observability/alerting-rules.md` | **Superseded** |
| 5 | Telemetry enablement plan reviewed and approved | **Superseded** |

> **Superseded:** Production telemetry enabled via operational decision 2026-04-03. Staging observation conducted during March 2026 deployment cycle.

**Note:** As of 2026-04-03, production telemetry has been enabled following CORS verification.

**Target**: Re-enable production telemetry by end of Q2 2026.

See `docs/observability/telemetry-enablement-plan.md` for the detailed rollout plan.

## Related
- Issue: #TBD - Investigate SWA custom domain CORS
- Timeline: Enable production telemetry after CORS verification (target: Q2 2026)
