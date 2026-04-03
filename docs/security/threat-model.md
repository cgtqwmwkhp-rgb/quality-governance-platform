# Threat Model — Quality Governance Platform (D06)

**Owner**: Platform Engineering
**Last Updated**: 2026-04-03
**Methodology**: STRIDE
**Review Cycle**: Annually and before major architecture changes

---

## 1. System Overview

The Quality Governance Platform is a multi-tenant SaaS application for workplace safety, quality management, and regulatory compliance. It processes organizational data (incidents, audits, risks, complaints, CAPA actions) for tenant organizations.

### Architecture Summary

```
Users (Browser) → Azure Static Web Apps (React SPA)
                      ↓ HTTPS
                Azure App Service (FastAPI backend)
                      ↓ TLS
                Azure PostgreSQL Flexible Server
                      ↓
                Azure Blob Storage (evidence assets)
```

---

## 2. Trust Boundaries

| Boundary | Description |
|----------|-------------|
| **B1**: Internet → SWA | Public internet to frontend CDN |
| **B2**: SWA → App Service | Frontend API calls to backend |
| **B3**: App Service → PostgreSQL | Backend to database |
| **B4**: App Service → Blob Storage | Backend to file storage |
| **B5**: App Service → Redis | Backend to cache/rate limiter |
| **B6**: Tenant A ↔ Tenant B | Logical isolation within shared infrastructure |

---

## 3. STRIDE Analysis

### Spoofing (S)

| Threat | Risk | Mitigation | Evidence |
|--------|------|------------|----------|
| Credential theft via phishing | Medium | JWT with short expiry; bcrypt password hashing | `src/infrastructure/auth/` |
| Token replay | Medium | Token expiry validation; HTTPS-only transport | `src/api/middleware/auth.py` |
| Cross-tenant impersonation | High | `tenant_id` validated on every request via dependency injection | `src/api/dependencies.py` |

### Tampering (T)

| Threat | Risk | Mitigation | Evidence |
|--------|------|------------|----------|
| Request body manipulation | Medium | Pydantic validation on all inputs; type-safe schemas | `src/domain/schemas/` |
| Database record tampering | Low | App-level access control; no direct DB access exposed | Row-level tenant filtering |
| Evidence file tampering | Medium | Blob storage SAS tokens with expiry; no public access | `src/infrastructure/blob_storage.py` |

### Repudiation (R)

| Threat | Risk | Mitigation | Evidence |
|--------|------|------------|----------|
| Denial of actions taken | Medium | Structured audit logs with `request_id`, `user_id`, `tenant_id` | `src/infrastructure/middleware/request_logger.py` |
| Audit trail manipulation | Low | Logs stored in Azure Log Analytics (immutable retention) | Azure platform |

### Information Disclosure (I)

| Threat | Risk | Mitigation | Evidence |
|--------|------|------------|----------|
| Cross-tenant data leakage | Critical | Row-level `tenant_id` filtering on all queries | `src/api/dependencies.py` |
| Sensitive data in logs | Medium | Structured logging; PII not logged in request bodies | Logger configuration |
| Error message information leakage | Low | Global error handler returns generic messages; `request_id` for correlation | `src/api/middleware/error_handler.py` |
| Evidence asset unauthorized access | Medium | SAS URLs with tenant-scoped paths and time-limited tokens | Blob storage service |

### Denial of Service (D)

| Threat | Risk | Mitigation | Evidence |
|--------|------|------------|----------|
| API endpoint flooding | Medium | Rate limiting middleware (Redis-backed, in-memory fallback) | `src/infrastructure/middleware/rate_limiter.py` |
| Database query exhaustion | Medium | `statement_timeout=30000`; connection pool limits (`pool_size=10, max_overflow=20`) | `src/infrastructure/database.py` |
| Large file upload abuse | Low | Size limits on evidence uploads | Service-layer validation |
| Compute resource exhaustion | Medium | Auto-scale (min 2, max 6 instances); CPU-based scaling | `scripts/infra/autoscale-settings.json` |

### Elevation of Privilege (E)

| Threat | Risk | Mitigation | Evidence |
|--------|------|------------|----------|
| Regular user accessing admin functions | Medium | `CurrentSuperuser` dependency for admin endpoints | `src/api/dependencies.py` |
| Tenant user accessing other tenants | Critical | `tenant_id` enforcement at dependency layer | Consistent across all routes |
| SQL injection | Low | SQLAlchemy ORM with parameterized queries; no raw SQL in routes | `src/api/routes/` |
| XSS via stored content | Medium | React auto-escaping; CSP headers in `staticwebapp.config.json` | Frontend framework + CSP |

---

## 4. Attack Surface Inventory

| Surface | Exposure | Controls |
|---------|----------|----------|
| Public API (`/api/v1/*`) | Internet-facing via App Service | JWT auth, rate limiting, input validation |
| Health endpoints (`/healthz`, `/readyz`) | Internet-facing, unauthenticated | Read-only; no sensitive data |
| Static frontend (SWA) | Internet-facing CDN | CSP, HTTPS enforcement |
| PostgreSQL | Private (Azure VNET) | No public endpoint; App Service managed identity |
| Blob Storage | Private (SAS-only access) | Time-limited SAS tokens; tenant-scoped paths |
| Redis | Private (Azure VNET or built-in) | Internal-only access |

---

## 5. CI/CD Security Gates

| Gate | Tool | Scope |
|------|------|-------|
| Dependency vulnerability scan | `pip-audit` | Python packages |
| Dependency vulnerability scan | `npm audit` | npm packages |
| Secret scanning | `gitleaks` | Source code and history |
| SBOM generation | `cyclonedx-bom` | Software bill of materials |
| Security covenant | Custom script | CI pipeline integrity |
| Trojan source detection | Unicode scan | Source file encoding |
| Static analysis | `bandit` | Python security anti-patterns |

---

## 6. Residual Risks

| Risk | Severity | Status | Mitigation Plan |
|------|----------|--------|-----------------|
| No external penetration test conducted | Medium | Open | Scheduled per `docs/security/pentest-plan.md` |
| Production telemetry disabled (limits visibility) | Medium | Open | Enablement plan per `docs/observability/telemetry-enablement-plan.md` |
| Free-text fields may contain unintended PII | Low | Accepted | User responsibility; no automated PII detection |

---

## Related Documents

- [`docs/security/pentest-plan.md`](pentest-plan.md) — external pentest plan
- [`docs/security/security-baseline.md`](security-baseline.md) — security controls baseline
- [`docs/evidence/security-review-log.md`](../evidence/security-review-log.md) — review history
- [`docs/adr/ADR-0009-csrf-not-required.md`](../adr/ADR-0009-csrf-not-required.md) — CSRF decision
