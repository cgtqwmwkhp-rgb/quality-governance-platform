# Evidence Index

**Assessment Date:** 2026-03-07 (Post Week-1 Uplift)

---

## By Critical Function

### CF1: Auth/Session + Authorization Boundaries

| File | Referenced In | Purpose |
|------|--------------|---------|
| `src/api/dependencies/__init__.py` | D06, F-001, F-002 | CurrentUser, auth dependencies, JWT flow |
| `src/core/security.py` | D06 | JWT HS256, token creation/validation |
| `src/core/azure_auth.py` | D06, CF4 | Azure AD B2C JWKS validation |
| `src/infrastructure/middleware/rate_limiter.py` | D06, D05, F-008 | Rate limiting; authenticated multiplier bug (L253) |
| `src/main.py` (L22-54) | D06, F-004 | SecurityHeadersMiddleware, CSP header |
| `tests/unit/test_auth_enforcement.py` | D15, D06 | Auth enforcement regression tests (46+ pairs) |

### CF2: Primary Business Workflows

| File | Referenced In | Purpose |
|------|--------------|---------|
| `src/api/routes/incidents.py` | D10, D15 | Incident CRUD endpoints |
| `src/domain/services/incident_service.py` | D09, D15 | Incident business logic |
| `src/domain/models/incident.py` | D11, D24 | Incident ORM model |
| `src/api/routes/audits.py` | D10, D24 | Audit execution endpoints |
| `src/domain/services/audit_service.py` | D09, D15 | Audit business logic |
| `src/domain/models/audit.py` | D11, D24 | Audit ORM model (needs optimistic locking) |
| `src/api/routes/risks.py` | D10 | Risk assessment endpoints |
| `src/domain/models/risk.py` | D11 | Risk ORM model |
| `src/api/routes/planet_mark.py` | D06, F-001 | Carbon management (16 endpoints, now auth-guarded) |
| `src/api/routes/uvdb.py` | D06, F-001 | UVDB audit protocol (13 endpoints, now auth-guarded) |

### CF3: Data Writes + State Transitions

| File | Referenced In | Purpose |
|------|--------------|---------|
| `src/api/middleware/idempotency.py` | D24 | SHA-256 + Redis 24h idempotency |
| `src/domain/services/reference_number.py` | D24 | MAX/COUNT hybrid ref number generation |
| `src/api/routes/employee_portal.py` (L177-220) | D24, D06, F-011 | Public report creation without tenant_id |
| `src/domain/models/investigation.py` (L164) | D24, D11 | Optimistic locking (version column) |
| `src/domain/models/base.py` | D11 | TimestampMixin, ReferenceNumberMixin, SoftDeleteMixin, AuditTrailMixin |

### CF4: External Integrations

| File | Referenced In | Purpose |
|------|--------------|---------|
| `src/infrastructure/monitoring/azure_monitor.py` | D13, D28, F-010, C-001 | OpenTelemetry/OpenCensus mismatch |
| `src/api/routes/telemetry.py` | D28 | Frontend telemetry events |
| `src/api/routes/slo.py` | D13, D28, F-002, F-009, C-002 | SLO endpoints (not mounted) |
| `src/api/__init__.py` | F-009, C-002 | Router aggregation (missing SLO import) |
| `requirements.txt` | D20, F-010 | Dependencies (opencensus listed, not opentelemetry) |

### CF5: Release/Deploy + Rollback

| File | Referenced In | Purpose |
|------|--------------|---------|
| `.github/workflows/ci.yml` | D17 | 21+ CI jobs |
| `.github/workflows/deploy-staging.yml` | D18 | Staging deployment |
| `.github/workflows/deploy-production.yml` | D18 | Production deployment with governance gate |
| `release_signoff.json` | D18 | SHA-validated governance signoff |
| `scripts/verify_deploy_deterministic.sh` | D30 | Deterministic deploy verification |
| `Dockerfile` | D30 | Multi-stage, digest-pinned |
| `.github/dependabot.yml` | D20 | Dependency update automation |

---

## By Dimension

### D01: Product Clarity
- `README.md` — Project overview, tech stack, architecture
- `docs/user-journeys/personas-and-journeys.md` — 5 personas, 5 journey maps
- `frontend/src/App.tsx` (L12-79) — 71+ page routes

### D02: UX Quality & IA
- `docs/ux/information-architecture.md` — Sitemap, navigation structure
- `docs/ux/component-inventory.md` — 12 primitives, 11 gaps
- `frontend/src/contexts/ToastContext.tsx` — Global toast system
- `frontend/src/pages/Dashboard.tsx` — Live dashboard with Promise.allSettled
- `frontend/src/components/ui/Card.tsx` — CardSkeleton loading component

### D03: Accessibility
- `docs/accessibility/wcag-checklist.md` — WCAG 2.1 AA checklist
- `frontend/src/components/ui/LiveAnnouncer.tsx` — aria-live announcements
- `frontend/package.json` — eslint-plugin-jsx-a11y, jest-axe dependencies

### D04: Performance
- `src/infrastructure/database.py` — Pool config (pool_size=10, max_overflow=20, statement_timeout=30s)
- `frontend/.size-limit.json` — Bundle size limits
- `frontend/lighthouserc.js` — Lighthouse CI config
- `frontend/src/lib/webVitals.ts` — Web Vitals reporting

### D05: Reliability & Resilience
- `src/infrastructure/middleware/rate_limiter.py` — Rate limiting with fallback
- `src/api/routes/health.py` — /health, /healthz, /readyz (Redis check)

### D06: Security Engineering
- `src/api/dependencies/__init__.py` — Auth dependencies
- `src/main.py` (L22-54) — Security headers + CSP
- `src/infrastructure/middleware/rate_limiter.py` — Rate limiter (bug at L253)
- `.semgrep.yml` — Security scanning rules
- `SECURITY.md` — Security policy

### D07: Privacy & Data Protection
- `src/core/config.py` — pseudonymization_pepper validation
- `docs/privacy/dpia-incidents.md` — DPIA for incident module
- `docs/privacy/data-classification.md` — C1-C4 classification

### D08: Compliance Readiness
- `src/domain/models/iso27001.py` — ISO 27001 domain models
- `src/domain/models/ims_unification.py` — IMS unification
- `src/api/routes/compliance.py` — Compliance endpoints

### D09: Architecture Modularity
- `src/core/pagination.py` — Domain→API dependency fix
- `src/core/update.py` — Domain→API dependency fix
- `pyproject.toml` — 30 mypy overrides (GOVPLAT-004)

### D10: API Design Quality
- `src/api/middleware/idempotency.py` — Idempotency middleware
- `src/api/schemas/error_codes.py` — Structured error codes

### D11: Data Model Quality
- `src/domain/models/base.py` — 4 base mixins
- `src/domain/models/__init__.py` — 27+ model imports

### D12: Schema Versioning & Migrations
- `alembic/env.py` — Migration environment
- `alembic/versions/` — 63 migration files

### D13: Observability
- `src/infrastructure/monitoring/azure_monitor.py` — OTel/OpenCensus (mismatch)
- `docs/observability/slo-definitions.md` — 5 SLOs defined
- `src/api/routes/slo.py` — SLO endpoints (not mounted)

### D14: Error Handling
- `src/domain/exceptions.py` — 15-type exception hierarchy
- `src/api/middleware/error_handler.py` — Unified error envelope
- `frontend/src/contexts/ToastContext.tsx` — Global toast notifications

### D15: Testing Strategy
- `tests/unit/` — Unit tests
- `tests/integration/` — Integration tests
- `tests/contract/` — Contract tests
- `tests/e2e/` — E2E tests
- `tests/smoke/` — Smoke tests
- `tests/uat/` — UAT tests
- `pyproject.toml` (L201-221) — Pytest config, coverage 35%
- `frontend/playwright.config.ts` — Playwright configured (no specs)

### D16: Test Data & Fixtures
- `tests/factories/core.py` — 9 factory-boy factories
- `tests/conftest.py` — Session fixtures, JWT mocking, DB seeding

### D17: CI Quality Gates
- `.github/workflows/ci.yml` — 21+ CI jobs

### D18: CD/Release Pipeline
- `.github/workflows/deploy-staging.yml` — Staging deploy
- `.github/workflows/deploy-production.yml` — Production deploy

### D19: Configuration Management
- `src/core/config.py` — Pydantic BaseSettings with production validation
- `.env.example` — Environment template
- `src/api/routes/feature_flags.py` — Feature flag management

### D20: Dependency Management
- `requirements.txt` — Python dependencies
- `requirements.lock` — Pinned with hashes
- `frontend/package.json` — Node dependencies
- `.github/dependabot.yml` — Dependabot config

### D21: Code Quality & Maintainability
- `.flake8` — Linting config (F401/F841 ignored, max-complexity=20)
- `pyproject.toml` — Black 120, isort, mypy 30 overrides

### D22: Documentation Quality
- `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`
- `docs/adr/` — 9 ADRs (numbering collisions)
- `docs/runbooks/` — 25 runbooks

### D23: Operational Runbooks
- `docs/runbooks/incident-response.md` — Contacts filled, on-call rotation defined
- `docs/runbooks/escalation.md` — Updated escalation procedures
- `docs/runbooks/` — 25 total runbooks

### D24: Data Integrity & Consistency
- `src/api/middleware/idempotency.py` — Idempotency
- `src/domain/models/investigation.py` (L164) — Optimistic locking
- `src/domain/services/reference_number.py` — Collision-safe ref generation
- `src/api/routes/employee_portal.py` (L195-220) — Missing tenant_id

### D25: Scalability & Capacity
- `src/infrastructure/database.py` — Pool config
- `frontend/vite.config.ts` — Manual chunk splitting

### D26: Cost Efficiency
- `Dockerfile` — Multi-stage build
- `src/services/cost_alerts.py` — Cost alert module

### D27: I18n/L10n
- `frontend/src/i18n/i18n.ts` — i18next setup
- `frontend/src/i18n/locales/en.json` — 2,118 keys
- `scripts/i18n-check.mjs` — CI i18n validation

### D28: Analytics/Telemetry
- `src/api/routes/telemetry.py` — Frontend event telemetry
- `frontend/src/lib/webVitals.ts` — Web Vitals
- `docs/ux/analytics-baseline.md` — Analytics baseline

### D29: Governance & Decision Records
- `docs/adr/` — 9 ADRs (numbering collision: C-003)
- `CHANGELOG.md` — Keep a Changelog format
- `release_signoff.json` — Governance gate
- `docs/STAGE2_COVENANTS.md` — Stage 2 covenants

### D30: Build Determinism
- `Dockerfile` — Digest-pinned base image
- `requirements.lock` — Hash-pinned deps
- `scripts/verify_deploy_deterministic.sh` — Determinism verification
- `scripts/generate_lockfile.sh` — Lockfile generation

### D31: Environment Parity
- `docker-compose.yml` — PG 16-alpine
- `docs/evidence/environment_endpoints.json` — Endpoint listing

### D32: Supportability & Operability
- `src/api/routes/health.py` — Health probes (/health, /healthz, /readyz)
- `src/main.py` — /meta/version endpoint
- `docs/runbooks/incident-response.md` — On-call rotation

---

## Summary Statistics

| Category | Count |
|----------|-------|
| Total files referenced | 92 |
| Findings (all) | 12 (4 resolved, 8 open) |
| Contradictions | 3 |
| Evidence gaps | 6 |
| Backlog items | 34 |
| Dimensions at WCS 10.0 | 3 (D17, D18, D30) |
| Dimensions at WCS 9.0+ | 5 (D06, D24, D17, D18, D30) |
| Dimensions below WCS 5.0 | 3 (D03=4.5, D27=4.5, D26=3.0) |
