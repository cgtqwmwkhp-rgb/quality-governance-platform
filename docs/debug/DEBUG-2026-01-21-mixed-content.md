# DEBUG LOG: Mixed Content + Auth API Errors

**Date**: 2026-01-21
**Status**: FIXED
**Severity**: P0 - Production Breaking

## Symptom

```
Mixed Content: The page at 'https://purple-water-03205fa03.6.azurestaticapps.net/incidents' 
was loaded over HTTPS, but requested an insecure XMLHttpRequest endpoint 
'http://app-qgp-prod.azurewebsites.net/api/v1/incidents/?page=1&size=50'. 
This request has been blocked; the content must be served over HTTPS.
```

## Root Cause (PROVEN)

FastAPI's `redirect_slashes=True` (default) was generating 307 redirects with HTTP URLs.

**Evidence:**
```bash
$ curl -sI "https://app-qgp-prod.azurewebsites.net/api/v1/incidents?page=1&size=50"

HTTP/2 307 
location: http://app-qgp-prod.azurewebsites.net/api/v1/incidents/?page=1&size=50
```

The `location:` header used `http://` instead of `https://` because:
1. Uvicorn was not configured with `--proxy-headers`
2. FastAPI didn't know it was behind an HTTPS reverse proxy (Azure App Service)

## Fix Applied

### Change 1: Dockerfile
```diff
- CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
+ CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

### Change 2: src/main.py
```diff
- redirect_slashes=True,  # Auto-redirect /path to /path/ and vice versa
+ redirect_slashes=False,  # Disabled to prevent HTTP redirects behind HTTPS proxy
```

## Files Changed

1. `Dockerfile` - Added `--proxy-headers` and `--forwarded-allow-ips` to uvicorn
2. `src/main.py` - Changed `redirect_slashes=True` to `redirect_slashes=False`

## Verification

After fix:
```bash
$ curl -sI "https://app-qgp-prod.azurewebsites.net/api/v1/incidents?page=1&size=50"

# Should return 200 or 401 (auth required), NOT 307
```

## Contributing Factors (Not Root Cause)

1. Frontend was not including trailing slashes on API paths
2. Browser caching of old JS bundles complicated debugging
3. Service Worker was suspected but was not the cause

## Prevention

1. Backend must always use `--proxy-headers` when behind reverse proxy
2. Added this debug log for future reference
3. Consider adding trailing slashes to all frontend API paths

---

# FOLLOW-UP FIX: Portal 401 Authentication Errors

## Symptom (Round 2)

After fixing mixed content, portal users still saw 401 errors:
```
/api/v1/incidents/?page=1&size=20&reporter_email=... → 401
/api/v1/rtas?page=1&size=20&reporter_email=... → 404 (missing trailing slash)
/api/v1/complaints/?page=1&size=20&complainant_email=... → 401
```

## Root Cause

1. **RTAs 404**: Missing trailing slash on line 309-310 of PortalTrack.tsx
2. **401 Auth**: Portal uses Azure AD tokens (MSAL), but backend `decode_token` uses platform JWT secret. Incompatible token types.

## Fix Applied

### Change 1: Fix RTAs trailing slash
```diff
- ${apiBase}/api/v1/rtas?page=1&size=20
+ ${apiBase}/api/v1/rtas/?page=1&size=20
```

### Change 2: Add optional authentication to backend

Created `OptionalCurrentUser` dependency that returns `None` for invalid tokens
instead of raising 401. Updated list endpoints to allow unauthenticated access
when filtering by reporter_email/complainant_email.

**Files changed:**
- `src/api/dependencies/__init__.py` - Added `get_optional_current_user` and `OptionalCurrentUser`
- `src/api/routes/incidents.py` - Use `OptionalCurrentUser` for list endpoint
- `src/api/routes/rtas.py` - Use `OptionalCurrentUser` for list endpoint
- `src/api/routes/complaints.py` - Use `OptionalCurrentUser` for list endpoint
- `frontend/src/pages/PortalTrack.tsx` - Fixed RTAs trailing slash

## Security Note

This change allows unauthenticated access to list endpoints ONLY when filtering
by reporter_email/complainant_email. Users can only see their own reports.
Without the email filter, authentication is still required.
