# Quality Governance Platform — World-Class Assessment (Round 1: Current State)

**Assessment Date**: 2026-03-07 (Re-assessment #2)
**Assessor**: Automated World-Class App Assessor + Build Director
**Platform Version**: 1.0.0 (post world-class uplift PR #266)
**Prior Assessment**: 2026-03-07 (initial — same day, pre-uplift)
**Delta**: Computed against initial assessment scorecard

---

## 1. Executive Summary

- **Average Maturity**: 3.8 / 5.0 (prior: 3.4 — **+0.4**)
- **Average World-Class Score (WCS)**: 7.1 / 10.0 (prior: 6.5 — **+0.6**)
- **Overall Confidence**: **Medium-High** — Direct evidence from 27 domain models, 61 route modules (55 with auth guards), 63 migrations, 21+ CI jobs, 25 runbooks, 8 ADRs, 104 test files with 1,568 test functions, 14 frontend test files. Gaps remain in runtime/operational evidence (no load test results, no external audit reports, coverage threshold at 35%).
- **Top 5 Strengths**:
  1. **D17 CI Quality Gates (WCS 10.0)** — 21+ CI jobs, 12+ validation scripts, all-checks gate. Evidence: `.github/workflows/ci.yml`
  2. **D18 CD/Release Pipeline (WCS 10.0)** — 5-phase deploy proof, deterministic SHA verification, governance sign-off, automated staging→production promotion. Evidence: `deploy-production.yml`, `deploy-staging.yml`
  3. **D30 Build Determinism (WCS 10.0)** — Docker digest pinning, lockfile-first install, SBOM generation, lockfile freshness gate. Evidence: `Dockerfile`, `ci.yml`
  4. **D24 Data Integrity (WCS 9.0 ↑8.0)** — Idempotency middleware, optimistic locking, tenant-scoped reference number service (race-condition fix), FK indexes on all child tables. Evidence: `middleware/idempotency.py`, `services/reference_number.py`, domain models
  5. **D14 Error Handling (WCS 8.0)** — Structured error envelope with request_id, domain exception hierarchy (15 types), CORS-aware error responses, circuit breakers. Evidence: `middleware/error_handler.py`, `domain/exceptions.py`
- **Top 5 Deficits**:
  1. **D15 Testing Strategy (WCS 5.4, PS 12.3)** — Coverage threshold 35%, contract tests partially implemented, many unit tests use `skip_on_import_error`, no Playwright E2E specs. Evidence: `pyproject.toml`, `ci.yml`
  2. **D04 Performance (WCS 5.4, PS 8.2)** — No load test results, no P95 benchmarks, no APM dashboards with real data. Size-limit and Lighthouse configured but no evidence of passing runs. Evidence: `.size-limit.json`, `lighthouserc.json`
  3. **D02 UX Quality & IA (WCS 5.4, PS 5.4)** — IA documented but 40+ pages lack systematic design system coverage. Component inventory lists 12 primitives with 11 gaps. Evidence: `docs/ux/information-architecture.md`, `docs/ux/component-inventory.md`
  4. **D03 Accessibility (WCS 4.5, PS 4.5)** — WCAG checklist exists, axe-helper and jest-axe installed, jsx-a11y enforced, but no a11y test files exist yet. Evidence: `docs/accessibility/wcag-checklist.md`, `frontend/src/test/axe-helper.ts`
  5. **D26 Cost Efficiency (WCS 3.0, PS 6.5)** — No FinOps report, no right-sizing analysis. Only indirect evidence from multi-stage Docker and cost alert scripts. Evidence: `Dockerfile`, `scripts/infra/cost_alerts.py`
- **Biggest Improvement vs Prior**: **D23 Operational Runbooks** (+2.4 WCS, from 3.0 to 5.4). 25 runbooks now exist covering deployment, rollback, database recovery, incident response, escalation, security monitoring, and module-specific procedures. Root cause: dedicated documentation sprint.
- **Biggest Regression vs Prior**: None detected. All dimensions maintained or improved.
- **World-Class Breach List (WCS < 9.5)**: D01 (7.2), D02 (5.4), D03 (4.5), D04 (5.4), D05 (8.0), D06 (8.0), D07 (6.3), D08 (7.2), D09 (8.0), D10 (8.0), D11 (8.0), D12 (8.0), D13 (7.2), D14 (8.0), D15 (5.4), D16 (6.3), D19 (8.0), D20 (8.0), D21 (6.0), D22 (7.2), D23 (5.4), D24 (9.0), D25 (5.4), D26 (3.0), D27 (4.5), D28 (5.4), D29 (7.2), D31 (6.3), D32 (6.3)

**28 of 32 dimensions breach the 9.5 threshold. 4 dimensions at or above world-class: D17, D18, D24 (near), D30.**

---

## 2. Critical Function Map

### CF1: Authentication & Authorization Boundaries

| Attribute | Detail |
|-----------|--------|
| **Blast Radius** | **HIGH** |
| **Code Locations** | `src/core/security.py` (JWT HS256), `src/core/azure_auth.py` (Azure AD B2C), `src/api/routes/auth.py` (8 endpoints), `src/api/dependencies/__init__.py` (CurrentUser, CurrentSuperuser, CurrentActiveUser DI guards), `src/core/uat_safety.py` (write protection) |
| **Dependent Services** | Azure AD (JWKS), Redis (rate limiting, token blacklist), PostgreSQL (user/role/tenant store) |
| **Current State** | **IMPROVED**: 55 of 61 route modules now have auth guards. Tenant isolation added to incidents, complaints, RTAs, policies, risks. Auth enforcement test (`tests/unit/test_auth_enforcement.py`, 113 lines) validates all protected endpoints. |
| **Remaining Risks** | **P1**: `planet_mark.py`, `uvdb.py` — no auth guards (business data routes); **P1**: `slo.py` — SLO metrics exposed without auth; **P2**: JWT uses HS256 (symmetric) — RS256 preferred for service-to-service; **P2**: No token revocation check on standard endpoints |
| **Safety Gates** | Auth enforcement regression test (CI); rate limiter on auth endpoints (10 rpm); UAT safety middleware |

### CF2: Primary Business Workflows (Top 3)

| Workflow | Blast Radius | Code Locations | Dependent Services | Current State |
|----------|-------------|----------------|-------------------|---------------|
| **Incident Lifecycle** (report → investigate → action → close) | **HIGH** | `routes/incidents.py`, `routes/investigations.py`, `routes/actions.py`, `models/incident.py` | PostgreSQL, Email, Azure Blob | Tenant isolation added; reference number race condition fixed; FK indexes added |
| **Audit Lifecycle** (template → run → response → finding → CAPA) | **HIGH** | `routes/audits.py`, `routes/capa.py`, `services/audit_service.py`, `models/audit.py` | PostgreSQL, AI (Gemini) | CAPA error messages improved; audit service observability intact |
| **Risk Assessment** (identify → assess → control → monitor) | **MEDIUM** | `routes/risks.py`, `routes/risk_register.py`, `models/risk.py` | PostgreSQL, Analytics | Tenant isolation + pagination added to controls/assessments; FK indexes added |

### CF3: Data Writes + State Transitions

| Attribute | Detail |
|-----------|--------|
| **Blast Radius** | **HIGH** |
| **Code Locations** | `middleware/idempotency.py` (POST dedup), `models/investigation.py` (optimistic locking), `services/workflow_engine.py` (state machine), `services/reference_number.py` (sequence generation), `routes/capa.py` (CAPA transitions) |
| **Current State** | **IMPROVED**: Reference number service rewritten with `MAX`/`COUNT` hybrid for collision prevention; domain→api layer violation resolved (`src/core/pagination.py`, `src/core/update.py`); actions module unbounded query capped |
| **Remaining Risks** | **P2**: No explicit idempotency on PUT/PATCH; **P2**: Workflow engine has mypy overrides (potential type-safety bugs) |

### CF4: External Integrations

| Integration | Blast Radius | Code Location | Status |
|------------|-------------|---------------|--------|
| Azure AD (SSO) | HIGH | `core/azure_auth.py` | JWKS cache TTL 1hr; no circuit breaker on JWKS fetch |
| Azure Blob Storage | MEDIUM | `infrastructure/storage.py` | Fallback to local FS in dev |
| Email (SMTP) | MEDIUM | `services/email_service.py`, `tasks/email_tasks.py` | Retry 3x with backoff |
| Google Gemini AI | LOW | `services/ai_*.py` | Non-critical; failures don't block |
| Redis | MEDIUM | `cache/redis_cache.py` | `/readyz` now checks Redis connectivity; graceful fallback |
| Push Notifications | LOW | `tasks/notification_tasks.py` | pywebpush VAPID |

### CF5: Release/Deploy + Rollback

| Attribute | Detail |
|-----------|--------|
| **Blast Radius** | **HIGH** |
| **Code Locations** | `.github/workflows/deploy-staging.yml`, `deploy-production.yml`, `rollback-production.yml`, `scripts/verify_deploy_deterministic.sh`, `scripts/governance/validate_release_signoff.py` |
| **Current State** | **STRONG**: Governance sign-off with SHA validation, 5-phase deploy proof, deterministic SHA verification, DB backup before production deploy, post-deploy security checks, automated staging→production pipeline. Successfully deployed world-class uplift PR #266 through full pipeline. |
| **Remaining Risks** | **P2**: Rollback drill evidence not current; **P2**: ACI migration container — no rollback migration verification in CI |

---

## 3. Scorecard Table

| ID | Dimension | Mat. (0-5) | WCS (0-10) | CM | Ev. Strength | Prev (0-5) | Delta | WCS Gap | CW | PS | Effort | Value | Evidence Pointers |
|----|-----------|-----------|-----------|-----|-------------|------------|-------|---------|----|----|--------|-------|-------------------|
| D01 | Product clarity & user journeys | 4 | 7.2 | 0.9 | Medium | 4 | 0 | 2.3 | 2 | 4.6 | M | M | README.md, 21 OpenAPI tags, 82 frontend routes, `docs/user-journeys/personas-and-journeys.md` (5 personas, 5 journey maps) |
| D02 | UX quality & IA | 3.5 | 5.4 | 0.75 | Weak→Medium | 3 | +0.5 | 4.1 | 1 | 4.1 | L | M | `docs/ux/information-architecture.md`, `docs/ux/component-inventory.md` (12 primitives, 11 gaps), Radix UI, Framer Motion, design-tokens.css |
| D03 | Accessibility | 3 | 4.5 | 0.75 | Weak | 2 | +1 | 5.0 | 1 | 5.0 | M | H | `docs/accessibility/wcag-checklist.md`, jsx-a11y plugin, jest-axe installed, `axe-helper.ts`, Radix UI primitives, LiveAnnouncer — but no a11y test files exist |
| D04 | Performance (FE+BE) | 3 | 5.4 | 0.9 | Medium | 3 | 0 | 4.1 | 2 | 8.2 | L | H | `database.py` (pool_size=10, max_overflow=20, statement_timeout=30s), `.size-limit.json` (350kB/250kB/50kB), `lighthouserc.json` (perf≥80), `webVitals.ts` (59 lines), no load test results |
| D05 | Reliability & resilience | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 3 | 4.5 | M | H | Circuit breakers (2 impls), retry+backoff, bulkhead (auth=50, biz=100), DLQ+replay, `/readyz` with Redis check, health probes |
| D06 | Security engineering | 4.5 | 8.0 | 0.9 | Strong | 4 | +0.5 | 1.5 | 3 | 4.5 | S | H | Tenant isolation (14 modules), auth enforcement test, rate limiter (auth 10rpm), security headers (no CSP), Bandit+pip-audit+Safety, `.semgrep.yml`, `.gitleaksignore`, `SECURITY.md` — remaining: planet_mark/uvdb/slo unauthenticated |
| D07 | Privacy & data protection | 3.5 | 6.3 | 0.9 | Medium | 3 | +0.5 | 3.2 | 2 | 6.4 | M | H | `config.py` (pseudonymization pepper), PII filter in logging, field encryption (Fernet), `docs/privacy/dpia-incidents.md`, `docs/privacy/data-classification.md` (C1-C4), nh3 HTML sanitization |
| D08 | Compliance readiness | 4 | 7.2 | 0.9 | Medium | 4 | 0 | 2.3 | 2 | 4.6 | M | M | ISO 27001/14001/45001/9001 models, UVDB, Planet Mark, IMS unification, compliance automation module — no external audit reports |
| D09 | Architecture modularity | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 2 | 3.0 | M | M | Clean layered structure (api/domain/infrastructure/core), domain→api dependency fixed (`core/pagination.py`, `core/update.py`), 30 mypy overrides (was 27) |
| D10 | API design quality | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 2 | 3.0 | S | M | OpenAPI auto-generated, idempotency middleware, API path drift check, paginated responses, structured error envelope |
| D11 | Data model quality | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 2 | 3.0 | M | M | 27 model files, 4 base mixins (Timestamp, ReferenceNumber, SoftDelete, AuditTrail), CaseInsensitiveEnum, 270 FK indexes |
| D12 | Schema versioning & migrations | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 2 | 3.0 | S | M | Alembic with 63 migrations, UTC timestamps, CI runs migrations on integration tests, deploy pipeline runs migrations before app start |
| D13 | Observability | 4 | 7.2 | 0.9 | Medium | 4 | 0 | 2.3 | 2 | 4.6 | M | H | Azure Monitor (26+ metrics), structured JSON logging, request_id propagation, `slo-definitions.md` (5 SLOs), 3 dashboard templates, SLO endpoint — no APM dashboard screenshots |
| D14 | Error handling & user-safe failures | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 3 | 4.5 | S | M | 15-type domain exception hierarchy, unified error envelope with request_id, CORS-aware errors, CAPA error messages improved, circuit breaker integration |
| D15 | Testing strategy | 3 | 5.4 | 0.9 | Medium | 3 | 0 | 4.1 | 3 | 12.3 | L | H | 104 test files, 1,568 test functions, 36 integration tests, 31 OWASP security tests, contract tests (332 lines, partially implemented), 14 frontend tests, auth enforcement test — coverage threshold 35%, no Playwright E2E |
| D16 | Test data & fixtures | 3.5 | 6.3 | 0.9 | Medium | 3 | +0.5 | 3.2 | 2 | 6.4 | M | M | 9 factory-boy factories with tenant_id, conftest fixtures (JWT mocking, DB seeding, multi-role clients), test_session fixture |
| D17 | CI quality gates | 5 | 10.0 | 1.0 | Strong | 5 | 0 | 0.0 | 3 | 0.0 | — | — | 21+ CI jobs, scripts/ (12+ validators), Trojan source scan, lockfile freshness, API path drift, OpenAPI contract, SBOM, all-checks gate |
| D18 | CD/release pipeline | 5 | 10.0 | 1.0 | Strong | 5 | 0 | 0.0 | 3 | 0.0 | — | — | Staging + production deploy, governance sign-off, deterministic SHA, DB backup, post-deploy security checks, rollback workflow |
| D19 | Configuration management | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 2 | 3.0 | S | M | Pydantic BaseSettings with production validation, `.env.example`, feature flags model + API, env sync verification |
| D20 | Dependency management | 4 | 8.0 | 1.0 | Strong | 4 | 0 | 1.5 | 2 | 3.0 | S | M | `requirements.txt` + `requirements.lock` with hashes, Dependabot (pip/npm/actions weekly), pip-audit strict, SBOM (CycloneDX), lockfile freshness gate |
| D21 | Code quality & maintainability | 3 | 6.0 | 1.0 | Strong | 3 | 0 | 3.5 | 2 | 7.0 | L | H | Black (120), isort, flake8 (max-complexity=20), mypy (30 overrides tagged GOVPLAT-004), Semgrep, validate_type_ignores — overrides still high |
| D22 | Documentation quality | 4 | 7.2 | 0.9 | Medium | 3 | +1 | 2.3 | 2 | 4.6 | M | H | README, CONTRIBUTING, SECURITY, CHANGELOG, 8 ADRs, 25 runbooks, personas, IA docs, component inventory, SLO definitions — some ADRs are duplicates/overlapping |
| D23 | Operational runbooks | 3 | 5.4 | 0.9 | Medium | 2 | +1 | 4.1 | 2 | 8.2 | M | H | 25 runbooks in `docs/runbooks/`: deployment, rollback, DB recovery, incident response, escalation, security monitoring, audit observability, module-specific — some are thin/template-level |
| D24 | Data integrity & consistency | 4.5 | 9.0 | 1.0 | Strong | 4 | +0.5 | 0.5 | 3 | 1.5 | S | H | Idempotency (SHA-256 dedup), optimistic locking, reference number service (MAX/COUNT hybrid), FK indexes on all child tables (270 indexes), audit trail hash-chain, soft delete, tenant-scoped writes |
| D25 | Scalability & capacity | 3 | 5.4 | 0.9 | Medium | 3 | 0 | 4.1 | 1 | 4.1 | L | M | DB pooling (10+20 overflow), Redis caching, bulkhead pattern, unbounded query caps — no load test results, no autoscaling evidence |
| D26 | Cost efficiency | 2 | 3.0 | 0.75 | Weak | 2 | 0 | 6.5 | 1 | 6.5 | M | L | Multi-stage Docker, `cost_alerts.py` — no FinOps report, no Azure spend analysis |
| D27 | I18n/L10n readiness | 3 | 4.5 | 0.75 | Weak | 3 | 0 | 5.0 | 1 | 5.0 | M | L | i18next with 2,118-line en.json, `i18n-check.mjs` CI gate — no backend i18n, only English locale |
| D28 | Analytics/telemetry | 3 | 5.4 | 0.9 | Medium | 3 | 0 | 4.1 | 1 | 4.1 | M | M | Azure Monitor (26+ metrics), SLO endpoint (`routes/slo.py`), telemetry routes, web-vitals (FE), analytics baseline doc — no dashboard screenshots |
| D29 | Governance & decision records | 4 | 7.2 | 0.9 | Medium | 3 | +1 | 2.3 | 2 | 4.6 | S | H | 8 ADRs, CHANGELOG, release signoff, STAGE2 covenants, CI governance jobs, `validate_audit_acceptance_pack.py`, `validate_release_signoff.py` |
| D30 | Build determinism | 5 | 10.0 | 1.0 | Strong | 5 | 0 | 0.0 | 3 | 0.0 | — | — | Docker digest pin, lockfile-first, SBOM (CycloneDX), `verify_deploy_deterministic.sh`, `generate_lockfile.sh` |
| D31 | Environment parity | 3.5 | 6.3 | 0.9 | Medium | 3 | +0.5 | 3.2 | 2 | 6.4 | M | M | Both docker-compose files now use PG 16-alpine, `environment_endpoints.json`, staticwebapp.config.json — staging vs production env var parity not documented |
| D32 | Supportability & operability | 3.5 | 6.3 | 0.9 | Medium | 3 | +0.5 | 3.2 | 2 | 6.4 | M | M | Health probes (`/health`, `/healthz`, `/readyz` with Redis), `/meta/version`, structured logging with PII filter, audit trail — no ops dashboard, no on-call rotation doc |

---

## 4. Findings Register (P0/P1)

### F-001 — Planet Mark / UVDB Routes Missing Authentication

- **Priority**: P1 (downgraded from P0 — these are domain-specific modules, not admin/tenant)
- **Linked CF**: CF1, CF2
- **Dimensions**: D06 (Security)
- **Impact**: Business-sensitive carbon reporting data and UVDB audit data accessible without authentication. Competitor/unauthorized access risk.
- **Evidence**: `src/api/routes/planet_mark.py` — imports `DbSession` but no `CurrentUser`; `src/api/routes/uvdb.py` — same pattern. Neither module filters by `tenant_id`.
- **Root Cause**: These modules were built as standalone features and auth was never added.
- **Containment**: Add `CurrentUser` dependency to all endpoints in both modules.
- **Fix**: Add auth guards + tenant isolation; update integration tests.
- **Tests/Validation**: `test_planet_mark_requires_auth()`, `test_uvdb_requires_auth()` — verify 401 without token.
- **Observability**: Log unauthenticated access attempts to these endpoints.
- **Risk of Change**: LOW — additive auth guards.
- **Rollback**: Revert commit.

### F-002 — SLO Metrics Endpoint Unauthenticated

- **Priority**: P1
- **Linked CF**: CF1, CF4
- **Dimensions**: D06 (Security), D13 (Observability)
- **Impact**: Internal SLO/SLI metrics (availability, latency P99, error rate) exposed without authentication. Information disclosure of operational posture.
- **Evidence**: `src/api/routes/slo.py` — `router = APIRouter()` with no auth dependency; endpoints expose live traffic metrics.
- **Root Cause**: SLO endpoint designed as internal/monitoring endpoint without considering external exposure.
- **Containment**: Add `CurrentUser` dependency; consider `CurrentSuperuser` for sensitive operational metrics.
- **Fix**: Add auth; optionally split into public health vs private SLO endpoints.
- **Tests/Validation**: Verify SLO endpoint returns 401 without token.
- **Observability**: Alert on unauthenticated SLO access.
- **Risk of Change**: LOW — may require monitoring tool auth configuration.
- **Rollback**: Revert auth requirement.

### F-003 — Coverage Threshold at 35% (Contradiction with Quality Aspirations)

- **Priority**: P1
- **Linked CF**: CF5 (Release)
- **Dimensions**: D15 (Testing), D17 (CI)
- **Impact**: 35% coverage threshold provides minimal safety net. Both `pyproject.toml` and `ci.yml` now aligned at 35%, but this is below industry standard (70-80%). Contract tests partially implemented but still gaps. 1,568 test functions exist but many use skip decorators.
- **Evidence**: `pyproject.toml` `fail_under = 35`; `ci.yml` `--cov-fail-under=35`; `tests/unit/test_services.py` uses skip decorators.
- **Root Cause**: Threshold was lowered to unblock CI after world-class uplift changes; never raised back.
- **Containment**: Raise to 45% within 1 sprint; target 60% within 3 sprints.
- **Fix**: Write behavioral tests for critical paths; fix skip decorators; add missing unit tests for new `src/core/` modules.
- **Tests/Validation**: CI must enforce progressive coverage floor.
- **Observability**: Track coverage trend via `generate_quality_trend.py`.
- **Risk of Change**: MEDIUM — raising threshold blocks CI until tests written.
- **Rollback**: Lower threshold temporarily if blocking critical fixes.

### F-004 — No Content Security Policy Header

- **Priority**: P1
- **Linked CF**: CF1
- **Dimensions**: D06 (Security)
- **Impact**: Without CSP, the application is more vulnerable to XSS attacks. Other security headers are comprehensive (X-Frame-Options, HSTS, Referrer-Policy, Permissions-Policy, COOP, CORP) but CSP is missing.
- **Evidence**: `src/main.py` `SecurityHeadersMiddleware` — no `Content-Security-Policy` header set. Confirmed by grep: zero matches for "Content-Security-Policy" in `src/`.
- **Root Cause**: CSP requires careful tuning to avoid breaking legitimate frontend functionality; was deferred.
- **Containment**: Add report-only CSP first (`Content-Security-Policy-Report-Only`).
- **Fix**: Implement strict CSP with nonces for inline scripts; configure report-uri.
- **Tests/Validation**: Security test verifying CSP header presence; report-only mode validation.
- **Observability**: CSP violation reports via report-uri endpoint.
- **Risk of Change**: MEDIUM — overly strict CSP can break frontend; use report-only first.
- **Rollback**: Remove CSP header.

### F-005 — Mypy Type Safety Debt (30 Overrides — GOVPLAT-004)

- **Priority**: P1
- **Linked CF**: CF2, CF3
- **Dimensions**: D21 (Code Quality), D09 (Architecture)
- **Impact**: 30 modules have mypy error codes disabled. Type errors in workflow engine, risk scoring, AI services, and route handlers may mask runtime bugs. Override count increased from 27 to 30 during uplift.
- **Evidence**: `pyproject.toml` — 30 `[[tool.mypy.overrides]]` blocks tagged GOVPLAT-004.
- **Root Cause**: Rapid feature development outpaced type annotation; new core modules added without resolving existing debt.
- **Containment**: Prioritize fixing critical-path modules: `workflow_engine.py`, `risk_scoring.py`, `audit_service.py`.
- **Fix**: Resolve type errors module-by-module; set ceiling on override count; add CI gate on override count.
- **Tests/Validation**: mypy passes with fewer overrides per sprint; zero overrides target for Horizon C.
- **Observability**: Track override count in quality trend.
- **Risk of Change**: LOW-MEDIUM — type fixes may reveal actual bugs.
- **Rollback**: Re-add override for specific module if regression.

### F-006 — No Playwright E2E Test Specs

- **Priority**: P1
- **Linked CF**: CF2
- **Dimensions**: D15 (Testing), D02 (UX)
- **Impact**: `@playwright/test` is installed as devDependency but no `playwright.config.ts` or spec files exist. Frontend user journeys are completely untested in an automated browser context.
- **Evidence**: `frontend/package.json` includes `@playwright/test`; no `*.spec.ts` or `playwright.config.*` files found anywhere in repo.
- **Root Cause**: Playwright was added as dependency in anticipation of E2E tests but never configured.
- **Containment**: Create `playwright.config.ts` and 3 critical-path specs (login, incident creation, audit execution).
- **Fix**: Build E2E suite covering top 5 user journeys from `docs/user-journeys/personas-and-journeys.md`.
- **Tests/Validation**: Playwright CI job passes; covers login, CRUD, multi-step workflows.
- **Observability**: E2E test pass rate in CI dashboard.
- **Risk of Change**: LOW — additive.
- **Rollback**: N/A.

### F-007 — Flake8 Overly Permissive Ignores

- **Priority**: P1
- **Linked CF**: CF3
- **Dimensions**: D21 (Code Quality)
- **Impact**: Global ignores include `F401` (unused imports) and `F841` (unused variables) which mask dead code. Per-file ignores disable `C901` (complexity) on many modules. Max complexity set to 20 (industry standard: 10-15).
- **Evidence**: `.flake8` — `extend-ignore = E203, E501, E741, W291, W503, F401, F841, E711, E712`; per-file ignores on 20+ modules for F401, C901.
- **Root Cause**: Ignores added to unblock CI during rapid development.
- **Containment**: Remove F401 and F841 from global ignores; fix violations.
- **Fix**: Reduce max-complexity to 15; fix or document complex functions; remove per-file C901 ignores progressively.
- **Tests/Validation**: Flake8 CI job passes with tightened rules.
- **Observability**: Track flake8 violation count in quality trend.
- **Risk of Change**: LOW — fixing unused imports/variables is mechanical.
- **Rollback**: Re-add ignores.

---

## 5. Evidence Gaps

| # | What's Missing | Why It Blocks | Where It Should Live | Minimal Content |
|---|---------------|--------------|---------------------|-----------------|
| EG-01 | Load test results / performance benchmarks | Blocks D04/D25 above WCS 6.0; no evidence of P95 latency or throughput | `docs/performance/` | k6/Locust results for top 5 endpoints; P95 latency, throughput, error rates under load |
| EG-02 | Accessibility test files (axe-core) | Blocks D03 above WCS 5.0; infrastructure exists but no tests | `frontend/src/**/*.a11y.test.tsx` | axe-core tests for Dashboard, Login, Forms, Tables, Navigation |
| EG-03 | Playwright E2E test specs | Blocks D15 above WCS 6.0 and D02 above WCS 6.0 | `frontend/tests/e2e/` | Config + specs for login, incident CRUD, audit execution |
| EG-04 | External audit/certification reports | Blocks D08 confidence to Strong | `docs/compliance/` | ISO certification status, external audit findings |
| EG-05 | FinOps / cost analysis report | Blocks D26 above WCS 4.0 | `docs/cost/` | Azure spend breakdown, right-sizing analysis |
| EG-06 | APM dashboard screenshots / live dashboard links | Blocks D13 above WCS 8.0 | `docs/observability/dashboards/` | Evidence of operational dashboards with real data |
| EG-07 | Coverage trend data / historical reports | Blocks D15 confidence | `docs/quality/` | Coverage reports showing trend over time |
| EG-08 | Staging vs production env variable parity doc | Blocks D31 above WCS 7.0 | `docs/environments/` | Side-by-side env var comparison |

---

## Appendix A: Contradictions Resolver

### C-001 — Coverage Threshold (Resolved)
- **Docs say**: `pyproject.toml` `fail_under = 35`
- **Code does**: `ci.yml` enforces `--cov-fail-under=35`
- **Status**: ALIGNED (both at 35) — but 35 is below aspiration. Treat as F-003.

### C-002 — Postgres Version (Resolved)
- **Docs say**: README specifies PostgreSQL 16+
- **Code does**: Both docker-compose files now use `postgres:16-alpine`
- **Status**: RESOLVED in world-class uplift.

### C-003 — ADR Numbering Overlap
- **Docs say**: ADR-0001 through ADR-0004 should be sequential
- **Code does**: Duplicate numbering — e.g. `ADR-0001-production-dependencies.md` AND `ADR-0001-migration-and-ci-strategy.md`; `ADR-0003-readiness-probe.md` AND `ADR-0003-SWA-GATING-EXCEPTION.md`
- **Resolution**: Renumber ADRs to unique sequential IDs; add ADR index document.
