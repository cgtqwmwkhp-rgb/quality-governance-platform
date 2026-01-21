# DEBUG LOG: Mixed Content API Errors

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
