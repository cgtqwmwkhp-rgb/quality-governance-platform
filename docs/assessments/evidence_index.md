# Evidence Index — World-Class Assessment (Re-assessment #2)

**Date**: 2026-03-07

---

## By Critical Function

### CF1: Authentication & Authorization
| File | Dimensions | Role |
|------|-----------|------|
| `src/core/security.py` | D06 | JWT HS256, password hashing (bcrypt), token creation/validation |
| `src/core/azure_auth.py` | D06 | Azure AD B2C token exchange, JWKS validation |
| `src/api/routes/auth.py` | D06 | 8 auth endpoints (login, refresh, password reset, etc.) |
| `src/api/dependencies/__init__.py` | D06 | CurrentUser, CurrentSuperuser, CurrentActiveUser DI guards |
| `src/core/uat_safety.py` | D06 | UAT write protection middleware |
| `src/infrastructure/middleware/rate_limiter.py` | D06, D05 | Per-endpoint rate limiting (auth 10rpm, default 60rpm) |
| `tests/unit/test_security.py` | D15 | 14 tests: password hashing, JWT tokens |
| `tests/unit/test_rate_limiter.py` | D15 | 11 tests: rate limit config, in-memory limiter |
| `tests/unit/test_uat_safety.py` | D15 | 20 tests: UAT mode, overrides, admin checks |
| `tests/unit/test_auth_enforcement.py` | D15, D06 | 113 lines: auth enforcement regression |
| `tests/security/test_owasp_comprehensive.py` | D06, D15 | 31 OWASP Top 10 tests |
| `SECURITY.md` | D06, D22 | Security posture documentation |

### CF2: Business Workflows
| File | Dimensions | Role |
|------|-----------|------|
| `src/api/routes/incidents.py` | D06, D07, D10 | Incident CRUD with tenant isolation |
| `src/api/routes/complaints.py` | D06, D07, D10 | Complaint CRUD with tenant isolation |
| `src/api/routes/rtas.py` | D06, D10 | RTA CRUD with tenant isolation, reference numbers |
| `src/api/routes/audits.py` | D10 | Audit lifecycle endpoints |
| `src/api/routes/capa.py` | D14 | CAPA state transitions with improved error messages |
| `src/api/routes/risks.py` | D06, D10 | Risk CRUD with tenant isolation + pagination |
| `src/api/routes/policies.py` | D06, D10 | Policy CRUD with tenant isolation |
| `src/api/routes/standards.py` | D10 | Standards with fixed pagination |
| `src/api/routes/actions.py` | D10, D25 | Actions with unbounded query cap |
| `src/domain/services/reference_number.py` | D24 | Reference number generation (MAX/COUNT hybrid) |
| `src/domain/services/audit_service.py` | D09 | Audit business logic |
| `src/domain/services/capa_service.py` | D09 | CAPA service with core pagination |
| `docs/user-journeys/personas-and-journeys.md` | D01 | 5 personas, 5 journey maps |

### CF3: Data Writes + State Transitions
| File | Dimensions | Role |
|------|-----------|------|
| `src/api/middleware/idempotency.py` | D24 | SHA-256 payload dedup, 409 on mismatch |
| `src/domain/models/investigation.py` | D24 | Optimistic locking (version column) |
| `src/core/pagination.py` | D09, D24 | Framework-agnostic pagination utility |
| `src/core/update.py` | D09 | Framework-agnostic update utility |
| `src/domain/models/base.py` | D11 | TimestampMixin, ReferenceNumberMixin, SoftDeleteMixin, AuditTrailMixin |
| `src/domain/models/incident.py` | D11, D04 | FK indexes (index=True) on child relationships |
| `src/domain/models/complaint.py` | D11, D04 | FK indexes on child relationships |
| `src/domain/models/risk.py` | D11, D04 | FK indexes on child relationships |
| `src/domain/models/rta.py` | D11, D04 | FK indexes on child relationships |
| `src/domain/exceptions.py` | D14 | 15-type domain exception hierarchy |
| `src/api/middleware/error_handler.py` | D14 | Unified error envelope with request_id |
| `tests/unit/test_core_utils.py` | D15 | Tests for core pagination and update utilities |

### CF4: External Integrations
| File | Dimensions | Role |
|------|-----------|------|
| `src/infrastructure/cache/redis_cache.py` | D05 | Redis caching with graceful fallback |
| `src/infrastructure/resilience/circuit_breaker.py` | D05 | Dual circuit breaker implementation |
| `src/domain/services/email_service.py` | D05 | Email with retry (3x backoff) |
| `src/infrastructure/monitoring/azure_monitor.py` | D13, D28 | OpenTelemetry, 26+ metrics |
| `src/api/routes/health.py` | D05, D32 | Health probes with Redis connectivity check |
| `src/api/routes/slo.py` | D13, D28 | Live SLO/SLI metrics endpoint |
| `src/api/routes/telemetry.py` | D06, D13 | Telemetry with auth (superuser for reset) |
| `docs/observability/slo-definitions.md` | D13 | 5 SLOs with targets and error budgets |
| `docs/observability/dashboards/*.json` | D13, D32 | 3 Azure Monitor dashboard templates |

### CF5: Release/Deploy + Rollback
| File | Dimensions | Role |
|------|-----------|------|
| `.github/workflows/ci.yml` | D17 | 21+ CI jobs, all-checks gate |
| `.github/workflows/deploy-staging.yml` | D18 | Staging deployment with health verification |
| `.github/workflows/deploy-production.yml` | D18 | Production with governance signoff, deploy proof |
| `scripts/verify_deploy_deterministic.sh` | D30 | Deterministic SHA verification |
| `scripts/governance/validate_release_signoff.py` | D18, D29 | Release signoff validation |
| `docs/evidence/release_signoff.json` | D29 | Current release signoff artifact |
| `Dockerfile` | D30, D20 | Multi-stage build, digest pin, lockfile-first |
| `.github/dependabot.yml` | D20 | Weekly updates for pip, npm, actions |
| `requirements.txt` + `requirements.lock` | D20, D30 | Dependency management with hash verification |
| `CHANGELOG.md` | D22, D29 | Keep-a-Changelog format |

---

## By Dimension

### D01 Product clarity & user journeys
- `README.md`, `src/main.py` (21 OpenAPI tags), `frontend/src/App.tsx` (82 routes), `docs/user-journeys/personas-and-journeys.md`

### D02 UX quality & IA
- `docs/ux/information-architecture.md`, `docs/ux/component-inventory.md`, `docs/ux/analytics-baseline.md`, `frontend/src/styles/design-tokens.css`, `frontend/src/components/ui/`

### D03 Accessibility
- `docs/accessibility/wcag-checklist.md`, `frontend/src/test/axe-helper.ts`, `frontend/src/components/ui/LiveAnnouncer.tsx`, `frontend/package.json` (jsx-a11y, jest-axe)

### D04 Performance (FE+BE)
- `src/infrastructure/database.py` (pool config), `frontend/.size-limit.json`, `lighthouserc.json`, `frontend/src/lib/webVitals.ts`, `frontend/vite.config.ts` (manual chunks)

### D05 Reliability & resilience
- `src/infrastructure/resilience/circuit_breaker.py`, `src/infrastructure/tasks/dlq.py`, `src/api/routes/health.py`, `src/infrastructure/cache/redis_cache.py`

### D06 Security engineering
- `src/core/security.py`, `src/main.py` (SecurityHeadersMiddleware), `src/infrastructure/middleware/rate_limiter.py`, `.semgrep.yml`, `.gitleaksignore`, `SECURITY.md`, `docs/SECURITY_WAIVERS.md`, `tests/security/test_owasp_comprehensive.py`, `tests/unit/test_auth_enforcement.py`

### D07 Privacy & data protection
- `src/core/config.py` (pseudonymization_pepper), `docs/privacy/dpia-incidents.md`, `docs/privacy/data-classification.md`

### D08 Compliance readiness
- `src/domain/models/iso27001.py`, `src/domain/models/ims_unification.py`, `src/domain/models/planet_mark.py`, `src/domain/models/uvdb_achilles.py`

### D09 Architecture modularity
- `src/` directory structure, `src/api/__init__.py`, `src/core/pagination.py`, `src/core/update.py`, `pyproject.toml` (mypy overrides)

### D10 API design quality
- `src/main.py` (OpenAPI), `src/api/middleware/idempotency.py`, `scripts/check_api_path_drift.py`, `scripts/check_openapi_compatibility.py`

### D11 Data model quality
- `src/domain/models/` (27 files), `src/domain/models/base.py` (4 mixins), FK indexes across all child models

### D12 Schema versioning & migrations
- `alembic.ini`, `alembic/env.py`, `alembic/versions/` (63 migrations)

### D13 Observability
- `src/infrastructure/monitoring/azure_monitor.py`, `docs/observability/slo-definitions.md`, `docs/observability/dashboards/`, `src/api/routes/slo.py`

### D14 Error handling & user-safe failures
- `src/domain/exceptions.py`, `src/api/middleware/error_handler.py`, `src/infrastructure/resilience/`

### D15 Testing strategy
- `tests/` (104 files, 1,568 functions), `pyproject.toml` (pytest, coverage), `.github/workflows/ci.yml` (7 test jobs), `tests/contract/test_api_contracts.py` (332 lines)

### D16 Test data & fixtures
- `tests/factories/core.py` (9 factories), `tests/conftest.py`, `tests/integration/conftest.py`

### D17 CI quality gates
- `.github/workflows/ci.yml` (21+ jobs), `scripts/` (12+ validation scripts)

### D18 CD/release pipeline
- `.github/workflows/deploy-staging.yml`, `.github/workflows/deploy-production.yml`, `scripts/verify_deploy_deterministic.sh`, `scripts/governance/validate_release_signoff.py`

### D19 Configuration management
- `src/core/config.py`, `.env.example`, `src/domain/models/feature_flag.py`, `src/api/routes/feature_flags.py`

### D20 Dependency management
- `requirements.txt`, `requirements.lock`, `.github/dependabot.yml`, `Dockerfile`

### D21 Code quality & maintainability
- `pyproject.toml` (Black, isort, mypy), `.flake8`, `.semgrep.yml`, `scripts/validate_type_ignores.py`

### D22 Documentation quality
- `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`, `docs/adr/` (8 ADRs), `docs/runbooks/` (25 runbooks)

### D23 Operational runbooks
- `docs/runbooks/` (25 files: incident-response.md, rollback.md, database-recovery.md, deployment.md, escalation.md, + 20 more)

### D24 Data integrity & consistency
- `src/api/middleware/idempotency.py`, `src/domain/models/investigation.py`, `src/domain/services/reference_number.py`, FK indexes

### D25 Scalability & capacity
- `src/infrastructure/database.py` (pool config), `src/infrastructure/cache/`, `src/infrastructure/resilience/`

### D26 Cost efficiency
- `Dockerfile` (multi-stage), `docker-compose.yml`, `scripts/infra/cost_alerts.py`

### D27 I18n/L10n readiness
- `frontend/src/i18n/i18n.ts`, `frontend/src/i18n/locales/en.json` (2,118 lines), `scripts/i18n-check.mjs`

### D28 Analytics/telemetry
- `src/infrastructure/monitoring/azure_monitor.py`, `src/api/routes/telemetry.py`, `frontend/src/lib/webVitals.ts`, `docs/ux/analytics-baseline.md`

### D29 Governance & decision records
- `docs/adr/` (8 files), `CHANGELOG.md`, `docs/evidence/release_signoff.json`, `docs/STAGE2_COVENANTS.md`

### D30 Build determinism
- `Dockerfile`, `scripts/verify_deploy_deterministic.sh`, `scripts/generate_lockfile.sh`, `requirements.lock`

### D31 Environment parity
- `docker-compose.yml`, `docker-compose.sandbox.yml`, `docs/evidence/environment_endpoints.json`, `frontend/staticwebapp.config.json`

### D32 Supportability & operability
- `src/api/routes/health.py`, `src/main.py` (`/meta/version`), `src/infrastructure/monitoring/`, `docs/runbooks/`
