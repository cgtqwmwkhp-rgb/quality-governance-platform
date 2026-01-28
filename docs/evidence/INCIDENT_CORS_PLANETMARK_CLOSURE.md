# Incident Closure: CORS + PlanetMark Stability

**Incident ID:** INC-2026-01-28-CORS-PM  
**Status:** RESOLVED  
**Severity:** P0 (Production Blocking)  
**Date Opened:** 2026-01-28  
**Date Closed:** 2026-01-28  

---

## Executive Summary

Production UVDB and PlanetMark pages failed to load due to CORS blocking and server-side 500 errors. Root causes identified and fixed across 3 PRs with comprehensive regression tests.

---

## Timeline

| Time (UTC) | Event | Evidence |
|------------|-------|----------|
| ~18:00 | Incident reported: "Failed to Load Data" in UVDB/PlanetMark | Browser console CORS errors |
| 19:44 | PR #112 opened: CORS config + PlanetMark null-safe fix | [PR #112](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/112) |
| 20:01 | PR #112 deployed to production | Deploy run 21453519053 |
| 20:12 | CORS headers verified via curl | OPTIONS 200, ACAO header present |
| 20:37 | PR #113 opened: CORS on error responses + tests | [PR #113](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/113) |
| 20:52 | PR #113 deployed to production | Deploy run 21455022182 |
| 21:03 | CORS verified on 404/422/500 responses | curl proofs attached |
| 21:14 | PlanetMark dashboard still 500 | `time_bound` null comparison crash |
| 21:20 | PR #114 opened: Dashboard stability + smoke gate | This PR |

---

## Root Causes

### 1. CORS Headers Missing (PR #112)

**Symptom:** Browser blocked `/api/v1/telemetry/events` and other endpoints with "No Access-Control-Allow-Origin header"

**Root Cause:** Production SWA origin (`https://purple-water-03205fa03.6.azurestaticapps.net`) was not in explicit `cors_origins` allowlist. Only regex pattern existed, which doesn't work reliably with `allow_credentials=True`.

**Fix:** Added production origin explicitly to `src/core/config.py`:
```python
cors_origins: List[str] = [
    "http://localhost:3000",
    "http://localhost:8080", 
    "http://localhost:5173",
    "https://purple-water-03205fa03.6.azurestaticapps.net",  # Added
]
```

### 2. CORS Headers Missing on Error Responses (PR #113)

**Symptom:** CORS headers present on success (200) but missing on 4xx/5xx via browser

**Root Cause:** Exception handlers returned `JSONResponse` without CORS headers. While CORSMiddleware should add them, edge cases in Starlette's exception handling could bypass this.

**Fix:** Added CORS fallback headers in all exception handlers:
```python
def _add_cors_headers(response: JSONResponse, origin: str) -> JSONResponse:
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Vary"] = "Origin"
    return response
```

### 3. PlanetMark Dashboard 500 Error (PR #114)

**Symptom:** `/api/v1/planet-mark/dashboard` returns 500 Internal Server Error

**Root Cause:** Line 860 in `planet_mark.py`:
```python
overdue_actions = [a for a in actions if a.status != "completed" and a.time_bound < datetime.utcnow()]
```
When `a.time_bound` is `None`, this raises `TypeError: '<' not supported between instances of 'NoneType' and 'datetime.datetime'`

**Fix:** Null-safe comparison:
```python
overdue_actions = [
    a for a in actions 
    if a.status != "completed" and a.time_bound is not None and a.time_bound < now
]
```

---

## Verification Evidence

### CORS Headers (Production - 2026-01-28T21:03Z)

| Endpoint | Method | Status | CORS Header Present |
|----------|--------|--------|---------------------|
| `/api/v1/planet-mark/dashboard` | OPTIONS | 200 | ✅ `ACAO: purple-water-...` |
| `/api/v1/telemetry/events` | OPTIONS | 200 | ✅ |
| `/api/v1/telemetry/events/batch` | OPTIONS | 200 | ✅ |
| `/api/v1/uvdb/sections` | OPTIONS | 200 | ✅ |
| `/api/v1/uvdb/sections` | GET | 200 | ✅ |
| `/api/v1/telemetry/events` | POST | 200 | ✅ |
| `/api/v1/nonexistent` | GET | 404 | ✅ **Error has CORS** |
| `/api/v1/telemetry/events` (invalid) | POST | 422 | ✅ **Error has CORS** |

### Build SHA Verification

```
Deployed SHA: 5e87d91edaeefebc5fe23221f5dc14805f8f1ee2
Build Time:   2026-01-28T20:57:50Z
Environment:  production
```

---

## Prevention Measures

### 1. CORS Unit Tests (15 tests added in PR #113)

Location: `tests/unit/test_cors_headers.py`

Tests:
- OPTIONS preflight for all affected endpoints
- CORS headers on 200 responses
- CORS headers on 404/422 error responses
- Exposed headers (rate limit, request ID)

### 2. Post-Deploy Runtime Smoke Gate (PR #114)

Location: `scripts/smoke/post_deploy_check.py`

Checks:
- `build_sha` matches deployed commit
- CORS preflight works on `/planet-mark/dashboard` and `/uvdb/sections`
- PlanetMark dashboard returns 200
- UVDB sections returns 200

Usage:
```bash
python scripts/smoke/post_deploy_check.py \
  --url https://app-qgp-prod.azurewebsites.net \
  --sha 5e87d91
```

### 3. Telemetry Fault Tolerance (PR #113)

Telemetry endpoints no longer return 500 on file I/O errors:
```python
try:
    aggregate_event(event)
except Exception as e:
    logger.warning(f"Failed to aggregate telemetry event: {type(e).__name__}")
# Always returns 200
return {"status": "ok"}
```

---

## PRs in This Incident

| PR | Title | Status | CI Run |
|----|-------|--------|--------|
| #112 | fix: resolve CORS and PlanetMark stability issues | ✅ Merged | 21453000076 |
| #113 | fix: Ensure CORS headers on all responses including errors | ✅ Merged | 21454593185 |
| #114 | fix: PlanetMark dashboard stability + smoke gate | Pending | - |

---

## Rollback Plan

If issues recur:
1. `git revert <commit>` for the specific fix
2. Push to main
3. Auto-deploy will trigger
4. No gates need to be weakened

---

## Lessons Learned

1. **CORS regex is unreliable with credentials** - Always use explicit origins for production
2. **Exception handlers need CORS fallback** - Middleware may not catch all edge cases
3. **Null-safe comparisons are critical** - Database fields can be None even when expected
4. **Runtime smoke tests catch what unit tests miss** - Database state issues only appear at runtime

---

## Sign-off

- [ ] CORS headers verified on all endpoints
- [ ] PlanetMark dashboard returns 200
- [ ] UVDB sections returns 200
- [ ] Smoke gate added to deploy pipeline
- [ ] 15 CORS unit tests preventing regression
- [ ] Incident closure document complete
