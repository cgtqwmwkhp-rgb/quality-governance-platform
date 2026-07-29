# Security Baseline — QGP

**Platform:** Quality Governance Platform (QGP)  
**Version:** 1.0  
**Related code:** `src/main.py`, `src/core/security.py`, `src/core/azure_auth.py`, `src/domain/authz/` (permission catalogue, route census), `src/api/dependencies/__init__.py` (`require_permission`), `.github/workflows/ci.yml`, `.github/dependabot.yml`

---

## 1. OWASP Top 10 (2021) mapping

| OWASP category | Risk | Control in QGP |
| --- | --- | --- |
| **A01 Broken Access Control** | IDOR, privilege escalation | **Enforced:** JWT authentication; roles (`src/domain/models/user.py`, table `roles`) carrying permission tokens from the catalogue in `src/domain/authz/catalogue.py`; per-endpoint checks via `require_permission` (`src/api/dependencies/__init__.py`); rate limiting. Measured by `src/domain/authz/census.py` over the mounted app: **464 of 988 endpoints are authorisation-checked** (435 by permission token, 29 by superuser flag), including **413 of 500 writes**. A new route that is neither checked nor declared fails CI (`tests/integration/test_route_authorisation_census.py`). **Partial — authorisation coverage:** the other **474 endpoints (74 of them writes)** authenticate the caller and then run no authorisation check, so nothing refuses the request before the handler. Recorded route by route as `AUTHENTICATED_ONLY_DEBT` in `src/domain/authz/route_declarations.py` (defect C-2, open). **Not effective — RLS tenant scoping:** services filter on `tenant_id`, and 21 tables carry a `tenant_isolation` row-level-security policy, but the application connects as a role holding `rolbypassrls`, so PostgreSQL never evaluates those policies (defect C-27, open — `docs/governance/rls-least-privilege-rollout.md`). **Not implemented:** ABAC, field-level permissions, permission-denial auditing — see §5. |
| **A02 Cryptographic Failures** | Weak crypto, exposed secrets | bcrypt password hashing; JWT signed with configured secret; TLS in transit; production fail-fast for weak secrets (`src/core/config.py`); Azure platform encryption at rest |
| **A03 Injection** | SQL/command injection | SQLAlchemy ORM parameterisation; input validation via Pydantic; `nh3` / sanitisation where used for HTML |
| **A04 Insecure Design** | Missing threat modelling | Security headers middleware, idempotency for safe retries, UAT read-only mode, structured logging without secrets |
| **A05 Security Misconfiguration** | Verbose errors, default creds | Exception handlers, env-based settings, CORS allowlist + staging regex, production DB URL validation |
| **A06 Vulnerable Components** | CVEs in dependencies | **pip-audit** (strict), **npm audit** (high gate), **Dependabot** weekly PRs, lockfile checks |
| **A07 Identification and Authentication Failures** | Weak auth | Email/password + lockout (`AuthService`), **Azure AD** ID token validation for portal, JWT access + refresh tokens |
| **A08 Software and Data Integrity Failures** | Supply chain | Lockfile + hash verification, Gitleaks, Trojan-source scan in CI, SBOM job (CycloneDX) |
| **A09 Security Logging and Monitoring Failures** | No audit trail | JSON logging, request logger middleware, immutable **audit log** model with hash chain, Azure Monitor hooks |
| **A10 Server-Side Request Forgery** | SSRF | Controlled outbound HTTP (httpx) with allowlisted use cases; review new integrations in threat modelling |

---

## 2. Content-Security-Policy (CSP)

**Source of truth:** `SecurityHeadersMiddleware` in `src/main.py`.

**Current `Content-Security-Policy` header value:**

```
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline';
img-src 'self' data: blob:;
font-src 'self';
connect-src 'self';
frame-ancestors 'none';
base-uri 'self';
form-action 'self'
```

**Other headers set in the same middleware:** `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Strict-Transport-Security`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`. API responses under `/api/` receive `Cache-Control: no-store`.

---

## 3. Dependency and secret security in CI

Configured in **`.github/workflows/ci.yml`** (job `security-scan`, `frontend-tests`, `secret-scanning`) and **`.github/dependabot.yml`**.

| Tool | Scope | CI behaviour |
| --- | --- | --- |
| **Bandit** | Python (`src/`) | **Blocking** on high severity (`-ll`) |
| **pip-audit** | Python dependencies | **`--strict`**, blocking |
| **Safety** | Python environment | **Advisory** (non-blocking; reports full output) |
| **Gitleaks** | Git history | Secret scanning on push/PR workflow |
| **npm audit** | Frontend | **`--omit=dev --audit-level=high`**, blocking |
| **Dependabot** | pip, npm, GitHub Actions | Weekly update PRs |

Additional related gates: **dependency-review** (PRs, high severity), **lockfile freshness** (`requirements.lock`), **SBOM** generation job.

---

## 4. Authentication security

| Mechanism | Implementation |
| --- | --- |
| **Azure AD** | `src/core/azure_auth.py`, token validation used by `AuthService` for portal / federated flows |
| **JWT** | Access + refresh tokens in `src/core/security.py`; expiry from settings (`jwt_access_token_expire_minutes`, `jwt_refresh_token_expire_days`) |
| **Password hashing** | **bcrypt** via Passlib (`CryptContext`) in `src/core/security.py` |
| **Brute-force mitigation** | Failed-attempt tracking and temporary lockout in `src/domain/services/auth_service.py` |
| **Token hygiene** | Blacklist / cleanup tasks (`cleanup_expired_tokens` in `src/infrastructure/tasks/cleanup_tasks.py`) |

---

## 5. Authorization model

| Layer | Status | Description | Code |
| --- | --- | --- | --- |
| **Authentication** | Enforced | Bearer JWT decoded per request; revoked access tokens rejected; inactive users rejected | `get_current_user` in `src/api/dependencies/__init__.py`, `src/core/security.py` |
| **RBAC — roles and permission tokens** | Enforced | A user's roles are joined through `user_roles`; each role row stores a JSON list of permission tokens in `roles.permissions`; `User.has_permission` does **exact set membership** — no globbing, inheritance or wildcard expansion | `src/domain/models/user.py` (`Role`, `User`, `user_roles`) |
| **Permission vocabulary** | Enforced | The tokens that exist, which are enforced, and which may be granted; write-time validation keeps `roles.permissions` inside the catalogue | `src/domain/authz/catalogue.py`, `src/domain/authz/validation.py` |
| **RBAC — endpoint checks** | **Partial** | `require_permission("<token>")` returns 403 when the token is absent from the caller's roles. In force on 435 endpoints; a further 29 are gated on the superuser flag (`CurrentSuperuser`). The remaining **474 of 988** endpoints (**74 of 500 writes**) authenticate and then check nothing — defect C-2, open. Some of those enforce ownership inside the handler, so the accurate statement is that no authorisation check runs *before* the handler, not that every one is exploitable | `require_permission` in `src/api/dependencies/__init__.py`; measurement in `src/domain/authz/census.py`; per-route register in `src/domain/authz/route_declarations.py` |
| **Coverage gate** | Enforced | Every endpoint must be either authorisation-checked or named in `PUBLIC_BY_DESIGN` / `AUTHENTICATED_ONLY_DEBT`, with exact `(method, path)` pairs and no globbing, and both registers are capped — so a new unprotected route fails the build and the debt can only shrink | `tests/integration/test_route_authorisation_census.py`, `src/domain/authz/route_declarations.py` |
| **Role hierarchy** | **Not implemented** | The live `Role` has `name`, `description`, `permissions`, `is_system_role` and no parent or level. `parent_role_id` / `hierarchy_level` exist only on `ABACRole` (see below), which no request path reads. Privilege is flat: a role grants exactly the tokens listed on it | — |
| **ABAC — attribute/policy checks, field-level permissions, denial auditing** | **Not implemented** | `ABACService` and the `abac_*`, `field_level_permissions` and `permission_audits` tables exist in the schema but are **unreachable**: `ABACService` is constructed in exactly one place in the repository, its own unit test (`tests/unit/test_abac_service.py`); no route, dependency or middleware builds one. `src/domain/authz/__init__.py` records the model set as dead code. Do not cite this as a control | `src/domain/services/abac_service.py`, `src/domain/models/permissions.py` (both dead) |
| **Tenant scoping** | **Not effective** | Services filter on `tenant_id`, and 21 tables carry a `tenant_isolation` RLS policy, but the application's database role holds `rolbypassrls`, so PostgreSQL skips policy evaluation entirely — defect C-27, open | `src/infrastructure/middleware/tenant_context.py` (`TenantContextMiddleware`), `docs/governance/rls-least-privilege-rollout.md` |

**On field-level permissions and denial auditing specifically**, because both were previously claimed here: no live code path masks a field by permission, and no live code path writes a permission-denial record. The only implementations are `ABACService.get_allowed_fields` / `ABACService.mask_field_value` over `FieldLevelPermission`, and `ABACService._log_permission_check` writing `PermissionAudit` — all on the unreachable service. `require_permission` raises a bare 403 and records nothing. A refused **write** does leave an entry in the API audit trail via `AuditLoggingMiddleware` carrying `status_code: 403` in its metadata, but that is an incidental byproduct of mutating-request logging, not a denial decision record — it has no decision field, and refused **reads** (400 of the 474 uncovered endpoints are `GET`) produce nothing at all.

**Provenance of the endpoint figures.** The counts in this section are produced by `src/domain/authz/census.py` over the mounted non-production app, not maintained by hand; re-measure with `take_census(app)` and group by `EndpointPosture.posture`. They were measured for this revision on 2026-07-29. Defect C-2 remediation reduces the 474 as it lands, so a lower figure here is expected progress, not a discrepancy.

---

## 6. Infrastructure and transport security

| Control | Detail |
| --- | --- |
| **HTTPS** | Enforced at reverse proxy / App Service; app sets **HSTS** (`max-age=31536000; includeSubDomains`) |
| **Security headers** | See §2 CSP; `X-Frame-Options: DENY`, COOP/CORP, MIME sniff protection |
| **CORS** | Explicit origins + Azure Static Web Apps preview regex in `src/main.py` |
| **Rate limiting** | `RateLimitMiddleware` → infrastructure rate limiter (Redis-backed when configured) |

---

## 7. Vulnerability management

| Process | Detail |
| --- | --- |
| **Dependabot** | Weekly dependency PRs with labels (`.github/dependabot.yml`) |
| **Advisory handling** | Triage pip-audit / npm audit / GitHub Advisory DB findings; patch or document waiver via `scripts/validate_security_waivers.py` |
| **Responsible disclosure** | Publish a security contact in the organisation’s main README / website; track issues privately until patched |

---

## 8. Penetration testing plan

| Item | Plan |
| --- | --- |
| **Cadence** | **Annual** full-scope penetration test; **incremental** retest after major architecture changes |
| **Scope** | External API (`/api/v1`), authentication flows (Azure AD + JWT), tenant isolation, file uploads, admin functions, Celery/redis exposure (if any), frontend SPA hosting |
| **Rules of engagement** | Staging environment mirror; no production destructive testing without written approval |
| **Remediation SLA** | **Critical:** 7 days; **High:** 30 days; **Medium:** 90 days; **Low:** next maintenance window (adjust per policy) |
| **Evidence** | Store executive summary and ticket closure references in `docs/evidence/` (controlled document) |

---

## 9. Dependency Deprecation Notices

### passlib → direct bcrypt

`passlib` is in maintenance-only mode. The project plans to migrate to direct `bcrypt` usage:

| Item | Current | Target |
|------|---------|--------|
| Library | `passlib[bcrypt]` | `bcrypt` (direct) |
| Hash function | `CryptContext(schemes=["bcrypt"])` | `bcrypt.hashpw()` / `bcrypt.checkpw()` |
| Timeline | — | Q3 2026 |
| Migration risk | Low — hash format is identical; only the Python wrapper changes |
| Tracking | ADR to be created when migration begins |

**Action:** No user-facing change. During migration, verify that existing bcrypt hashes are readable by the new implementation (they will be — bcrypt is standardised).

## 10. Review

Review this baseline **annually** or after significant incidents, releases, or infrastructure moves.

**Last updated:** 2026-07-29 (§1 A01 and §5 corrected: the authorisation evidence cited dead ABAC code and overstated RBAC coverage and tenant scoping — C-71)
