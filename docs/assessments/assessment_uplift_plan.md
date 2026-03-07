# Quality Governance Platform — World-Class Uplift Plan (Round 2)

**Assessment Date**: 2026-03-07 (Re-assessment #2)
**Target**: WCS 9.5+ across all 32 dimensions
**Current Average WCS**: 7.1 / 10.0
**Gap**: 28 of 32 dimensions below 9.5 threshold

---

## 6. Quick Wins Engine (Small Effort / High Value)

### QW-01: Add Auth to Planet Mark + UVDB Routes
- **Linked CF**: CF1, CF2 | **Dimensions**: D06
- **Why high leverage**: Closes last unauthenticated business-data routes; each endpoint needs one parameter added.
- **Exact change locations**: `src/api/routes/planet_mark.py` — add `current_user: CurrentUser` to all endpoint functions; `src/api/routes/uvdb.py` — same pattern. Add tenant_id filtering to queries.
- **Definition of Done**: All endpoints return 401 without token; tenant isolation verified.
- **Validation**: Integration test `test_planet_mark_requires_auth()`; auth enforcement regression test updated.
- **Rollback**: Revert commit.
- **Expected WCS lift**: D06 +0.3 to +0.5
- **Risk reduction**: {SEC}
- **ROI**: {Risk avoided}
- **Out-of-Scope**: Refactoring Planet Mark/UVDB business logic.

### QW-02: Add Auth to SLO Metrics Endpoint
- **Linked CF**: CF1 | **Dimensions**: D06, D13
- **Why high leverage**: Single file, single dependency addition; prevents operational metrics disclosure.
- **Exact change locations**: `src/api/routes/slo.py` — add `current_user: CurrentUser` to metric-reading endpoints; add `CurrentSuperuser` to any reset/admin endpoints.
- **Definition of Done**: SLO endpoint returns 401 without token.
- **Validation**: Unit test verifying auth requirement.
- **Rollback**: Revert commit.
- **Expected WCS lift**: D06 +0.1 to +0.2
- **Risk reduction**: {SEC}
- **ROI**: {Risk avoided}
- **Out-of-Scope**: Changing SLO metric collection logic.

### QW-03: Add Content-Security-Policy Header (Report-Only)
- **Linked CF**: CF1 | **Dimensions**: D06
- **Why high leverage**: One middleware addition completes security header suite; report-only mode is zero-risk.
- **Exact change locations**: `src/main.py` `SecurityHeadersMiddleware` — add `Content-Security-Policy-Report-Only: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' https://*.azurewebsites.net`.
- **Definition of Done**: CSP-Report-Only header present on all responses; no frontend breakage.
- **Validation**: Security test for header presence; manual verification in browser DevTools.
- **Rollback**: Remove header line.
- **Expected WCS lift**: D06 +0.2 to +0.4
- **Risk reduction**: {SEC}
- **ROI**: {Risk avoided}
- **Out-of-Scope**: Enforcing CSP (move from Report-Only to enforcing is a separate item).

### QW-04: Renumber ADRs to Unique Sequential IDs
- **Linked CF**: CF5 | **Dimensions**: D29, D22
- **Why high leverage**: 10-minute fix resolves C-003 contradiction; creates clean ADR index.
- **Exact change locations**: Rename `docs/adr/` files to sequential ADR-0001 through ADR-0008; create `docs/adr/INDEX.md` mapping titles to files; update code references.
- **Definition of Done**: All ADR files have unique sequential IDs; index document exists.
- **Validation**: No duplicate ADR numbers; all code references resolve.
- **Rollback**: Revert renames.
- **Expected WCS lift**: D29 +0.2, D22 +0.1
- **Risk reduction**: {GOV}
- **ROI**: {Quality uplift}
- **Out-of-Scope**: Writing new ADRs.

### QW-05: Remove F401/F841 from Flake8 Global Ignores
- **Linked CF**: CF3 | **Dimensions**: D21
- **Why high leverage**: Mechanical fix; catches dead code; no behavior change. Removes unused imports and variables from codebase.
- **Exact change locations**: `.flake8` — remove `F401, F841` from `extend-ignore`; fix all resulting violations (unused imports/variables).
- **Definition of Done**: Flake8 passes without F401/F841 in global ignores.
- **Validation**: CI flake8 job passes; no runtime changes.
- **Rollback**: Re-add ignores.
- **Expected WCS lift**: D21 +0.3 to +0.5
- **Risk reduction**: {GOV}
- **ROI**: {Quality uplift}
- **Out-of-Scope**: Reducing max-complexity or fixing C901 violations.

### QW-06: Create Playwright Config + 3 Critical Specs
- **Linked CF**: CF2 | **Dimensions**: D15, D02
- **Why high leverage**: Infrastructure already exists (@playwright/test installed); unlocks entire E2E testing capability.
- **Exact change locations**: `frontend/playwright.config.ts` (new), `frontend/tests/e2e/login.spec.ts`, `frontend/tests/e2e/incident-lifecycle.spec.ts`, `frontend/tests/e2e/audit-execution.spec.ts`.
- **Definition of Done**: 3 E2E specs run against local dev server; CI job configured (can be advisory initially).
- **Validation**: `npx playwright test` passes locally; specs cover login, incident CRUD, audit run.
- **Rollback**: Delete test files.
- **Expected WCS lift**: D15 +0.4 to +0.8, D02 +0.2 to +0.4
- **Risk reduction**: {REL}
- **ROI**: {Quality uplift}
- **Out-of-Scope**: Full E2E coverage of all 82 routes.

### QW-07: Create 5 Accessibility Test Files
- **Linked CF**: CF2 | **Dimensions**: D03
- **Why high leverage**: axe-helper.ts and jest-axe already installed; test infrastructure exists; each test is ~20 lines.
- **Exact change locations**: `frontend/src/pages/__tests__/Dashboard.a11y.test.tsx`, `Login.a11y.test.tsx`, `Incidents.a11y.test.tsx`, `Complaints.a11y.test.tsx`, `AuditTemplateLibrary.a11y.test.tsx`.
- **Definition of Done**: 5 a11y test files pass `npm run test:a11y`; each renders component and runs `expect(await axe(container)).toHaveNoViolations()`.
- **Validation**: `npm run test:a11y` exits 0; CI a11y gate passes.
- **Rollback**: Delete test files.
- **Expected WCS lift**: D03 +0.5 to +1.0
- **Risk reduction**: {UX}
- **ROI**: {Risk avoided}
- **Out-of-Scope**: Fixing a11y violations found by tests (separate backlog items).

### QW-08: Raise Coverage Threshold to 45%
- **Linked CF**: CF5 | **Dimensions**: D15
- **Why high leverage**: Forces writing ~30-50 new behavioral tests; prevents further coverage erosion.
- **Exact change locations**: `pyproject.toml` `fail_under = 45`; `.github/workflows/ci.yml` `--cov-fail-under=45` (2 locations).
- **Definition of Done**: CI passes at 45% coverage; no skip decorators added.
- **Validation**: CI green; coverage report shows 45%+.
- **Rollback**: Revert to 35%.
- **Expected WCS lift**: D15 +0.3 to +0.6
- **Risk reduction**: {REL}
- **ROI**: {Quality uplift}
- **Out-of-Scope**: Reaching 70%+ coverage (Horizon B/C item).

### QW-09: Document Staging vs Production Env Parity
- **Linked CF**: CF5 | **Dimensions**: D31
- **Why high leverage**: Documentation-only; captures existing tribal knowledge.
- **Exact change locations**: Create `docs/environments/parity-matrix.md` — side-by-side table of all env vars, infrastructure settings, and feature flags across dev/staging/production.
- **Definition of Done**: Parity matrix documents all env vars; differences are annotated with rationale.
- **Validation**: Document exists and is linked from README.
- **Rollback**: N/A (additive).
- **Expected WCS lift**: D31 +0.3 to +0.6
- **Risk reduction**: {REL}
- **ROI**: {Risk avoided}
- **Out-of-Scope**: Automating parity checks.

### QW-10: Add Mypy Override Count CI Gate
- **Linked CF**: CF3 | **Dimensions**: D21
- **Why high leverage**: Prevents override count from growing; forces progressive type safety improvement.
- **Exact change locations**: `.github/workflows/ci.yml` code-quality job — add step: `grep -c 'tool.mypy.overrides' pyproject.toml | awk '{if ($1 > 30) exit 1}'`; `scripts/validate_mypy_overrides.py`.
- **Definition of Done**: CI fails if mypy override count exceeds ceiling (30); ceiling reduced each sprint.
- **Validation**: Deliberately add override; verify CI fails.
- **Rollback**: Remove CI step.
- **Expected WCS lift**: D21 +0.2 to +0.4
- **Risk reduction**: {GOV}
- **ROI**: {Quality uplift}
- **Out-of-Scope**: Fixing all 30 overrides (Horizon B/C item).

### QW-11: Enforce CSP (Move from Report-Only)
- **Linked CF**: CF1 | **Dimensions**: D06
- **Why high leverage**: After QW-03 validates no frontend breakage, switch from report-only to enforcing mode.
- **Exact change locations**: `src/main.py` `SecurityHeadersMiddleware` — change `Content-Security-Policy-Report-Only` to `Content-Security-Policy`.
- **Definition of Done**: CSP enforced; no frontend console errors; no broken functionality.
- **Validation**: Manual browser test; automated security scan; no CSP violations reported.
- **Rollback**: Switch back to Report-Only.
- **Expected WCS lift**: D06 +0.1 to +0.2
- **Risk reduction**: {SEC}
- **ROI**: {Risk avoided}
- **Out-of-Scope**: Adding nonce-based script policies (future hardening).
- **Dependencies**: QW-03 must be deployed and validated first.

### QW-12: Add Operational Health Dashboard Doc
- **Linked CF**: CF4 | **Dimensions**: D32, D13
- **Why high leverage**: Dashboard JSON templates already exist (`docs/observability/dashboards/`); documenting access and usage is low-effort.
- **Exact change locations**: Create `docs/observability/operations-dashboard-guide.md` — document how to import dashboard templates, configure Azure Monitor, access live metrics.
- **Definition of Done**: Guide exists; links to 3 dashboard templates; includes screenshots or descriptions.
- **Validation**: Document exists and is linked from runbooks.
- **Rollback**: N/A (additive).
- **Expected WCS lift**: D32 +0.2, D13 +0.2
- **Risk reduction**: {REL}
- **ROI**: {Time saved}
- **Out-of-Scope**: Creating new dashboards.

---

## 7. "Critical Bars" Hardening Plan

### Gate 1: Security Hardening (P0)

**Current state**: 55/61 route modules have auth guards; tenant isolation on 14 modules; rate limiter on auth endpoints; security headers complete except CSP; Bandit, pip-audit, Safety in CI.

**Gap**: 3 route modules (planet_mark, uvdb, slo) lack authentication; no CSP header; no Semgrep/Trivy/Gitleaks in CI.

**Implementation steps**:
1. Add `CurrentUser` to planet_mark.py, uvdb.py, slo.py (QW-01, QW-02)
2. Add CSP header in report-only mode (QW-03)
3. Add auth enforcement regression test covering all 61 route modules
4. Add SAST (Semgrep is configured via `.semgrep.yml` but not in CI — add CI step)
5. Add container scanning (Trivy) to CI

**Done criteria**: All 61 route modules have auth guards verified by CI test; CSP header present; SAST and container scan in CI.

### Gate 2: Data Integrity (P0)

**Current state**: Idempotency middleware (POST); optimistic locking (investigations); reference number service (MAX/COUNT hybrid); 270 FK indexes; audit trail hash-chain.

**Gap**: No idempotency on PUT/PATCH; no concurrency tests; some write endpoints lack audit trail calls.

**Implementation steps**:
1. Extend idempotency middleware to support PUT/PATCH (conditional on Idempotency-Key header)
2. Add concurrency test: two concurrent reference number generations must produce unique sequences
3. Audit all write endpoints for audit trail calls; add missing ones
4. Add migration test: up/down roundtrip on latest 5 migrations

**Done criteria**: Idempotency on all write methods; concurrency test passes; all write endpoints have audit trail; migration roundtrip passes.

### Gate 3: Release Safety (P0)

**Current state**: Governance sign-off, deterministic SHA verification, DB backup, post-deploy security checks, rollback workflow.

**Gap**: Coverage threshold at 35%; rollback drill not current; no canary deployment.

**Implementation steps**:
1. Raise coverage to 45% (QW-08) with behavioral tests for critical paths
2. Execute and document rollback drill; update `docs/runbooks/rollback.md` with evidence
3. Add coverage trend tracking to quality trend report
4. Add migration rollback verification to CI (down migration on latest revision)

**Done criteria**: Coverage ≥45%; rollback drill documented within last 30 days; migration rollback verified in CI.

---

## 8. World-Class Roadmap (3 Horizons)

### Horizon A: Safety + Determinism + Testability (0–2 weeks)

**Entry criteria**: All changes from world-class uplift PR #266 deployed to production (DONE).

| Epic | Objective | Dimensions | CF Coverage | Tasks |
|------|-----------|------------|-------------|-------|
| A1: Complete Auth Coverage | All 61 route modules authenticated | D06 | CF1 | QW-01, QW-02, auth enforcement test for all modules |
| A2: CSP Header | Content-Security-Policy deployed | D06 | CF1 | QW-03, then QW-11 after validation |
| A3: Coverage Floor | Coverage threshold raised to 45% | D15 | CF5 | QW-08, write ~40 behavioral tests for critical paths |
| A4: E2E Foundation | Playwright configured with 3 specs | D15, D02 | CF2 | QW-06 |
| A5: A11y Testing | 5 axe-core test files created | D03 | CF2 | QW-07 |
| A6: Governance Cleanup | ADRs renumbered; override ceiling set | D29, D21 | CF5 | QW-04, QW-10 |

**Exit criteria**: All auth gaps closed; CSP deployed (report-only or enforced); coverage ≥45%; 3 E2E specs pass; 5 a11y tests pass; ADRs sequential; mypy override ceiling in CI.

**Dependencies**: None (all items independent of each other).

**Risks + mitigations**: CSP may break frontend (mitigation: report-only first); coverage raise may block CI (mitigation: write tests before raising threshold).

### Horizon B: Core Quality Uplift (2–6 weeks)

**Entry criteria**: Horizon A complete; all quick wins deployed.

| Epic | Objective | Dimensions | CF Coverage | Tasks |
|------|-----------|------------|-------------|-------|
| B1: Testing Maturity | Coverage 60%, contract tests real, Playwright 10+ specs | D15, D16 | CF2, CF5 | Write behavioral unit tests; implement contract tests from OpenAPI; expand E2E to 10 critical journeys |
| B2: Performance Baseline | Load tests documented; Lighthouse CI green | D04, D25 | CF2 | k6/Locust test for top 10 endpoints; document P95 latency; integrate Lighthouse in CI |
| B3: Security Hardening | Semgrep + Trivy in CI; CSP enforced; PUT/PATCH idempotency | D06, D24 | CF1, CF3 | Add Semgrep CI step; add Trivy container scan; extend idempotency to mutations |
| B4: Type Safety Sprint | Mypy overrides reduced from 30 to 15 | D21, D09 | CF2, CF3 | Fix type errors in workflow_engine, risk_scoring, audit_service, ai_services |
| B5: Observability Maturity | APM dashboards live; SLO alerting configured | D13, D28, D32 | CF4 | Deploy dashboard templates to Azure Monitor; configure alerts on SLO breach; document ops procedures |
| B6: Privacy & Compliance | DSAR workflow; data retention automation | D07, D08 | CF3 | Implement DSAR endpoint; add data retention cron; external audit prep |
| B7: Documentation Sprint | All runbooks reviewed; env parity documented | D22, D23, D31 | CF5 | Review 25 runbooks for completeness; QW-09; architecture diagrams |

**Exit criteria**: Coverage ≥60%; load test baselines established; Semgrep+Trivy in CI; CSP enforced; mypy overrides ≤15; SLO alerts configured; DSAR workflow; all docs reviewed.

**Dependencies**: B3 depends on A2 (CSP validation); B4 depends on A6 (override ceiling).

**Risks + mitigations**: Type fixes may reveal runtime bugs (mitigation: comprehensive test coverage from B1); performance testing may reveal bottlenecks (mitigation: address in B2).

### Horizon C: Automation, Resilience, and 5/5 Completion (6–12 weeks)

**Entry criteria**: Horizon B complete; average WCS ≥8.0.

| Epic | Objective | Dimensions | CF Coverage | Tasks |
|------|-----------|------------|-------------|-------|
| C1: Testing Excellence | Coverage 80%, chaos testing, property-based tests | D15, D16 | CF2, CF5 | Property-based tests for domain logic; chaos tests for circuit breakers; mutation testing |
| C2: Performance Optimization | P95 < 200ms; auto-scaling configured | D04, D25 | CF2, CF4 | Query optimization; read replicas; CDN for static assets; Azure autoscale rules |
| C3: Full A11y Compliance | WCAG 2.1 AA certified; screen reader tested | D03 | CF2 | Full a11y audit; remediation sprint; screen reader testing; keyboard navigation audit |
| C4: Design System Maturity | 23 components; Storybook; design tokens complete | D02 | CF2 | Build missing 11 components; Storybook catalog; design token documentation |
| C5: Zero Type Debt | Mypy overrides = 0; strict mode | D21, D09 | CF2, CF3 | Fix remaining 15 overrides; enable strict mypy; address all type errors |
| C6: FinOps + Cost Optimization | Azure spend analysis; right-sizing documented | D26 | CF4 | FinOps report; resource right-sizing; cost optimization recommendations |
| C7: I18n Completion | 2+ locales; backend i18n | D27 | CF2 | Add backend i18n framework; add 1+ additional locale; locale switching UI |
| C8: Full E2E Coverage | 30+ Playwright specs; visual regression | D15, D02 | CF2 | Expand E2E to all major journeys; add visual regression with Percy/Playwright |

**Exit criteria**: Average WCS ≥9.5; all dimensions ≥9.0; coverage ≥80%; zero mypy overrides; WCAG certified; load tests pass SLOs; cost analysis complete.

**Dependencies**: C1 depends on B1; C2 depends on B2; C5 depends on B4.

**Risks + mitigations**: I18n may require significant refactoring (mitigation: start with backend framework, add locales incrementally); WCAG certification may reveal significant remediation (mitigation: automated a11y tests catch most issues).

---

## 9. PR-Ready Backlog (Sorted by Priority Score desc, then Effort asc)

### [P1] (Effort S) (PS=12.3) Raise coverage threshold to 45% with behavioral tests
  - CF(s): CF5
  - Dimension(s): D15
  - Files/Modules: `pyproject.toml`, `.github/workflows/ci.yml`, `tests/unit/` (new test files)
  - Change Summary: Change `fail_under` to 45 in both files; write ~40 behavioral tests for critical-path functions in `src/domain/services/`, `src/api/routes/auth.py`, `src/core/security.py`.
  - Definition of Done: CI passes at 45% coverage; no new skip decorators.
  - Tests/Validation: Coverage report shows ≥45%; all new tests exercise behavior not just imports.
  - Observability: Coverage trend in quality report.
  - Rollback: Revert threshold to 35; remove tests if broken.
  - Risk of Change: MEDIUM — may require writing significant test code first.
  - Dependencies: None.
  - Owner Role: Backend Engineer
  - Risk reduction: {REL}
  - ROI: {Quality uplift}
  - Out-of-Scope: Reaching 60%+ (Horizon B).

### [P1] (Effort S) (PS=8.2) Add auth guards to planet_mark.py and uvdb.py
  - CF(s): CF1, CF2
  - Dimension(s): D06
  - Files/Modules: `src/api/routes/planet_mark.py`, `src/api/routes/uvdb.py`
  - Change Summary: Import and add `current_user: CurrentUser` parameter to all endpoint functions; add `tenant_id` filtering to queries.
  - Definition of Done: All endpoints return 401 without token; tenant isolation verified.
  - Tests/Validation: `test_planet_mark_requires_auth()`; `test_uvdb_requires_auth()`; auth enforcement test updated.
  - Observability: Log unauthenticated access attempts.
  - Rollback: Revert commit.
  - Risk of Change: LOW.
  - Dependencies: None.
  - Owner Role: Backend Engineer
  - Risk reduction: {SEC}
  - ROI: {Risk avoided}
  - Out-of-Scope: Refactoring module business logic.

### [P1] (Effort S) (PS=8.2) Add auth to SLO metrics endpoint
  - CF(s): CF1
  - Dimension(s): D06, D13
  - Files/Modules: `src/api/routes/slo.py`
  - Change Summary: Import and add `current_user: CurrentUser` to metric endpoints; add `CurrentSuperuser` to any admin endpoints.
  - Definition of Done: SLO endpoint returns 401 without token.
  - Tests/Validation: Unit test verifying auth.
  - Observability: Alert on unauthenticated SLO access.
  - Rollback: Revert commit.
  - Risk of Change: LOW.
  - Dependencies: None.
  - Owner Role: Backend Engineer
  - Risk reduction: {SEC}
  - ROI: {Risk avoided}
  - Out-of-Scope: Changing metric collection logic.

### [P1] (Effort S) (PS=8.2) Add Runbook depth review and gap fill
  - CF(s): CF5
  - Dimension(s): D23
  - Files/Modules: `docs/runbooks/` (25 files)
  - Change Summary: Review each runbook for completeness (trigger conditions, step-by-step actions, rollback, contacts); expand thin runbooks with detailed procedures.
  - Definition of Done: All 25 runbooks have minimum sections: Trigger, Steps, Verification, Rollback, Contacts.
  - Tests/Validation: Peer review by second engineer.
  - Observability: N/A (documentation).
  - Rollback: N/A (additive).
  - Risk of Change: LOW.
  - Dependencies: None.
  - Owner Role: SRE / Platform Engineer
  - Risk reduction: {REL}
  - ROI: {Time saved}
  - Out-of-Scope: Creating new runbooks for uncovered scenarios.

### [P1] (Effort S) (PS=7.0) Remove F401/F841 from flake8 global ignores
  - CF(s): CF3
  - Dimension(s): D21
  - Files/Modules: `.flake8`, multiple `src/` files with unused imports/variables
  - Change Summary: Remove `F401, F841` from `extend-ignore`; fix all resulting violations by removing unused imports and variables.
  - Definition of Done: Flake8 passes without F401/F841 in global ignores.
  - Tests/Validation: CI flake8 job passes.
  - Observability: Track violation count.
  - Rollback: Re-add ignores.
  - Risk of Change: LOW.
  - Dependencies: None.
  - Owner Role: Backend Engineer
  - Risk reduction: {GOV}
  - ROI: {Quality uplift}
  - Out-of-Scope: Fixing C901 complexity violations.

### [P1] (Effort S) (PS=7.0) Add mypy override count CI gate
  - CF(s): CF3
  - Dimension(s): D21
  - Files/Modules: `.github/workflows/ci.yml`, `scripts/validate_mypy_overrides.py` (new)
  - Change Summary: Add CI step checking mypy override count ≤ 30; create validation script.
  - Definition of Done: CI fails if override count exceeds ceiling.
  - Tests/Validation: Deliberately add override; CI fails.
  - Observability: Override count in quality trend.
  - Rollback: Remove CI step.
  - Risk of Change: LOW.
  - Dependencies: None.
  - Owner Role: Platform Engineer
  - Risk reduction: {GOV}
  - ROI: {Quality uplift}
  - Out-of-Scope: Fixing overrides (separate items).

### [P1] (Effort S) (PS=6.4) Add CSP header (report-only)
  - CF(s): CF1
  - Dimension(s): D06
  - Files/Modules: `src/main.py` (`SecurityHeadersMiddleware`)
  - Change Summary: Add `Content-Security-Policy-Report-Only` header with appropriate directives.
  - Definition of Done: CSP-RO header on all responses; no frontend breakage.
  - Tests/Validation: Security test for header; browser DevTools check.
  - Observability: CSP violation reports.
  - Rollback: Remove header.
  - Risk of Change: LOW (report-only).
  - Dependencies: None.
  - Owner Role: Backend Engineer
  - Risk reduction: {SEC}
  - ROI: {Risk avoided}
  - Out-of-Scope: Enforcing CSP (QW-11).

### [P1] (Effort S) (PS=6.4) Document staging vs production env parity
  - CF(s): CF5
  - Dimension(s): D31
  - Files/Modules: `docs/environments/parity-matrix.md` (new)
  - Change Summary: Create side-by-side table of all env vars, infrastructure, and feature flags across dev/staging/production.
  - Definition of Done: Parity matrix exists; linked from README.
  - Tests/Validation: Peer review.
  - Observability: N/A.
  - Rollback: N/A.
  - Risk of Change: LOW.
  - Dependencies: None.
  - Owner Role: Platform Engineer
  - Risk reduction: {REL}
  - ROI: {Risk avoided}
  - Out-of-Scope: Automating parity checks.

### [P1] (Effort S) (PS=4.6) Renumber ADRs to unique sequential IDs
  - CF(s): CF5
  - Dimension(s): D29, D22
  - Files/Modules: `docs/adr/*.md`, code references in `src/main.py`, `tests/`, `scripts/`
  - Change Summary: Rename 8 ADR files to ADR-0001..ADR-0008; create INDEX.md; update code references.
  - Definition of Done: All ADRs have unique IDs; index exists; code references resolve.
  - Tests/Validation: Grep for ADR references; all resolve to valid files.
  - Observability: N/A.
  - Rollback: Revert renames.
  - Risk of Change: LOW.
  - Dependencies: None.
  - Owner Role: Any Engineer
  - Risk reduction: {GOV}
  - ROI: {Quality uplift}
  - Out-of-Scope: Writing new ADRs.

### [P1] (Effort S) (PS=4.6) Add operational health dashboard guide
  - CF(s): CF4
  - Dimension(s): D32, D13
  - Files/Modules: `docs/observability/operations-dashboard-guide.md` (new)
  - Change Summary: Document how to import 3 dashboard templates; configure Azure Monitor; access live metrics.
  - Definition of Done: Guide exists; linked from runbooks.
  - Tests/Validation: Peer review.
  - Observability: N/A.
  - Rollback: N/A.
  - Risk of Change: LOW.
  - Dependencies: None.
  - Owner Role: SRE
  - Risk reduction: {REL}
  - ROI: {Time saved}
  - Out-of-Scope: Creating new dashboard templates.

### [P1] (Effort M) (PS=8.2) Create Playwright config + 3 E2E specs
  - CF(s): CF2
  - Dimension(s): D15, D02
  - Files/Modules: `frontend/playwright.config.ts` (new), `frontend/tests/e2e/` (3 new spec files)
  - Change Summary: Configure Playwright with baseURL; create specs for login flow, incident lifecycle, audit execution.
  - Definition of Done: 3 specs pass locally; CI job configured (advisory).
  - Tests/Validation: `npx playwright test` exits 0.
  - Observability: E2E pass rate in CI.
  - Rollback: Delete files.
  - Risk of Change: LOW.
  - Dependencies: Frontend dev server.
  - Owner Role: Frontend Engineer
  - Risk reduction: {REL}
  - ROI: {Quality uplift}
  - Out-of-Scope: Full E2E coverage.

### [P1] (Effort M) (PS=6.4) Create 5 a11y test files (axe-core)
  - CF(s): CF2
  - Dimension(s): D03
  - Files/Modules: `frontend/src/pages/__tests__/*.a11y.test.tsx` (5 new files)
  - Change Summary: Create axe-core tests for Dashboard, Login, Incidents, Complaints, AuditTemplateLibrary using axe-helper.ts.
  - Definition of Done: `npm run test:a11y` passes; 5 files exist.
  - Tests/Validation: CI a11y gate passes.
  - Observability: A11y test count in quality report.
  - Rollback: Delete files.
  - Risk of Change: LOW.
  - Dependencies: axe-helper.ts (exists).
  - Owner Role: Frontend Engineer
  - Risk reduction: {UX}
  - ROI: {Risk avoided}
  - Out-of-Scope: Fixing a11y violations found.

### [P1] (Effort M) (PS=6.4) Privacy: implement DSAR request endpoint
  - CF(s): CF3
  - Dimension(s): D07
  - Files/Modules: `src/api/routes/privacy.py` (new), `src/domain/services/dsar_service.py` (new)
  - Change Summary: Create DSAR (Data Subject Access Request) endpoint; export user's personal data from all modules; generate report.
  - Definition of Done: User can request their data export; admin can process DSARs; response includes all PII fields.
  - Tests/Validation: Integration test: create user data across modules; request DSAR; verify all data returned.
  - Observability: DSAR request counter metric.
  - Rollback: Remove new route + service.
  - Risk of Change: LOW (new endpoint).
  - Dependencies: Data classification doc (exists).
  - Owner Role: Backend Engineer
  - Risk reduction: {DATA}
  - ROI: {Risk avoided}
  - Out-of-Scope: Automated deletion (right to erasure) — separate item.

### [P2] (Effort S) (PS=4.6) Add Semgrep to CI pipeline
  - CF(s): CF1
  - Dimension(s): D06
  - Files/Modules: `.github/workflows/ci.yml`, `.semgrep.yml` (exists)
  - Change Summary: Add Semgrep step to security-scan job; `.semgrep.yml` already configured.
  - Definition of Done: Semgrep runs in CI; high-severity findings block merge.
  - Tests/Validation: CI job passes; verify known-safe code doesn't trigger.
  - Observability: Semgrep finding count in security report.
  - Rollback: Remove CI step.
  - Risk of Change: LOW.
  - Dependencies: None.
  - Owner Role: Platform Engineer
  - Risk reduction: {SEC}
  - ROI: {Risk avoided}
  - Out-of-Scope: Custom Semgrep rules.

### [P2] (Effort S) (PS=4.6) Add Trivy container scan to CI
  - CF(s): CF5
  - Dimension(s): D06, D20
  - Files/Modules: `.github/workflows/ci.yml`
  - Change Summary: Add Trivy step after Docker build; scan for OS and library vulnerabilities.
  - Definition of Done: Trivy runs in CI; critical vulnerabilities block merge.
  - Tests/Validation: CI job passes on current image.
  - Observability: Trivy finding count.
  - Rollback: Remove CI step.
  - Risk of Change: LOW.
  - Dependencies: Docker build step.
  - Owner Role: Platform Engineer
  - Risk reduction: {SEC}
  - ROI: {Risk avoided}
  - Out-of-Scope: Fixing found vulnerabilities (separate items).

### [P2] (Effort M) (PS=8.2) Load test baseline (k6/Locust) for top 10 endpoints
  - CF(s): CF2
  - Dimension(s): D04, D25
  - Files/Modules: `tests/performance/` (new directory), `tests/performance/k6/` or `tests/performance/locust/`
  - Change Summary: Create load test scripts for auth, incidents, audits, risks, complaints, standards, users, actions, compliance, health endpoints. Document P95 latency, throughput, error rates.
  - Definition of Done: Load test results documented in `docs/performance/baseline.md`; P95 latency known.
  - Tests/Validation: Tests reproducible; CI job configured (nightly, advisory).
  - Observability: Performance trend tracking.
  - Rollback: N/A (additive).
  - Risk of Change: LOW.
  - Dependencies: Test environment.
  - Owner Role: QA Engineer
  - Risk reduction: {PERF}
  - ROI: {Quality uplift}
  - Out-of-Scope: Performance optimization (Horizon C).

### [P2] (Effort M) (PS=7.0) Fix 10 mypy overrides in critical-path modules
  - CF(s): CF2, CF3
  - Dimension(s): D21, D09
  - Files/Modules: `src/services/workflow_engine.py`, `src/services/risk_scoring.py`, `src/domain/services/audit_service.py`, `src/domain/services/ai_*.py`, `pyproject.toml`
  - Change Summary: Fix type errors in 10 highest-priority modules; remove their mypy overrides.
  - Definition of Done: mypy override count ≤ 20; CI passes.
  - Tests/Validation: mypy passes on fixed modules; no runtime regressions.
  - Observability: Override count trend.
  - Rollback: Re-add specific overrides.
  - Risk of Change: MEDIUM — may reveal bugs.
  - Dependencies: QW-10 (override ceiling gate).
  - Owner Role: Backend Engineer
  - Risk reduction: {GOV}
  - ROI: {Quality uplift}
  - Out-of-Scope: Reaching zero overrides (Horizon C).

### [P2] (Effort M) (PS=6.4) Implement contract tests from OpenAPI spec
  - CF(s): CF2, CF4
  - Dimension(s): D15, D10
  - Files/Modules: `tests/contract/test_api_contracts.py`
  - Change Summary: Generate contract schemas from runtime OpenAPI spec; validate top 15 most-used endpoints; test request/response shape.
  - Definition of Done: 15 contract tests pass; CI contract-tests job is non-advisory.
  - Tests/Validation: Contract tests fail on incompatible schema change.
  - Observability: Contract test pass rate.
  - Rollback: N/A (additive).
  - Risk of Change: LOW.
  - Dependencies: OpenAPI spec accuracy.
  - Owner Role: Backend Engineer
  - Risk reduction: {REL}
  - ROI: {Quality uplift}
  - Out-of-Scope: Frontend-side contract verification (Horizon C).

### [P2] (Effort M) (PS=5.0) Add backend i18n framework
  - CF(s): CF2
  - Dimension(s): D27
  - Files/Modules: `src/core/i18n.py` (new), `src/locales/` (new), error messages in route handlers
  - Change Summary: Add i18n framework for backend error messages and validation responses; extract hardcoded strings.
  - Definition of Done: Backend error messages localizable; framework installed.
  - Tests/Validation: Unit test: set locale; verify translated error message.
  - Observability: N/A.
  - Rollback: Remove i18n framework.
  - Risk of Change: LOW.
  - Dependencies: None.
  - Owner Role: Backend Engineer
  - Risk reduction: {UX}
  - ROI: {Revenue protection}
  - Out-of-Scope: Adding additional locales (separate items).

### [P2] (Effort M) (PS=4.6) Add architecture diagrams to documentation
  - CF(s): CF5
  - Dimension(s): D22, D09
  - Files/Modules: `docs/architecture/` (new directory)
  - Change Summary: Create C4 diagrams (context, container, component) for the platform; document key integration points.
  - Definition of Done: 3 architecture diagrams exist; linked from README.
  - Tests/Validation: Peer review.
  - Observability: N/A.
  - Rollback: N/A.
  - Risk of Change: LOW.
  - Dependencies: None.
  - Owner Role: Architect / Senior Engineer
  - Risk reduction: {GOV}
  - ROI: {Time saved}
  - Out-of-Scope: Detailed sequence diagrams.

### [P2] (Effort M) (PS=4.1) Add SLO alerting configuration
  - CF(s): CF4
  - Dimension(s): D13, D28
  - Files/Modules: `docs/observability/slo-alerting.md` (new), Azure Monitor alert rules
  - Change Summary: Configure alerts based on SLO definitions; 50% error budget → warning, <20% → critical.
  - Definition of Done: Alerts configured in Azure Monitor; documented.
  - Tests/Validation: Trigger test alert; verify notification.
  - Observability: Alert fire rate.
  - Rollback: Remove alerts.
  - Risk of Change: LOW.
  - Dependencies: SLO definitions (exist).
  - Owner Role: SRE
  - Risk reduction: {REL}
  - ROI: {Time saved}
  - Out-of-Scope: Custom dashboards.

### [P2] (Effort M) (PS=4.1) Add data retention automation
  - CF(s): CF3
  - Dimension(s): D07, D08
  - Files/Modules: `src/domain/services/data_retention.py` (new), `src/infrastructure/tasks/retention_tasks.py` (new)
  - Change Summary: Implement configurable data retention policies per data classification level; automated soft-delete of expired data.
  - Definition of Done: Retention policies configurable; automated cleanup runs; audit trail preserved.
  - Tests/Validation: Integration test: create data, advance time, verify cleanup.
  - Observability: Retention job metrics.
  - Rollback: Disable retention task.
  - Risk of Change: MEDIUM (data deletion).
  - Dependencies: Data classification doc (exists).
  - Owner Role: Backend Engineer
  - Risk reduction: {DATA}
  - ROI: {Cost reduction}
  - Out-of-Scope: Manual data purge requests.

### [P2] (Effort L) (PS=8.2) Build comprehensive behavioral test suite (coverage 60%)
  - CF(s): CF2, CF5
  - Dimension(s): D15, D16
  - Files/Modules: `tests/unit/`, `tests/integration/` (many new test files)
  - Change Summary: Write behavioral tests for all domain services, critical route handlers, middleware, and utilities. Target coverage from 45% to 60%.
  - Definition of Done: Coverage ≥60%; zero skip decorators added; all tests test behavior not imports.
  - Tests/Validation: CI passes at 60% threshold.
  - Observability: Coverage trend.
  - Rollback: N/A.
  - Risk of Change: LOW (additive).
  - Dependencies: QW-08 (45% threshold) completed.
  - Owner Role: Backend Engineer
  - Risk reduction: {REL}
  - ROI: {Quality uplift}
  - Out-of-Scope: 80%+ coverage (Horizon C).

### [P2] (Effort L) (PS=6.5) FinOps report and Azure cost optimization
  - CF(s): CF4
  - Dimension(s): D26
  - Files/Modules: `docs/cost/` (new directory)
  - Change Summary: Analyze Azure spend; document resource utilization; identify right-sizing opportunities; implement cost alerts.
  - Definition of Done: FinOps report published; cost alerts configured.
  - Tests/Validation: Monthly cost review process documented.
  - Observability: Cost alert integration.
  - Rollback: N/A.
  - Risk of Change: LOW.
  - Dependencies: Azure billing access.
  - Owner Role: Platform Engineer / FinOps
  - Risk reduction: {COST}
  - ROI: {Cost reduction}
  - Out-of-Scope: Infrastructure migration.

### [P2] (Effort L) (PS=5.0) Design system maturity: build 11 missing components
  - CF(s): CF2
  - Dimension(s): D02, D03
  - Files/Modules: `frontend/src/components/ui/` (11 new component files)
  - Change Summary: Build missing components from component inventory: DataTable, Modal, Select, MultiSelect, Tabs, Accordion, Alert, Badge, Breadcrumb, Pagination, Skeleton.
  - Definition of Done: 11 new components exist; Radix-based; accessible; dark mode; documented.
  - Tests/Validation: Unit tests for each component; a11y tests for each.
  - Observability: N/A.
  - Rollback: N/A.
  - Risk of Change: LOW (additive).
  - Dependencies: design-tokens.css (exists).
  - Owner Role: Frontend Engineer
  - Risk reduction: {UX}
  - ROI: {Time saved}
  - Out-of-Scope: Storybook setup (separate item).

### [P2] (Effort L) (PS=4.1) Expand Playwright E2E to 10+ specs
  - CF(s): CF2
  - Dimension(s): D15, D02
  - Files/Modules: `frontend/tests/e2e/` (7+ new spec files)
  - Change Summary: Expand E2E to cover all 5 persona journeys from personas doc; add risk management, compliance, document control, user management, analytics flows.
  - Definition of Done: 10+ E2E specs pass; CI job runs on merge.
  - Tests/Validation: Full Playwright suite passes.
  - Observability: E2E pass rate.
  - Rollback: N/A.
  - Risk of Change: LOW.
  - Dependencies: QW-06 (Playwright foundation).
  - Owner Role: Frontend Engineer / QA
  - Risk reduction: {REL}
  - ROI: {Quality uplift}
  - Out-of-Scope: Visual regression testing (Horizon C).

### [P2] (Effort L) (PS=4.1) Reduce flake8 max-complexity to 15
  - CF(s): CF3
  - Dimension(s): D21
  - Files/Modules: `.flake8`, complex functions in `src/api/routes/`, `src/domain/services/`
  - Change Summary: Lower `max-complexity` from 20 to 15; refactor functions exceeding limit; remove per-file C901 ignores.
  - Definition of Done: Flake8 passes with max-complexity=15; no C901 per-file ignores.
  - Tests/Validation: CI passes; refactored functions have equivalent tests.
  - Observability: Complexity metrics.
  - Rollback: Raise back to 20.
  - Risk of Change: MEDIUM — refactoring may introduce bugs.
  - Dependencies: QW-05 (F401/F841 cleanup).
  - Owner Role: Backend Engineer
  - Risk reduction: {GOV}
  - ROI: {Quality uplift}
  - Out-of-Scope: Achieving max-complexity=10 (aspirational).

---

## 10. Acceptance-Test Matrix (World-Class Proof)

| CF | E2E Tests | Integration Tests | Unit Tests | Chaos/Failure Tests | Observability Checks | Release Checks |
|----|-----------|-------------------|------------|--------------------|--------------------|----------------|
| **CF1: Auth/AuthZ** | Login flow, role-based access, multi-tenant isolation | Auth endpoint 401/403, token refresh, password reset, tenant isolation | JWT creation/validation, password hashing, Azure AD token exchange | Token expiry during session, JWKS endpoint down, Redis unavailable | Auth success rate SLI >99.5%, failed auth counter, rate limit hit counter | Auth enforcement test in CI; all 61 modules verified |
| **CF2: Business Workflows** | Incident lifecycle (create→investigate→action→close), audit execution (template→run→response→finding), risk assessment flow | CRUD for all entities, state transitions (CAPA), reference number generation, pagination | Domain service logic, factory validation, schema validation | Concurrent reference number generation, DB connection pool exhaustion | Business metric counters (incidents created, audits completed), API latency P95 | Contract tests for top 15 endpoints; coverage ≥45% |
| **CF3: Data Writes** | Form submission with validation errors, bulk operations | Idempotency collision (duplicate POST), optimistic lock conflict, tenant-scoped writes | Reference number parsing, update utility, pagination utility | Concurrent writes to same entity, DB transaction rollback, DLQ overflow | Idempotency conflict rate, DLQ depth, write latency | Migration roundtrip test; FK constraint validation |
| **CF4: External Integrations** | Azure AD SSO login, file upload to blob | Email send (SMTP), Redis connectivity, Azure Blob operations | Circuit breaker state transitions, retry logic, cache TTL | Azure AD JWKS down, Redis down, SMTP down, Blob storage down | Circuit breaker state metric, external service latency, error rate per integration | Health check validates all dependencies; `/readyz` covers DB + Redis |
| **CF5: Release/Deploy** | Smoke test after deploy (health, version, auth) | Migration up/down roundtrip, config validation | Deploy proof script, lockfile validation, release signoff | Rollback drill (revert to previous version), migration failure recovery | Deploy duration, rollback time, SLO error budget consumption | Governance signoff; deterministic SHA; 21+ CI gates; rollback workflow |

---

## 11. World-Class Checklist (9.5+ Criteria per Dimension)

| ID | Dimension | Observable 9.5+ Criteria |
|----|-----------|--------------------------|
| D01 | Product clarity & user journeys | All 5 persona journeys mapped end-to-end; journey tests in E2E suite; OpenAPI tags match user mental model |
| D02 | UX quality & IA | 23+ reusable components in design system; Storybook catalog; consistent IA validated by user testing; Lighthouse UX score ≥90 |
| D03 | Accessibility | WCAG 2.1 AA audit report with zero critical violations; automated axe-core tests on all pages; screen reader tested; keyboard navigation complete |
| D04 | Performance (FE+BE) | P95 API latency <200ms documented; Lighthouse perf ≥90; load test baseline for top 10 endpoints; bundle size within budget |
| D05 | Reliability & resilience | Circuit breakers tested via chaos tests; DLQ depth consistently <10; 99.9% availability over 30 days; graceful degradation tested |
| D06 | Security engineering | All route modules authenticated (61/61); CSP enforced; Semgrep + Trivy + Bandit + pip-audit in CI; zero critical/high findings; penetration test report |
| D07 | Privacy & data protection | DSAR workflow operational; data retention automated; DPIA for all PII-processing modules; data classification enforced in code |
| D08 | Compliance readiness | External audit report available; ISO certification status documented; compliance automation covers all frameworks; evidence pack auto-generated |
| D09 | Architecture modularity | Zero domain→api layer violations; mypy overrides = 0; clean dependency graph; ADRs for all significant decisions |
| D10 | API design quality | OpenAPI spec validated in CI; contract tests for top 20 endpoints; consistent pagination/error/auth patterns; versioning strategy documented |
| D11 | Data model quality | All FK relationships indexed; migration coverage for all models; data dictionary generated from models; no nullable columns without documented reason |
| D12 | Schema versioning & migrations | Migration up/down roundtrip tested in CI; zero manual migration steps; migration naming convention enforced; rollback tested for latest 5 |
| D13 | Observability | APM dashboards with real data; SLO alerting configured and tested; distributed tracing across all services; custom metrics for business KPIs |
| D14 | Error handling & user-safe failures | No raw exception traces in API responses; all error codes documented; error rate SLI <1%; user-facing error messages tested |
| D15 | Testing strategy | Coverage ≥80%; E2E suite covers all persona journeys; contract tests for all public APIs; mutation testing score ≥70%; zero skip decorators |
| D16 | Test data & fixtures | Factories for all domain models; test data builder patterns; database seeding for all environments; no hardcoded test data in source |
| D17 | CI quality gates | ≥20 CI jobs with final gate; all security scans blocking; <15 min total CI time; flaky test rate <1% |
| D18 | CD/release pipeline | Blue-green or canary deployment; automated rollback on health check failure; <10 min deploy time; zero-downtime releases |
| D19 | Configuration management | All config validated at startup; feature flags with gradual rollout; config drift detection between environments; secrets rotation automated |
| D20 | Dependency management | All deps pinned with hashes; weekly automated updates; zero known vulnerabilities; SBOM generated and published |
| D21 | Code quality & maintainability | mypy strict mode (zero overrides); max-complexity ≤10; zero linter warnings; consistent code style enforced; technical debt tracked |
| D22 | Documentation quality | Architecture diagrams (C4); API docs auto-generated; runbook for every critical operation; onboarding guide; all docs reviewed within 90 days |
| D23 | Operational runbooks | Runbook for every SEV-1/2 scenario; runbooks tested quarterly; incident response time documented; post-incident review process |
| D24 | Data integrity & consistency | Idempotency on all write operations; optimistic locking on concurrent resources; referential integrity enforced; backup verified daily |
| D25 | Scalability & capacity | Load test results for 10x current traffic; autoscaling configured; read replicas for reporting; CDN for static assets |
| D26 | Cost efficiency | FinOps report published monthly; resource utilization >70%; cost per transaction tracked; optimization recommendations implemented |
| D27 | I18n/L10n readiness | 2+ locales fully translated; backend i18n framework; RTL support; locale switching tested; i18n CI gate for missing keys |
| D28 | Analytics/telemetry | Business KPI dashboards operational; web-vitals tracked in production; A/B testing framework; analytics data retention policy |
| D29 | Governance & decision records | Sequential ADR index; all ADRs have status; CHANGELOG updated per release; governance process documented; audit trail queryable |
| D30 | Build determinism | Identical builds on any CI agent; container digest verified; no floating dependencies; reproducibility tested |
| D31 | Environment parity | Parity matrix documented; automated drift detection; same versions across all environments; config differences documented |
| D32 | Supportability & operability | Ops dashboard with real-time metrics; on-call rotation documented; runbook links in alert definitions; incident response SLA met |

---

## Appendix B: Risk & ROI Tags Summary

| Tag | Count | Items |
|-----|-------|-------|
| {SEC} | 7 | QW-01, QW-02, QW-03, QW-11, Semgrep, Trivy, CSP enforcement |
| {REL} | 8 | QW-06, QW-08, QW-09, Runbook review, E2E expansion, behavioral tests, SLO alerting, dashboard guide |
| {GOV} | 5 | QW-04, QW-05, QW-10, mypy fixes, complexity reduction |
| {UX} | 3 | QW-07, a11y tests, design system |
| {DATA} | 2 | DSAR endpoint, data retention |
| {PERF} | 1 | Load test baseline |
| {COST} | 1 | FinOps report |

| ROI Tag | Count |
|---------|-------|
| Risk avoided | 9 |
| Quality uplift | 10 |
| Time saved | 4 |
| Cost reduction | 2 |
| Revenue protection | 1 |

---

## Appendix C: No-Scope-Creep Guardrails

Every backlog item includes an explicit "Out-of-Scope" line. Key guardrails:

1. **Auth fixes** (QW-01/02): Do NOT refactor module business logic.
2. **Coverage raises**: Do NOT target 80%+ in Horizon A; step incrementally (35→45→60→80).
3. **CSP**: Deploy report-only first; do NOT enforce until validated.
4. **Mypy**: Fix 10 overrides per sprint; do NOT attempt all 30 at once.
5. **E2E**: Start with 3 specs; do NOT build full suite before Playwright is validated.
6. **Design system**: Build components; do NOT set up Storybook until components are stable.
7. **Performance**: Establish baselines first; do NOT optimize until bottlenecks are identified.
8. **FinOps**: Document and analyze first; do NOT change infrastructure until recommendations reviewed.
