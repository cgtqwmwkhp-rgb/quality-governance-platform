# ADR-0004: Telemetry CORS Quarantine Policy

## Status
**ACCEPTED** - 2026-01-26

## Context
The frontend telemetry service sends events to `/api/v1/telemetry/events` and `/api/v1/telemetry/events/batch`. In some production scenarios, CORS preflight requests may fail due to:
- Origin mismatch with SWA custom domains
- Network transient failures
- Rate limiting

## Decision
Telemetry is **quarantined in production** and **non-blocking everywhere**:

### 1. Feature Flag (`TELEMETRY_ENABLED`)
- **Default**: Enabled in development/staging, **DISABLED in production**
- **Override**: Set `window.__TELEMETRY_ENABLED__ = true` to enable in any environment
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
- `allow_origin_regex=r"https://.*\.azurestaticapps\.net"` covers Azure SWA
- `cors_origins` includes localhost variants for development

## Policy
1. Telemetry failures MUST NOT block user workflows
2. Telemetry failures MUST NOT spam console with errors
3. Events are dropped after 100 buffer limit to prevent memory issues
4. Production telemetry is disabled until CORS is verified

## Consequences
- Telemetry data may be incomplete in production until CORS is fixed
- No user-facing impact from telemetry failures
- No console spam in any environment
- Operators should monitor Azure Log Analytics for telemetry gaps

## Verification
- `TELEMETRY_ENABLED` is `false` in production by default
- `silentLog()` is a no-op except on localhost
- `sendToBackend()` returns `false` on error, never throws, never logs
- `flushBuffer()` catches all errors, preserves buffer, never logs errors
- `trackExpEvent()` never throws to caller, never spams console

## Testing Proof Plan
1. Open browser DevTools Console on production domain
2. Navigate through all major flows (create investigation, view lists)
3. Filter console for "Telemetry" or "CORS" — should be empty
4. Network tab should show NO telemetry requests when disabled

## Related
- Issue: #TBD - Investigate SWA custom domain CORS
- Timeline: Enable production telemetry after CORS verification
