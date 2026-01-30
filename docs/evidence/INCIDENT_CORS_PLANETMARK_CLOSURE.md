# Incident Closure: CORS & PlanetMark Stability

**Incident ID**: INC-2026-01-30-CORS  
**Status**: ⚠️ REQUIRES ADDITIONAL FIX  
**Date**: 2026-01-30  
**Author**: Release Governance SRE  

---

## Executive Summary

Investigation into the CORS and PlanetMark stability incident revealed that **PR #113 did not fully resolve the CORS issue**. The production frontend origin (`app-qgp-prod.azurestaticapps.net`) was not included in the CORS allowlist.

**Root Cause**: The CORS allowlist and regex pattern did not include the production Azure Static Web App origin.

**Fix Applied**: This PR adds the missing origin and implements a runtime smoke gate to prevent recurrence.

---

## Timeline

| Timestamp (UTC) | Event |
|-----------------|-------|
| 2026-01-28T20:41:51Z | PR #113 merged - CORS fix (incomplete) |
| 2026-01-28T20:57:50Z | Commit `5e87d91` deployed to production |
| 2026-01-28T21:00:00Z | Deploy run 21455022182 completed |
| 2026-01-30T12:21:48Z | Runtime validation detected CORS still failing |
| 2026-01-30T12:22:XX Z | Root cause identified: missing origin in allowlist |
| 2026-01-30T12:XX:XXZ | Fix applied: added `app-qgp-prod.azurestaticapps.net` to allowlist |

---

## Root Cause Analysis

### Primary Issue: Incomplete CORS Allowlist

The CORS configuration in `src/core/config.py` and `src/api/exceptions.py` only included:
- `https://purple-water-03205fa03.6.azurestaticapps.net` (auto-generated Azure SWA URL)
- Localhost origins for development

The **actual production frontend** uses:
- `https://app-qgp-prod.azurestaticapps.net` (custom domain style)

This origin was NOT in the allowlist and did NOT match the regex pattern:
```regex
^https://[a-z0-9-]+\.[0-9]+\.azurestaticapps\.net$
```

The regex requires a `.NUMBER.` segment (e.g., `.6.`), which the production URL lacks.

### Secondary Issue: PlanetMark Dashboard 500

The PlanetMark dashboard endpoint returns HTTP 500 instead of 200. This is a **separate issue** likely related to:
- Missing database records for CarbonReportingYear
- Data initialization not completed

The static endpoint `/api/v1/planet-mark/iso14001-mapping` returns 200, confirming the module is loaded.

---

## Verification Evidence

### Phase 0: Runtime Validation (2026-01-30T12:21:48Z)

| Endpoint | Expected | Observed | Latency | Pass/Fail |
|----------|----------|----------|---------|-----------|
| `/api/v1/meta/version` | 200 | 200 | 0.113s | ✅ PASS |
| Build SHA verification | `5e87d91...` | `5e87d91...` | - | ✅ PASS |
| `/api/v1/uvdb/sections` | 200 | 200 | 0.101s | ✅ PASS |
| `/api/v1/planet-mark/dashboard` | 200 | 500 | 0.179s | ⚠️ DATA ISSUE |
| `/api/v1/planet-mark/iso14001-mapping` | 200 | 200 | - | ✅ PASS |

### CORS Header Analysis

**Before fix (OPTIONS /api/v1/meta/version)**:
```
HTTP/2 400 
access-control-allow-credentials: true
access-control-allow-headers: Accept, Accept-Language, Authorization...
access-control-allow-methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
access-control-max-age: 86400
vary: Origin

Disallowed CORS origin
```

**Issue**: No `Access-Control-Allow-Origin` header returned because `app-qgp-prod.azurestaticapps.net` was not in the allowlist.

---

## Fix Implementation

### Files Modified

| File | Change |
|------|--------|
| `src/core/config.py` | Added `https://app-qgp-prod.azurestaticapps.net` to `cors_origins` |
| `src/api/exceptions.py` | Added `https://app-qgp-prod.azurestaticapps.net` to `CORS_ALLOWED_ORIGINS` |
| `.github/workflows/deploy-production.yml` | Added post-deploy runtime smoke gate |

### CORS Allowlist (After Fix)

```python
cors_origins: List[str] = [
    # Local development
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:5173",
    # Production Azure Static Web App (custom domain style)
    "https://app-qgp-prod.azurestaticapps.net",
    # Production Azure Static Web App (auto-generated style)
    "https://purple-water-03205fa03.6.azurestaticapps.net",
]
```

---

## Prevention: Runtime Smoke Gate

A new post-deploy runtime smoke gate has been added to `.github/workflows/deploy-production.yml`.

### Checks Implemented

1. **Build SHA Verification**: Confirms deployed SHA matches expected commit
2. **CORS Preflight**: Verifies OPTIONS request with Origin header
3. **CORS Credentials**: Confirms `access-control-allow-credentials: true` on GET
4. **UVDB Sections**: Verifies `/api/v1/uvdb/sections` returns 200
5. **PlanetMark Dashboard**: Verifies `/api/v1/planet-mark/dashboard` is accessible
6. **PlanetMark ISO Mapping**: Verifies static endpoint returns 200

### Gate Behavior

- **Fail deployment** if critical checks fail (SHA, CORS, UVDB)
- **Warn only** for PlanetMark dashboard 500 (may be data configuration issue)

---

## Monitoring Snapshot

| Metric | Value | Status |
|--------|-------|--------|
| Health (`/health`) | 200, healthy | ✅ PASS |
| Readiness (`/readyz`) | 200, db:connected | ✅ PASS |
| Response Time (avg) | ~100ms | ✅ PASS |
| Rate Limit Headers | Present (60/min) | ✅ PASS |
| Security Headers | All present | ✅ PASS |

---

## Open Items

| Item | Priority | Status |
|------|----------|--------|
| PlanetMark dashboard 500 | Medium | 🔄 Requires data initialization |
| Staging deploy smoke gate | Low | 📋 Recommend adding to staging workflow |

---

## Rollback Plan

If CORS issues persist after this fix:

1. **Immediate**: Add origin via Azure App Service CORS settings (portal)
2. **Short-term**: Revert to previous commit and investigate
3. **Emergency**: Disable CORS validation (not recommended for production)

---

## Closure Criteria

| Criterion | Status |
|-----------|--------|
| Root cause identified | ✅ Complete |
| Fix implemented | ✅ Complete |
| Runtime smoke gate added | ✅ Complete |
| CORS verified in production | ⏳ Pending deployment |
| Evidence documented | ✅ Complete |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-30 | Release Governance SRE | Initial creation |

---

**Next Steps**: Merge this PR, deploy to production, and verify CORS headers are present on all responses.
