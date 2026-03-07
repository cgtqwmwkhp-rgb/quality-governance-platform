# Quality Governance Platform — World-Class Assessment (Round 1)

**Date:** 2026-03-07 (Post Week-1 Uplift)
**Assessor:** World-Class App Assessor + Build Director
**Prior Assessment:** 2026-03-07 (Pre Week-1 Uplift)
**Method:** Evidence-led, two-round, 32-dimension, enterprise audit standard

---

## 1. Executive Summary

- **Average Maturity:** 3.81 / 5.0 (prior 3.73 — **+0.08**)
- **Average World-Class Score (WCS):** 7.1 / 10.0 (prior 7.0 — **+0.1**)
- **Overall Confidence:** Medium-High — Direct evidence from 27 domain models, 55 route modules (all business endpoints now auth-guarded), 63 migrations, 21+ CI jobs, 25 runbooks, 9 ADRs, 104+ test files with 1,582+ test functions, 14 frontend test files. Gaps: no load test results, no external audit reports, coverage 35%, SLO router not mounted.
- **Top 5 Strengths:**
  - D17 CI Quality Gates (WCS 10.0) — 21+ CI jobs, Trojan source, lockfile, API drift, SBOM
  - D18 CD/Release Pipeline (WCS 10.0) — staging+prod deploy, governance signoff, deterministic SHA
  - D30 Build Determinism (WCS 10.0) — Docker digest pin, lockfile-first, CycloneDX SBOM
  - D06 Security Engineering (WCS 9.0) — auth on all business endpoints + CSP + rate limiter + Bandit/pip-audit
  - D24 Data Integrity (WCS 9.0) — idempotency, optimistic locking, ref-number collision-safe, FK indexes, audit trail
- **Top 5 Deficits:**
  - D26 Cost Efficiency (WCS 3.0) — no FinOps, no spend analysis
  - D03 Accessibility (WCS 4.5) — tooling installed but no a11y test files
  - D27 I18n/L10n (WCS 4.5) — frontend only, single locale
  - D04 Performance (WCS 5.4) — no load test results, no APM profiling
  - D25 Scalability (WCS 5.4) — no autoscaling, no load tests
- **Biggest Improvement vs Prior:** D02 UX Quality & IA (+1.8 WCS, from 5.4 to 7.2) — live dashboard data, skeleton loading, global toast system
- **Biggest Regression vs Prior:** None detected
- **World-Class Breach List:** 29 of 32 dimensions have WCS < 9.5 (only D17, D18, D30 at 10.0)

---

## 2. Critical Function Map

### CF1: Auth/Session + Authorization Boundaries

| Attribute | Detail |
|-----------|--------|
| **Location** | `src/api/dependencies/__init__.py` (get_current_user L19-55), `src/core/security.py` (JWT HS256), `src/core/azure_auth.py` (Azure AD B2C) |
| **Dependent Services** | PostgreSQL (user lookup), Redis (token blacklist), Azure AD B2C (JWKS) |
| **Blast Radius** | **HIGH** — compromise exposes all tenant data, all CRUD operations |
| **Current Risks** | Rate limiter bug: `startswith("user:")` never matches (should be `"token:"`); authenticated users don't get 2x rate multiplier. SLO endpoints exist but router not mounted (dead code). |
| **Safety Gates** | `tests/unit/test_auth_enforcement.py` covers 46+ endpoint/method pairs; JWT expiry + refresh; tenant isolation on all queries |

### CF2: Primary Business Workflows (Top 3)

| Workflow | Location | Blast Radius | Risks |
|----------|----------|--------------|-------|
| **Incident Lifecycle** (report→triage→investigate→resolve→CAPA) | `src/api/routes/incidents.py`, `src/domain/services/incident_service.py`, `src/domain/models/incident.py` | **HIGH** — core business process, ISO 45001 compliance artifact | Coverage 35%; reference number collision in concurrent writes mitigated but not load-tested |
| **Audit Execution** (template→schedule→execute→findings→signoff) | `src/api/routes/audits.py`, `src/domain/services/audit_service.py`, `src/domain/models/audit.py` | **HIGH** — ISO compliance evidence chain | Optimistic locking only on InvestigationRun, not on AuditRun |
| **Risk Assessment** (identify→assess→controls→monitor→review) | `src/api/routes/risks.py`, `src/domain/models/risk.py`, `src/domain/models/risk_register.py` | **MEDIUM** — informs management decisions | No workflow state machine enforced in code |

### CF3: Data Writes + State Transitions + Side Effects

| Attribute | Detail |
|-----------|--------|
| **Location** | `src/api/middleware/idempotency.py`, `src/domain/services/reference_number.py`, `src/api/routes/employee_portal.py` (public writes) |
| **Blast Radius** | **HIGH** — data corruption/duplication affects audit trails and compliance |
| **Current Risks** | Employee portal `submit_quick_report` (L177-220) creates Incident/Complaint without `tenant_id` — orphaned records invisible to tenant-scoped queries. Reference number generation uses `MAX+COUNT` hybrid but not load-tested under concurrency. |
| **Safety Gates** | Idempotency middleware (SHA-256 + Redis 24h TTL), FK constraints (270 indexes), audit trail hash-chain |

### CF4: External Integrations

| Integration | Location | Blast Radius | Risks |
|-------------|----------|--------------|-------|
| **Azure AD B2C** | `src/core/azure_auth.py`, `src/api/routes/auth.py` (token-exchange) | **MEDIUM** — auth fallback to local JWT exists | JWKS cache timeout not configurable |
| **Azure Blob Storage** | `src/infrastructure/storage/` | **LOW** — file attachments only | Retry/circuit breaker not confirmed for blob ops |
| **Azure Monitor** | `src/infrastructure/monitoring/azure_monitor.py` | **LOW** — observability only | Code references OpenTelemetry but `requirements.txt` lists OpenCensus (deprecated) |

### CF5: Release/Deploy + Rollback + Config

| Attribute | Detail |
|-----------|--------|
| **Location** | `.github/workflows/deploy-staging.yml`, `.github/workflows/deploy-production.yml`, `scripts/verify_deploy_deterministic.sh`, `release_signoff.json` |
| **Blast Radius** | **HIGH** — bad deploy = platform outage |
| **Current Risks** | `release_signoff.json` SHA mismatch requires manual `workflow_dispatch` override; no automated canary or blue-green mechanism |
| **Safety Gates** | Governance signoff gate, deterministic SHA verification (3 consecutive matches), DB backup before migration, post-deploy health/security checks, rollback workflow |

---

## 3. Scorecard Table

| ID | Dimension | Mat (0-5) | WCS (0-10) | CM | Ev Str | Prev (0-5) | Delta | WCS Gap | CW | PS | Effort | Value | Evidence Pointers |
|----|-----------|-----------|------------|-----|--------|------------|-------|---------|----|----|--------|-------|-------------------|
| D01 | Product clarity & user journeys | 4 | 7.2 | 0.9 | Medium | 4 | 0 | 2.3 | 2 | 4.6 | M | M | README.md; 21 OpenAPI tags; 71+ frontend pages; `docs/user-journeys/personas-and-journeys.md` (5 personas, 5 journeys) |
| D02 | UX quality & IA | 4 | 7.2 | 0.9 | Medium | 3.5 | +0.5 | 2.3 | 1 | 2.3 | L | M | Dashboard wired to real API data via `Promise.allSettled`; skeleton loading; global toast (`ToastContext.tsx`); `docs/ux/information-architecture.md`; `docs/ux/component-inventory.md` (12 primitives, 11 gaps); Radix UI; design-tokens.css |
| D03 | Accessibility | 3 | 4.5 | 0.75 | Weak | 3 | 0 | 5.0 | 1 | 5.0 | M | H | `docs/accessibility/wcag-checklist.md`; jsx-a11y plugin; jest-axe ^9.0.0 installed; `LiveAnnouncer.tsx`; Radix UI primitives — **no `.a11y.test` files exist** |
| D04 | Performance (FE+BE) | 3 | 5.4 | 0.9 | Medium | 3 | 0 | 4.1 | 2 | 8.2 | L | H | `database.py` pool_size=10/max_overflow=20/statement_timeout=30s; `.size-limit.json`; `lighthouserc.js` (perf≥80); `webVitals.ts`; `CardSkeleton` loading — **no load test results, no APM profiling** |
| D05 | Reliability & resilience | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 3 | 4.5 | M | H | Circuit breakers (2 impls); retry+backoff; bulkhead (auth=50, biz=100); DLQ+replay; `/readyz` with Redis check; health probes |
| D06 | Security engineering | 5 | 9.0 | 0.9 | Strong | 4.5 | +0.5 | 0.5 | 3 | 1.5 | S | H | **All business endpoints auth-guarded** (planet_mark 16, uvdb 13, slo 2, /metrics/resources); CSP header added; tenant isolation (14+ modules); `test_auth_enforcement.py` (46+ pairs); rate limiter; Bandit+pip-audit+Safety; `.semgrep.yml`; **rate limiter bug: `startswith("user:")` → should be `"token:"`** |
| D07 | Privacy & data protection | 3.5 | 6.3 | 0.9 | Medium | 3.5 | 0 | 3.2 | 2 | 6.4 | M | H | pseudonymization pepper (config.py); PII logging filter; Fernet encryption; `dpia-incidents.md`; `data-classification.md` (C1-C4); nh3 sanitization |
| D08 | Compliance readiness | 4 | 7.2 | 0.9 | Medium | 4 | 0 | 2.3 | 2 | 4.6 | M | M | ISO 27001/14001/45001/9001 domain models; UVDB Achilles; Planet Mark; IMS unification; compliance automation — no external audit reports |
| D09 | Architecture modularity | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 2 | 3.0 | M | M | Clean layered structure (api/domain/infrastructure/core); domain→api fix (core/pagination.py, core/update.py); 30 mypy overrides (GOVPLAT-004) |
| D10 | API design quality | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 2 | 3.0 | S | M | OpenAPI auto-gen; idempotency middleware; API path drift CI check; paginated responses; structured error envelope |
| D11 | Data model quality | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 2 | 3.0 | M | M | 27 model files; 4 base mixins (Timestamp, ReferenceNumber, SoftDelete, AuditTrail); CaseInsensitiveEnum; 270 FK indexes |
| D12 | Schema versioning & migrations | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 2 | 3.0 | S | M | Alembic with 63 migrations; UTC timestamps; CI runs migrations; deploy pipeline runs migrations before start |
| D13 | Observability | 4 | 7.2 | 0.9 | Medium | 4 | 0 | 2.3 | 2 | 4.6 | M | H | Azure Monitor (26+ metrics); JSON logging (pythonjsonlogger); request_id propagation; `slo-definitions.md` (5 SLOs); 3 dashboard templates; SLOMetricsMiddleware — **SLO router not mounted in `__init__.py`**; OpenCensus in deps vs OpenTelemetry in code |
| D14 | Error handling & user-safe failures | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 3 | 4.5 | S | M | 15-type domain exception hierarchy (`src/domain/exceptions.py`); unified error envelope with request_id; CORS-aware errors; circuit breaker integration; global toast notifications (frontend) |
| D15 | Testing strategy | 3.5 | 6.3 | 0.9 | Medium | 3 | +0.5 | 3.2 | 3 | 9.6 | L | H | 104+ test files; 1,582+ test functions; `test_auth_enforcement.py` (+14 endpoint pairs this cycle); 36 integration; 31 OWASP; contract tests; 14 frontend tests; **coverage 35%; no Playwright E2E specs; frontend coverage threshold 3%** |
| D16 | Test data & fixtures | 3.5 | 6.3 | 0.9 | Medium | 3.5 | 0 | 3.2 | 2 | 6.4 | M | M | 9 factory-boy factories (all with tenant_id); conftest fixtures (JWT mock, DB seed, multi-role clients); test_session fixture |
| D17 | CI quality gates | 5 | 10.0 | 1.0 | Strong | 5 | 0 | 0.0 | 3 | 0.0 | — | — | 21+ CI jobs; 12+ validators; Trojan source scan; lockfile freshness; API path drift; OpenAPI contract; SBOM; performance budget; all-checks gate |
| D18 | CD/release pipeline | 5 | 10.0 | 1.0 | Strong | 5 | 0 | 0.0 | 3 | 0.0 | — | — | Staging+prod deploy; governance signoff; deterministic SHA (3x match); DB backup; post-deploy health+security checks; rollback workflow |
| D19 | Configuration management | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 2 | 3.0 | S | M | Pydantic BaseSettings with prod validation (rejects placeholders); `.env.example`; feature flags (DB-backed + tenant overrides); env sync |
| D20 | Dependency management | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 2 | 3.0 | S | M | `requirements.txt` + `requirements.lock` with hashes; Dependabot (pip/npm/actions weekly); pip-audit strict; CycloneDX SBOM; lockfile freshness gate |
| D21 | Code quality & maintainability | 3 | 6.0 | 1.0 | Strong | 3 | 0 | 3.5 | 2 | 7.0 | L | H | Black 120; isort; flake8 (F401/F841 global ignore, max-complexity=20); mypy 30 overrides (GOVPLAT-004); Semgrep; validate_type_ignores |
| D22 | Documentation quality | 4 | 7.2 | 0.9 | Medium | 4 | 0 | 2.3 | 2 | 4.6 | M | H | README; CONTRIBUTING; SECURITY; CHANGELOG; 9 ADRs (with numbering duplicates); 25 runbooks; personas; IA docs; component inventory; SLO definitions |
| D23 | Operational runbooks | 3.5 | 6.3 | 0.9 | Medium | 3 | +0.5 | 3.2 | 2 | 6.4 | M | H | 25 runbooks; incident response contacts now filled (was TBD); on-call rotation defined (weekly primary/secondary); escalation procedures updated — some runbooks still thin/template-level |
| D24 | Data integrity & consistency | 4.5 | 9.0 | 1.0 | Strong | 4.5 | 0 | 0.5 | 3 | 1.5 | S | H | Idempotency (SHA-256 + Redis 24h); optimistic locking (InvestigationRun); ref number MAX/COUNT hybrid; 270 FK indexes; audit trail hash-chain; soft delete; tenant-scoped writes — **portal creates w/o tenant_id** |
| D25 | Scalability & capacity | 3 | 5.4 | 0.9 | Medium | 3 | 0 | 4.1 | 1 | 4.1 | L | M | DB pool 10+20; Redis caching; bulkhead pattern; manual chunk splitting (Vite) — **no load tests, no autoscaling config, no capacity plan** |
| D26 | Cost efficiency | 2 | 3.0 | 0.75 | Weak | 2 | 0 | 6.5 | 1 | 6.5 | M | L | Multi-stage Docker; `cost_alerts.py` — **no FinOps report, no Azure spend analysis** |
| D27 | I18n/L10n readiness | 3 | 4.5 | 0.75 | Weak | 3 | 0 | 5.0 | 1 | 5.0 | M | L | i18next + react-i18next; 2,118-key en.json; `i18n-check.mjs` CI gate — **no backend i18n; only English locale** |
| D28 | Analytics/telemetry | 3 | 5.4 | 0.9 | Medium | 3 | 0 | 4.1 | 1 | 4.1 | M | M | Azure Monitor (26+ metrics); SLO endpoint (route exists but not mounted); telemetry routes; web-vitals (FE); analytics baseline doc |
| D29 | Governance & decision records | 4 | 7.2 | 0.9 | Medium | 4 | 0 | 2.3 | 2 | 4.6 | S | H | 9 ADRs (numbering collision: 2x ADR-0001, 3x ADR-0003, 2x ADR-0004); CHANGELOG; release signoff; STAGE2 covenants; governance CI jobs |
| D30 | Build determinism | 5 | 10.0 | 1.0 | Strong | 5 | 0 | 0.0 | 3 | 0.0 | — | — | Docker digest pin; lockfile-first; CycloneDX SBOM; `verify_deploy_deterministic.sh`; `generate_lockfile.sh` |
| D31 | Environment parity | 3.5 | 6.3 | 0.9 | Medium | 3.5 | 0 | 3.2 | 2 | 6.4 | M | M | PG 16-alpine in all docker-compose; `environment_endpoints.json`; staging/prod both use Azure ACA — parity not formally documented |
| D32 | Supportability & operability | 4 | 7.2 | 0.9 | Medium | 3.5 | +0.5 | 2.3 | 2 | 4.6 | M | M | Health probes (/health, /healthz, /readyz with Redis); `/meta/version`; structured JSON logging with PII filter; audit trail; on-call rotation now defined — no ops dashboard |

---

## 4. Findings Register (P0/P1)

### F-001 — RESOLVED (Previously P1)

| Field | Detail |
|-------|--------|
| **Title** | Planet Mark / UVDB routes missing authentication |
| **Status** | **RESOLVED** — auth guards added to all 31 endpoints across `planet_mark.py`, `uvdb.py`, `slo.py`, `/metrics/resources` |
| **Resolution Evidence** | `src/api/routes/planet_mark.py` (16 endpoints with `CurrentUser`), `src/api/routes/uvdb.py` (13 endpoints), `src/api/routes/slo.py` (2 endpoints), `src/api/routes/health.py` (`resource_metrics`); `tests/unit/test_auth_enforcement.py` (+14 new endpoint pairs) |

### F-002 — RESOLVED (Previously P1)

| Field | Detail |
|-------|--------|
| **Title** | SLO metrics endpoint unauthenticated |
| **Status** | **RESOLVED** — `CurrentUser` added to SLO endpoints |
| **Note** | SLO router is NOT mounted in `src/api/__init__.py` or `src/main.py`; endpoints exist but are unreachable. See F-009. |

### F-003 — OPEN (Previously P1)

| Field | Detail |
|-------|--------|
| **Title** | Coverage threshold at 35% |
| **Linked CF** | CF2, CF3 |
| **Dimensions** | D15, D17 |
| **Impact** | Below industry standard (60%+); many skip decorators in tests; minimal safety net for regressions |
| **Evidence** | `pyproject.toml` `fail_under = 35`; `ci.yml` `--cov-fail-under=35` |
| **Root Cause** | Threshold lowered to unblock CI during initial uplift; never raised back |
| **Fix** | Raise to 50% within 2 sprints; target 65% within 6 sprints; write behavioral tests for critical paths |
| **Tests** | CI must enforce progressive coverage floor |
| **Observability** | Track coverage trend via `generate_quality_trend.py` |
| **Risk of Change** | Medium — may surface untestable code |
| **Rollback** | Lower threshold temporarily if blocking |

### F-004 — RESOLVED (Previously P1)

| Field | Detail |
|-------|--------|
| **Title** | No Content Security Policy header |
| **Status** | **RESOLVED** — CSP added in `src/main.py` SecurityHeadersMiddleware (L30-40) |
| **Resolution Evidence** | `response.headers["Content-Security-Policy"]` with strict defaults: `default-src 'self'`, `script-src 'self'`, `style-src 'self' 'unsafe-inline'`, `frame-ancestors 'none'` |

### F-005 — OPEN (Previously P1)

| Field | Detail |
|-------|--------|
| **Title** | Mypy type safety debt (30 overrides — GOVPLAT-004) |
| **Linked CF** | CF2, CF3 |
| **Dimensions** | D21, D09 |
| **Impact** | Type errors masked in workflow engine / risk scoring / AI services; potential runtime bugs |
| **Evidence** | `pyproject.toml` — 30 `[[tool.mypy.overrides]]` blocks |
| **Root Cause** | Rapid feature development outpaced type annotation effort |
| **Fix** | Fix critical-path modules: `workflow_engine.py`, `risk_scoring.py`, `audit_service.py` first; reduce by 5/sprint |
| **Tests** | mypy passes with fewer overrides per sprint |
| **Risk of Change** | Low-Medium |
| **Rollback** | Re-add override for specific module |

### F-006 — OPEN (Previously P1)

| Field | Detail |
|-------|--------|
| **Title** | No Playwright E2E test specs |
| **Linked CF** | CF2 |
| **Dimensions** | D15, D02 |
| **Impact** | Frontend user journeys completely untested in automated browser context |
| **Evidence** | `frontend/package.json` has `@playwright/test ^1.49.0`; `frontend/playwright.config.ts` exists; no spec files in `frontend/tests/e2e/` |
| **Root Cause** | Playwright added as dependency but specs never written |
| **Fix** | Create 5 critical-path E2E specs (login, incident CRUD, audit lifecycle, risk matrix, portal report) |
| **Tests** | Playwright CI job passes; covers 5 journeys |
| **Risk of Change** | Low (additive) |
| **Rollback** | N/A |

### F-007 — OPEN (Previously P1)

| Field | Detail |
|-------|--------|
| **Title** | Flake8 overly permissive ignores |
| **Linked CF** | CF2 |
| **Dimensions** | D21 |
| **Impact** | F401/F841 global ignores mask dead code; max-complexity=20 too high |
| **Evidence** | `.flake8` — `extend-ignore = E203, E501, E741, W291, W503, F401, F841, E711, E712`; `max-complexity = 20` |
| **Root Cause** | Ignores added to unblock CI during rapid development |
| **Fix** | Remove F401/F841 from global ignores; fix violations; reduce max-complexity to 15 |
| **Risk of Change** | Low |
| **Rollback** | Re-add ignores |

### F-008 — NEW (P1)

| Field | Detail |
|-------|--------|
| **Title** | Rate limiter authenticated user multiplier never applies |
| **Linked CF** | CF1 |
| **Dimensions** | D06, D05 |
| **Impact** | Authenticated users get same rate limits as anonymous; the 2x multiplier code path is dead |
| **Evidence** | `src/infrastructure/middleware/rate_limiter.py` L253: `is_authenticated = client_id.startswith("user:")` — but `get_client_identifier()` (L162-179) returns `"token:{hash}"` or `"ip:{ip}"`, never `"user:"` |
| **Root Cause** | Identifier prefix changed from `user:` to `token:` without updating the multiplier check |
| **Containment** | No immediate security risk (lower limits still apply); just a missed enhancement |
| **Fix** | Change L253 to `is_authenticated = client_id.startswith("token:")` |
| **Tests** | Unit test: authenticated client gets 2x limit; anonymous gets 1x |
| **Observability** | Log rate limit hits with `is_authenticated` flag |
| **Risk of Change** | Low — single line fix |
| **Rollback** | Revert the single line |

### F-009 — NEW (P1)

| Field | Detail |
|-------|--------|
| **Title** | SLO router not mounted — endpoints unreachable |
| **Linked CF** | CF4 (observability) |
| **Dimensions** | D13, D28 |
| **Impact** | SLO/SLI metrics endpoints (`/api/v1/slo/current`, `/api/v1/slo/metrics`) exist in code but are never registered on the app; `SLOMetricsMiddleware` runs but its data is inaccessible via API |
| **Evidence** | `src/api/routes/slo.py` defines router; `src/api/__init__.py` has no import of `slo`; `src/main.py` has no reference to `slo` |
| **Root Cause** | SLO module developed after the initial router aggregation; never added to `__init__.py` |
| **Containment** | SLOMetricsMiddleware still records metrics internally; no data loss |
| **Fix** | Add `from src.api.routes import slo` and `api_router.include_router(slo.router, prefix="/slo", tags=["SLO"])` to `src/api/__init__.py` |
| **Tests** | Integration test: `GET /api/v1/slo/current` returns 200/401; contract test for response schema |
| **Observability** | Monitor SLO endpoint response times |
| **Risk of Change** | Low — additive |
| **Rollback** | Remove the include_router line |

### F-010 — NEW (P1)

| Field | Detail |
|-------|--------|
| **Title** | OpenTelemetry vs OpenCensus dependency mismatch |
| **Linked CF** | CF4 |
| **Dimensions** | D13, D20 |
| **Impact** | `src/infrastructure/monitoring/azure_monitor.py` imports OpenTelemetry (`trace`, `metrics`, `FastAPIInstrumentor`), but `requirements.txt` lists `opencensus`, `opencensus-ext-azure`, `opencensus-ext-requests`. Code falls back to `_HAS_OTEL = False` in production — no distributed tracing active. |
| **Evidence** | `azure_monitor.py` L1-20 (try/except ImportError for opentelemetry); `requirements.txt` has `opencensus*`; `docs/ux/analytics-baseline.md` notes "OpenCensus (deprecated) → migration to OpenTelemetry pending" |
| **Root Cause** | Code refactored to use OpenTelemetry API but dependencies never updated |
| **Containment** | Application runs fine; just no APM/tracing |
| **Fix** | Replace `opencensus*` with `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy`, `azure-monitor-opentelemetry-exporter` in `requirements.txt`; regenerate lockfile |
| **Tests** | Verify `_HAS_OTEL = True` in startup logs; traces visible in Azure Monitor |
| **Risk of Change** | Medium — dependency swap requires testing |
| **Rollback** | Revert to opencensus deps |

### F-011 — NEW (P1)

| Field | Detail |
|-------|--------|
| **Title** | Employee portal creates records without tenant_id |
| **Linked CF** | CF3 |
| **Dimensions** | D24, D06 |
| **Impact** | `submit_quick_report` (L177-220) creates Incident/Complaint without `tenant_id`; these records are invisible to tenant-scoped queries; data integrity gap |
| **Evidence** | `src/api/routes/employee_portal.py` L195-220: `Incident()` constructor has no `tenant_id` parameter; endpoint has no auth (`db: DbSession` only) |
| **Root Cause** | Endpoint designed as public anonymous reporting; tenant association was never considered |
| **Containment** | Portal is behind rate limiter + UAT safety; records exist but can't be viewed through normal tenant-scoped queries |
| **Fix** | Option A: require minimal auth (portal token) and set tenant_id. Option B: set a configurable "default tenant" for portal submissions. Option C: add `tenant_id` as a hidden field from the portal URL (signed/encrypted). |
| **Tests** | Integration test: portal-created record visible in tenant-scoped incident list |
| **Risk of Change** | Medium — requires portal UX consideration |
| **Rollback** | Revert auth/tenant changes |

### F-012 — NEW (P2)

| Field | Detail |
|-------|--------|
| **Title** | ADR numbering collision |
| **Linked CF** | CF5 (governance) |
| **Dimensions** | D29, D22 |
| **Impact** | Duplicate ADR numbers (2× ADR-0001, 3× ADR-0003, 2× ADR-0004) create confusion; no ADR index/README |
| **Evidence** | `docs/adr/ADR-0001-production-dependencies.md`, `docs/adr/ADR-0001-migration-and-ci-strategy.md`, `docs/adr/ADR-0003-SWA-GATING-EXCEPTION.md`, `docs/adr/ADR-0003-readiness-probe.md`, `docs/ADR-0003-READINESS-PROBE-DB-CHECK.md`, `docs/adr/ADR-0004-ACA-STAGING-INFRASTRUCTURE.md`, `docs/adr/ADR-0004-TELEMETRY-CORS-QUARANTINE.md` |
| **Root Cause** | ADRs created by different contributors without checking existing numbering |
| **Fix** | Renumber to sequential ADR-0001 through ADR-0009; create `docs/adr/README.md` index; add CI check for duplicate ADR numbers |
| **Tests** | CI script validates no duplicate ADR numbers |
| **Risk of Change** | Low |
| **Rollback** | Revert renaming |

---

## 5. Evidence Gaps

### EG-01: No Load Test Results

| Field | Detail |
|-------|--------|
| **What's Missing** | Load/stress test execution results (k6, Locust, or Artillery output) |
| **Why It Blocks** | Cannot validate D04 (Performance), D25 (Scalability), D05 (Reliability under load). CM capped at 0.9 for D04/D25. |
| **Where It Should Live** | `docs/evidence/load-test-results/` or CI artifact |
| **Minimal Content** | k6 script + results for: 100 concurrent users, 95th percentile latency, error rate, throughput per critical endpoint |

### EG-02: No External Audit Reports

| Field | Detail |
|-------|--------|
| **What's Missing** | Third-party security audit, penetration test, ISO certification audit results |
| **Why It Blocks** | Cannot validate D06 (Security) and D08 (Compliance) at CM=1.0. |
| **Where It Should Live** | `docs/evidence/external-audits/` |
| **Minimal Content** | Pentest report summary, ISO audit findings, remediation status |

### EG-03: No APM Dashboard Evidence

| Field | Detail |
|-------|--------|
| **What's Missing** | Screenshots or exported JSON of Azure Monitor dashboards |
| **Why It Blocks** | D13 Observability CM capped at 0.9; dashboard templates exist but no evidence they're deployed |
| **Where It Should Live** | `docs/observability/dashboards/` |
| **Minimal Content** | Dashboard JSON exports + screenshot of live dashboard |

### EG-04: OpenTelemetry Not Active

| Field | Detail |
|-------|--------|
| **What's Missing** | Working distributed tracing (OpenTelemetry deps not installed) |
| **Why It Blocks** | D13, D28 cannot reach WCS 9.5 without distributed tracing |
| **Where It Should Live** | `requirements.txt` (opentelemetry packages) + verified trace data in Azure Monitor |
| **Minimal Content** | OpenTelemetry packages installed; trace_id in logs; traces visible in Azure Monitor |

### EG-05: Frontend Test Coverage Gap

| Field | Detail |
|-------|--------|
| **What's Missing** | Meaningful frontend test coverage (14 test files exist but threshold is 3%) |
| **Why It Blocks** | D15 Testing strategy cannot improve without frontend coverage |
| **Where It Should Live** | `frontend/src/**/__tests__/*.test.tsx` |
| **Minimal Content** | 30%+ statement coverage; tests for critical components (Dashboard, IncidentForm, AuditExecution) |

### EG-06: Staging/Production Parity Documentation

| Field | Detail |
|-------|--------|
| **What's Missing** | Formal documentation of staging vs production environment configuration differences |
| **Why It Blocks** | D31 Environment parity CM capped at 0.9 |
| **Where It Should Live** | `docs/infrastructure/environment-parity.md` |
| **Minimal Content** | Table comparing staging vs prod: compute size, DB tier, feature flags, env vars |

---

## Contradictions Resolver

### C-001: OpenTelemetry Code vs OpenCensus Dependencies

| Field | Detail |
|-------|--------|
| **Docs/Code Conflict** | `azure_monitor.py` uses OpenTelemetry API; `requirements.txt` installs OpenCensus |
| **Evidence** | `src/infrastructure/monitoring/azure_monitor.py` L1-20; `requirements.txt` (opencensus lines); `docs/ux/analytics-baseline.md` ("migration pending") |
| **Impact** | No distributed tracing in production despite code being written for it |
| **Resolution** | Treat as P1 (F-010): swap deps and verify |

### C-002: SLO Endpoints Exist but Not Mounted

| Field | Detail |
|-------|--------|
| **Docs/Code Conflict** | `src/api/routes/slo.py` defines endpoints; `slo-definitions.md` references them; they're unreachable |
| **Evidence** | `src/api/__init__.py` has no slo import; `src/main.py` has no slo reference |
| **Impact** | SLO visibility gap; middleware collects data but API can't serve it |
| **Resolution** | Treat as P1 (F-009): mount the router |

### C-003: ADR Numbering Duplicates

| Field | Detail |
|-------|--------|
| **Docs/Code Conflict** | Multiple ADRs share the same number (ADR-0001, ADR-0003, ADR-0004) |
| **Evidence** | See F-012 for full file list |
| **Impact** | Governance confusion; ADR references in other docs may point to wrong decision |
| **Resolution** | Treat as P2 (F-012): renumber and index |

