# Security Baseline — QGP

**Platform:** Quality Governance Platform (QGP)  
**Version:** 1.0  
**Related code:** `src/main.py`, `src/core/security.py`, `src/core/azure_auth.py`, `.github/workflows/ci.yml`, `.github/dependabot.yml`

---

## 1. OWASP Top 10 (2021) mapping

| OWASP category | Risk | Control in QGP |
| --- | --- | --- |
| **A01 Broken Access Control** | IDOR, privilege escalation | JWT authentication, **RBAC** (`Role`, `Permission`, `UserRole`), **ABAC** (`ABACService`, policies), tenant scoping on queries, rate limiting |
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

| Layer | Description | Code |
| --- | --- | --- |
| **RBAC** | Permissions aggregated into roles; user–role assignments | `src/domain/models/permissions.py` (`Role`, `Permission`, `UserRole`, `RolePermission`) |
| **Role hierarchy** | Parent role / `hierarchy_level` on `Role` | `src/domain/models/permissions.py` |
| **ABAC** | Attribute and policy-based checks, field-level permissions, audit of permission denials | `src/domain/services/abac_service.py` |

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

**Last updated:** 2026-03-21
