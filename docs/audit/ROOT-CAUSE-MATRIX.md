# ROOT CAUSE MATRIX

**Date**: 2026-01-22
**Status**: Active Investigation

## Executive Summary

This document captures evidence-led root cause analysis for recurring production issues.

---

## FAILURE CLASS 1: Routing & Trailing Slashes

### Symptom
- `/api/v1/rtas?page=1` → 404
- `/api/v1/rtas/?page=1` → 200/401 (works)

### Root Cause
FastAPI `redirect_slashes=False` (set in `src/main.py:146`) combined with routes defined with trailing slashes (`@router.get("/")` at line 69 in `rtas.py`).

### Evidence
```python
# src/main.py:146
redirect_slashes=False,  # Disabled to prevent HTTP redirects behind HTTPS proxy

# src/api/routes/rtas.py:69
@router.get("/", response_model=RTAListResponse)
```

### Contributing Causes
1. Frontend endpoint strings constructed in multiple places (2 files: `client.ts`, `PortalTrack.tsx`)
2. No centralized endpoint builder to enforce trailing slash policy
3. Historical fix for Mixed Content (307 redirects with HTTP) disabled slash redirects

### Preventative Design
- **Option A**: Centralized endpoint builder in frontend that enforces trailing slash
- **Option B**: Backend routes should NOT use trailing slash (more RESTful)
- **Option C**: Re-enable redirect_slashes but configure uvicorn with `--proxy-headers`

### Recommended Fix
Option A + Option C: Re-enable redirect_slashes with proper proxy-headers, AND centralize frontend endpoints.

---

## FAILURE CLASS 2: Authentication Model Mismatch

### Symptom
- Portal users get 401 on all API calls
- Azure AD tokens rejected by backend

### Root Cause
Portal authenticates via Azure AD (MSAL), producing Microsoft-signed ID tokens.
Backend `decode_token()` uses `settings.jwt_secret_key` (platform secret), cannot validate Azure AD tokens.

### Evidence
```python
# src/core/security.py:76-79
payload = jwt.decode(
    token,
    settings.jwt_secret_key,  # Platform secret, NOT Azure AD JWKS
    algorithms=[settings.jwt_algorithm],
)

# frontend/src/contexts/PortalAuthContext.tsx:114
localStorage.setItem('portal_id_token', idToken);  # Azure AD ID token

# frontend/src/pages/PortalTrack.tsx:264-266
const portalToken = localStorage.getItem('portal_id_token');
const adminToken = localStorage.getItem('access_token');
const token = portalToken || adminToken;  # Sends Azure AD token to backend
```

### Threat Model
| Attack Vector | Risk | Mitigation |
|---------------|------|------------|
| Unauthenticated access to filtered data | LOW | Filters by email; no cross-user data |
| Email spoofing in query param | MEDIUM | Email not verified; attacker could query other users |
| Rate limiting bypass | LOW | Rate limiter still active |

### Fix Options
| Option | Complexity | Security | Description |
|--------|------------|----------|-------------|
| A: JWKS validation | HIGH | BEST | Backend fetches Azure AD public keys, validates tokens |
| B: Token exchange | MEDIUM | GOOD | Portal exchanges Azure AD token for platform JWT |
| C: Restricted unauthenticated | LOW | ACCEPTABLE | Allow filtered reads without auth (current approach) |

### Recommended Fix
Short-term: Option C with enhanced security (rate limiting, audit logging, IP tracking)
Long-term: Option B (token exchange endpoint)

---

## FAILURE CLASS 3: Schema/Migration Drift

### Symptom
- 500 Internal Server Error when using `reporter_email` filter
- Column `reporter_email` referenced in code but may not exist in production DB

### Root Cause
Migration `add_reporter_email_01` exists but may not have been applied due to:
1. Container quota exceeded during migration run (see deploy-production.yml:185-188)
2. Silent failure path: "WARNING: Container quota exceeded - migrations skipped"

### Evidence
```yaml
# .github/workflows/deploy-production.yml:185-188
echo "⚠️ WARNING: Container quota exceeded - migrations skipped"
echo "The app is deployed but migrations may need manual execution"
echo "migration_status=quota_exceeded" >> $GITHUB_OUTPUT
exit 0  # DOES NOT FAIL THE DEPLOY!
```

```python
# src/domain/models/incident.py:89
reporter_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

# alembic/versions/20260121_add_reporter_email_fields.py
op.add_column('incidents', sa.Column('reporter_email', sa.String(255), nullable=True))
```

### Preventative Design
1. Deploy MUST fail if migrations cannot run
2. Health endpoint should expose migration state
3. Startup check should verify expected schema version
4. Remove silent "quota_exceeded" exit path

---

## FAILURE CLASS 4: Type Safety (Optional Parameters)

### Symptom
- Runtime error from `reporter_email: str = Query(None)` (should be `Optional[str]`)

### Root Cause
Type annotation mismatch: default value `None` with type `str` instead of `Optional[str]`.

### Evidence
```python
# src/api/routes/incidents.py (before fix)
reporter_email: str = Query(None, description="Filter by reporter email"),

# Should be:
reporter_email: Optional[str] = Query(None, description="Filter by reporter email"),
```

### Preventative Design
1. Enable mypy/pyright strict mode
2. Add CI check for type consistency
3. Use FastAPI's recommended patterns for optional query params

---

## FAILURE CLASS 5: CI/Deploy Reliability

### Symptom
- OpenAPI fetch timeout (exit code 28)
- Security scan failures (permission issues)

### Evidence
```
# OpenAPI timeout (from staging smoke tests)
Test 4: OpenAPI specification
##[error]Process completed with exit code 28.

# Security scan failure
##[error]Resource not accessible by integration - https://docs.github.com/rest
##[warning]This run of the CodeQL Action does not have permission to access the CodeQL Action API endpoints.
```

### Root Causes
1. OpenAPI: Service not ready when smoke test runs; no readiness gate
2. Security: Missing `security-events: read` permission in workflow

### Preventative Design
1. Add readiness check with exponential backoff before smoke tests
2. Add proper permissions to security workflow
3. Increase timeout only after readiness confirmed

---

---

## FAILURE CLASS 6: Duplicate Model Class Names

### Symptom
- 500 Internal Server Error on any database query
- Error: `InvalidRequestError: Multiple classes found for path "DocumentVersion"`

### Root Cause
Two model classes with the same name `DocumentVersion`:
- `document_control.py:143` → table `controlled_document_versions`
- `document.py:281` → table `document_versions`

SQLAlchemy cannot resolve which class to use.

### Evidence
```python
# src/domain/models/document_control.py:143
class DocumentVersion(Base):  # DUPLICATE NAME!
    __tablename__ = "controlled_document_versions"

# src/domain/models/document.py:281
class DocumentVersion(Base, TimestampMixin):
    __tablename__ = "document_versions"
```

### Fix Applied
Renamed `document_control.py:DocumentVersion` → `ControlledDocumentVersion`

---

## VARIANCE MATRIX: Single Points of Failure

| Component | Count | Locations | Issue |
|-----------|-------|-----------|-------|
| API Base URL | 3 | `apiBase.ts`, `client.ts`, `PortalTrack.tsx` | Multiple sources of truth |
| Endpoint strings | 48+ | `client.ts` (26), `PortalTrack.tsx` (7), others | No centralized builder |
| Auth header creation | 2 | `client.ts` interceptor, `PortalTrack.tsx` manual | Duplicate logic |
| Current user dependency | 2 | `CurrentUser`, `OptionalCurrentUser` | Split by design (OK) |
| Error response shape | Variable | Each route handles differently | No contract |

---

## REMEDIATION PRIORITY

| Priority | Issue | Impact | Effort | Owner |
|----------|-------|--------|--------|-------|
| P0 | Migration not running | Portal broken | LOW | DevOps |
| P1 | Auth model mismatch | Portal 401s | MEDIUM | Backend |
| P1 | Endpoint trailing slashes | Portal 404s | LOW | Frontend |
| P2 | Type safety | Runtime errors | LOW | Backend |
| P2 | CI reliability | Flaky deploys | MEDIUM | DevOps |
| P3 | Frontend consolidation | Maintenance | MEDIUM | Frontend |
