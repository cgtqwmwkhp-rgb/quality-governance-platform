# ADR-0009: CSRF Protection Not Required

## Status
Accepted

## Context
The Quality Governance Platform is a single-page application (SPA) that communicates with a FastAPI backend exclusively via JSON API calls. Authentication uses JWT Bearer tokens transmitted in the `Authorization` HTTP header.

## Decision
CSRF protection is not required for this application because:

1. **No cookie-based authentication**: The platform uses JWT Bearer tokens in the Authorization header, not session cookies. Browsers do not automatically attach Authorization headers to cross-origin requests.
2. **SPA architecture**: All API calls originate from JavaScript `fetch()` with explicit headers. There are no HTML form submissions to the API.
3. **CORS policy**: The backend enforces a strict CORS allowlist, rejecting requests from unauthorized origins.
4. **Content-Type enforcement**: The API only accepts `application/json` request bodies, which cannot be sent by simple cross-origin HTML forms.

## Consequences
- No CSRF middleware or token management overhead.
- If cookie-based authentication is added in the future, this decision must be revisited.
- The CORS allowlist must be kept up to date as deployment environments change.
