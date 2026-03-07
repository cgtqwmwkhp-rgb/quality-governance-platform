# Changelog

All notable changes to the Quality Governance Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- World-class assessment framework with 32-dimension scoring (`docs/assessments/`)
- Top 15 action plan across 3 categories: Low Effort/High Value, Critical Workflows, UI/UX
- ADR-0001 through ADR-0003 retrospective architecture decision records
- Operational runbook skeletons for 5 key scenarios
- SLO/SLI definitions for platform observability
- User personas and journey maps (`docs/user-journeys/personas-and-journeys.md`)
- WCAG 2.1 AA compliance checklist (`docs/accessibility/wcag-checklist.md`)
- Auth enforcement regression test suite (`tests/unit/test_auth_enforcement.py`)
- Behavioral service tests for reference numbers, risk scoring, JWT utils (`tests/unit/test_services.py`)
- Full CRUD API contract tests for all major endpoints (`tests/contract/test_api_contracts.py`)
- axe-core accessibility test helper for component tests (`frontend/src/test/axe-helper.ts`)
- Accessibility lint gate in CI (jsx-a11y errors are now blocking)
- Down-migration reversibility check in CI integration tests
- DPIA for incident and complaint data (`docs/privacy/dpia-incidents.md`)
- Data classification policy with model-level tagging (`docs/privacy/data-classification.md`)
- 3 Azure Monitor dashboard templates: API health, auth/security, business metrics (`docs/observability/dashboards/`)
- DLQ depth threshold alerting with WARN (10) and CRITICAL (50) thresholds
- Circuit breaker state transition metrics emitted to Azure Monitor
- Information Architecture audit with full sitemap and navigation recommendations (`docs/ux/information-architecture.md`)
- Design tokens CSS custom properties for spacing, colour, typography, radii, shadows (`frontend/src/styles/design-tokens.css`)
- Component inventory documenting 12 existing primitives and 11 recommended additions (`docs/ux/component-inventory.md`)
- Web Vitals reporter (CLS, FID, LCP, TTFB, INP) wired into app entry point (`frontend/src/lib/webVitals.ts`)
- Lighthouse CI configuration with performance/accessibility/SEO score gates (`lighthouserc.json`)
- Analytics baseline document covering current capabilities, KPIs, and instrumentation gaps (`docs/ux/analytics-baseline.md`)
- CHANGELOG.md (this file)

### Security
- **[P0]** Restored authentication guards on all tenant management endpoints (`src/api/routes/tenants.py`)
- **[P0]** Added authentication to all ISO compliance endpoints (`src/api/routes/compliance.py`)
- **[P0]** Tenant-scoped data isolation on incidents, complaints, risks, near-misses
- Expired/forged JWT rejection verified via automated test suite

### Fixed
- PostgreSQL version parity: all CI service containers upgraded from 15 to 16
- Misleading alembic.ini placeholder database URL replaced with documented comment
- Hardcoded `user_id=1` in tenant routes replaced with `current_user.id` from JWT
- Coverage threshold aligned between CI (was 35%) and pyproject.toml (50%)
- Near-miss, risk, incident, and complaint queries now respect tenant boundaries
- **[SECURITY]** Rate limiter auth path mismatch: `/api/auth/` → `/api/v1/auth/` (brute-force limits were never matching)
- **[RELIABILITY]** `/readyz` now performs real `SELECT 1` database health check instead of returning hardcoded `"ok"`
- **[RELIABILITY]** Added `pool_recycle=1800` and `pool_timeout=30` to PostgreSQL engine (prevents stale connections behind load balancers)
- **[API]** Idempotency middleware 409 response now uses standard `{"error": {...}}` envelope
- **[API]** Idempotency middleware extended to cover PUT/PATCH methods (was POST-only)
- **[DATABASE]** `alembic/env.py` now imports all models via wildcard (was missing ~80 of 100+ models for autogenerate)
- **[PERFORMANCE]** Added `index=True` on `status` and `created_at` columns across 10 high-traffic tables
- **[PERFORMANCE]** Actions endpoint refactored from in-memory pagination to SQL-level LIMIT/OFFSET
- **[API]** Consolidated duplicate `ReferenceNumberService` — `src/services/` now re-exports from `src/domain/services/`

### Changed
- ESLint jsx-a11y rules upgraded from `warn` to `error` for critical accessibility rules
- `jest-axe` added to frontend devDependencies for automated accessibility testing
- **[B2]** Type safety: `workflow_engine.py` overrides reduced from 4 to 1 error code
- **[B2]** Type safety: `redis_cache.py` overrides reduced from 4 to 1 error code
- **[B2]** Type safety: `risk_scoring.py` overrides reduced from 3 to 1 error code
- **[B2]** Total suppressed mypy error codes reduced from ~85 to ~71 (target: <17 overrides by Q2)
- Design tokens imported in frontend entry point for consistent theming
- Web Vitals reporter initialized on app startup

## [1.0.0] - 2026-03-01

### Added
- Enterprise-grade Integrated Management System (IMS) platform
- ISO 9001, 14001, 27001, 45001 compliance management
- Incident reporting with RIDDOR classification and SIF/pSIF tracking
- Audit & inspection system with template-run pattern and version control
- Enterprise risk register with ISO 31000 taxonomy and bow-tie analysis
- Complaint management with email ingestion and external reference idempotency
- Road traffic collision management
- Investigation system with optimistic locking and customer pack generation
- CAPA (Corrective and Preventive Action) management with state machine
- Policy and document library with AI-powered analysis
- Digital signature system (eIDAS/ESIGN compliant design)
- AI Copilot with RAG knowledge base
- Multi-tenancy with feature flags and usage limits
- Immutable audit trail with hash-chain verification
- Workforce development platform (assessments, inductions, engineer competency)
- UVDB Achilles Verify B2 audit protocol
- Planet Mark carbon management (GHG Protocol Scope 1-3)
- LOLER 1998 equipment examination tracking
- React 18 + TypeScript + Vite frontend with 82 lazy-loaded pages
- FastAPI + SQLAlchemy 2.0 async backend with 48 route modules
- 62 Alembic database migrations
- 21+ CI quality gate jobs with deterministic deploy verification
- 5-phase production deploy proof
- Circuit breakers, DLQ with replay, bulkhead resilience patterns
- Field-level encryption (Fernet/AES-128-CBC) for PII
- Structured JSON logging with PII filtering and correlation IDs
- Azure AD SSO integration with JWKS validation
