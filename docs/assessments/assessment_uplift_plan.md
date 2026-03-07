# Quality Governance Platform — World-Class Uplift Plan (Round 2)

**Date:** 2026-03-07 (Post Top-15 Uplift)
**Target:** WCS 9.5+ across all applicable dimensions

---

## 6. Quick Wins Engine (Small Effort / High Value — Top 12)

### QW-1: Fix rate limiter auth prefix bug
- **CF:** CF1 | **Dim:** D06, D05
- **Leverage:** Single-line fix restores 2x rate limits for authenticated users
- **Files:** `src/infrastructure/middleware/rate_limiter.py:253`
- **DoD:** `is_authenticated` returns True for token-bearing requests
- **Validation:** Unit test asserting `"token:abc".startswith("token:")` path is exercised
- **Rollback:** Revert one line
- **WCS lift:** D06 +0.2 (9.0 → 9.2)

### QW-2: Standardize auth route errors to api_error()
- **CF:** CF1 | **Dim:** D14, D10, D21
- **Leverage:** Last major route file with plain-string errors
- **Files:** `src/api/routes/auth.py` — 7 HTTPException calls
- **DoD:** All auth errors return `{"error": {"code", "message"}}` envelope
- **Validation:** Integration test asserting 401/403 bodies contain `code` field
- **Rollback:** Revert auth.py
- **WCS lift:** D14 +0.3, D21 +0.3

### QW-3: Fix OpenTelemetry dependencies
- **CF:** CF4 | **Dim:** D13, D28
- **Leverage:** Enables distributed tracing with zero code changes (code already written)
- **Files:** `requirements.txt` — replace opencensus with opentelemetry-sdk, opentelemetry-instrumentation-fastapi, azure-monitor-opentelemetry-exporter
- **DoD:** `_HAS_OTEL = True` at runtime; traces visible in Azure Monitor
- **Validation:** Health endpoint returns `tracing: enabled`; Azure Monitor shows spans
- **Rollback:** Revert requirements.txt; `_HAS_OTEL = False` graceful fallback
- **WCS lift:** D13 +1.5 (6.3 → 7.8), D28 +0.8

### QW-4: Renumber ADRs sequentially
- **CF:** — | **Dim:** D29
- **Leverage:** Eliminates governance confusion from duplicate numbers
- **Files:** `docs/adr/ADR-0001-*.md` through `ADR-0008-*.md`
- **DoD:** 8 unique ADR numbers; no collisions
- **Validation:** `ls docs/adr/ | grep -oP 'ADR-\d+' | sort -u | wc -l` equals file count
- **Rollback:** Rename back
- **WCS lift:** D29 +0.5 (7.2 → 7.7)

### QW-5: Add 3 accessibility test files
- **CF:** CF2a | **Dim:** D03
- **Leverage:** Activates existing jest-axe + jsx-a11y infrastructure
- **Files:** `frontend/src/pages/Dashboard.a11y.test.tsx`, `Login.a11y.test.tsx`, `Incidents.a11y.test.tsx`
- **DoD:** `npm run test:a11y` passes with 3 specs; axe-core finds 0 violations
- **Validation:** CI `frontend-tests` job runs a11y suite
- **Rollback:** Delete test files
- **WCS lift:** D03 +1.0 (4.5 → 5.5)

### QW-6: Raise coverage threshold to 50%
- **CF:** CF2 | **Dim:** D15
- **Leverage:** Forces coverage growth with each PR
- **Files:** `pyproject.toml:217` — change `fail_under = 35` to `fail_under = 50`; add tests for `src/api/routes/auth.py`, `src/domain/services/incident_service.py`
- **DoD:** CI passes at 50% threshold
- **Validation:** `pytest --cov --cov-fail-under=50`
- **Rollback:** Revert threshold
- **WCS lift:** D15 +0.8 (6.3 → 7.1)

### QW-7: Assign tenant_id in portal endpoints
- **CF:** CF3 | **Dim:** D24, D06
- **Leverage:** Closes data isolation gap for portal-submitted records
- **Files:** `src/api/routes/employee_portal.py`
- **DoD:** Portal-created incidents/complaints have `tenant_id` set
- **Validation:** Integration test asserting portal records have non-null tenant_id
- **Rollback:** Revert portal route changes
- **WCS lift:** D24 +0.2 (9.0 → 9.2)

### QW-8: Add structured request logging correlation
- **CF:** CF4 | **Dim:** D13, D32
- **Leverage:** Request logger already exists; add user_id and tenant_id correlation
- **Files:** `src/infrastructure/middleware/request_logger.py`
- **DoD:** Logs include `user_id`, `tenant_id`, `request_id` fields
- **Validation:** grep structured log output for all three fields
- **Rollback:** Revert middleware
- **WCS lift:** D13 +0.3, D32 +0.3

### QW-9: Add Gitleaks to CI
- **CF:** CF5 | **Dim:** D06
- **Leverage:** Prevents secret leakage; fills security scan gap
- **Files:** `.github/workflows/ci.yml` — add gitleaks step; create `.gitleaks.toml`
- **DoD:** CI blocks on detected secrets
- **Validation:** CI job passes with `.gitleaks.toml` allowlist
- **Rollback:** Remove CI step
- **WCS lift:** D06 +0.3 (9.0 → 9.3)

### QW-10: Add health check dependency verification to runbook
- **CF:** CF5 | **Dim:** D23, D32
- **Leverage:** Closes operational gap with low effort
- **Files:** `docs/runbooks/health-check-triage.md`
- **DoD:** Runbook covers /readyz failure → DB/Redis triage → escalation
- **Validation:** Peer review by ops team
- **Rollback:** N/A (docs only)
- **WCS lift:** D23 +0.3 (6.3 → 6.6)

### QW-11: Add input sanitization evidence (verify nh3 usage)
- **CF:** CF3 | **Dim:** D06, D07
- **Leverage:** nh3 is installed but usage unconfirmed; wire into user-input fields
- **Files:** `src/api/schemas/` — add `nh3.clean()` validator on description/notes fields
- **DoD:** HTML tags stripped from user-submitted text fields
- **Validation:** Unit test with `<script>alert(1)</script>` input
- **Rollback:** Remove validator
- **WCS lift:** D06 +0.2, D07 +0.3

### QW-12: Create Playwright login + incident CRUD spec
- **CF:** CF1, CF2a | **Dim:** D15
- **Leverage:** First real E2E browser test; validates critical path end-to-end
- **Files:** `frontend/e2e/incident-crud.spec.ts`
- **DoD:** Playwright test logs in, creates incident, verifies it appears in list
- **Validation:** CI e2e-tests job passes
- **Rollback:** Delete spec file
- **WCS lift:** D15 +0.5 (6.3 → 6.8)

---

## 7. Critical Bars Hardening Plan

### Gate 1: Secrets & AuthZ (CF1)
- **Current:** Auth multiplier bug, plain string errors in auth
- **Gap:** Rate limiter prefix mismatch; auth errors inconsistent
- **Steps:** QW-1 (fix prefix), QW-2 (api_error in auth), QW-9 (Gitleaks CI)
- **Done:** Rate limiter logs show `authenticated_multiplier` applied; auth 401s return structured JSON; Gitleaks CI green

### Gate 2: Data Integrity (CF3)
- **Current:** Portal tenant_id gap; status transitions validated
- **Gap:** Portal records may lack tenant isolation
- **Steps:** QW-7 (portal tenant_id), verify nh3 sanitization (QW-11)
- **Done:** `SELECT * FROM incidents WHERE tenant_id IS NULL` returns 0 rows; HTML injection blocked

### Gate 3: Release Safety (CF5)
- **Current:** Governance signoff, SHA validation, staging gate
- **Gap:** No secret scanning in CI; health check runbook missing
- **Steps:** QW-9 (Gitleaks), QW-10 (health runbook)
- **Done:** Gitleaks CI step passes; runbook published and peer-reviewed

---

## 8. World-Class Roadmap (3 Horizons)

### Horizon A (0–2 weeks): Safety + Determinism + Testability

**Epics:**
1. **Security hardening** — QW-1, QW-2, QW-9, QW-11 | CF1, CF3 | D06, D14
2. **Observability fix** — QW-3 (OTel deps) | CF4 | D13, D28
3. **Testing foundation** — QW-5 (a11y tests), QW-6 (coverage 50%), QW-12 (Playwright) | CF2 | D03, D15

**Entry criteria:** All CI jobs passing; current assessment accepted
**Exit criteria:** Rate limiter fixed; auth errors structured; OTel traces visible; coverage ≥50%; 3 a11y tests; 1 Playwright spec
**Dependencies:** None — all independent
**Risks:** OTel package conflicts → mitigate: pin exact versions matching azure-monitor-opentelemetry
**Expected WCS:** Average 7.5 → 8.0

### Horizon B (2–6 weeks): Core Quality Uplift

**Epics:**
4. **Code quality** — Resolve 15 of 30 mypy overrides; add factory-boy patterns for test data | D21, D16
5. **Performance baseline** — Run k6 load test; establish P95/P99 baselines; add performance budget CI | D04, D25
6. **Operational maturity** — Health triage runbook (QW-10); alerting integration (PagerDuty/OpsGenie); SLO burn-rate alerts | D23, D32, D13
7. **Documentation** — Renumber ADRs (QW-4); add API versioning strategy ADR; update CHANGELOG | D22, D29

**Entry criteria:** Horizon A exit criteria met
**Exit criteria:** Mypy overrides ≤ 15; load test report published; PagerDuty configured; ADRs sequential
**Dependencies:** Horizon A (OTel for SLO alerts)
**Risks:** Load test may reveal bottlenecks → mitigate: allocate buffer for fixes
**Expected WCS:** Average 8.0 → 8.5

### Horizon C (6–12 weeks): Automation, Resilience, Completion

**Epics:**
8. **Full E2E coverage** — Playwright specs for all critical journeys (audit, complaint, risk, portal) | D15
9. **Resilience testing** — Circuit breaker for external services; chaos tests (DB failover, Redis unavailable) | D05, D25
10. **i18n backend** — Error message catalog; locale-aware date formatting | D27
11. **FinOps** — Azure cost analysis dashboard; resource right-sizing; cost alerts | D26
12. **Coverage 70%** — Systematic test gap filling; mutation testing pilot | D15, D16

**Entry criteria:** Horizon B exit criteria met
**Exit criteria:** 5+ Playwright specs; circuit breaker tested; backend i18n for errors; cost dashboard live; coverage ≥70%
**Dependencies:** Horizon B (performance baseline, operational maturity)
**Risks:** i18n scope creep → mitigate: errors-only first, no full translation
**Expected WCS:** Average 8.5 → 9.0+

---

## 9. PR-Ready Backlog

### Priority 0 (Critical Path)

- [P0] (Effort S) (PS=1.5) Fix rate limiter auth prefix bug
  - CF(s): CF1
  - Dimension(s): D06, D05
  - Files/Modules: `src/infrastructure/middleware/rate_limiter.py:253`
  - Change Summary: Replace `"user:"` with `"token:"` in startswith check
  - Definition of Done: Authenticated requests receive 2x rate limit
  - Tests/Validation: Unit test asserting token-prefixed client_id activates multiplier
  - Observability: Log `rate_limit.authenticated_multiplier_applied` event
  - Rollback: Revert one line
  - Risk of Change: Low
  - Dependencies: None
  - Owner Role: Backend engineer
  - Risk Reduction: {SEC, REL}
  - ROI: {Risk avoided}
  - Out-of-Scope: Changing rate limit values; adding per-user limits

### Priority 1 (High)

- [P1] (Effort S) (PS=9.6) Raise coverage threshold to 50% + add tests
  - CF(s): CF2a-c
  - Dimension(s): D15
  - Files/Modules: `pyproject.toml:217`, `tests/unit/test_auth_routes.py` (new), `tests/unit/test_incident_service.py` (new)
  - Change Summary: Change fail_under=35 to 50; add unit tests for uncovered auth and service code
  - Definition of Done: `pytest --cov --cov-fail-under=50` passes
  - Tests/Validation: CI unit-tests job green at 50%
  - Observability: Coverage trend tracked via quality-trend CI job
  - Rollback: Lower threshold back
  - Risk of Change: Low
  - Dependencies: None
  - Owner Role: Backend engineer
  - Risk Reduction: {REL}
  - ROI: {Quality uplift}
  - Out-of-Scope: Reaching 70%+ in this PR

- [P1] (Effort S) (PS=6.4) Fix OpenTelemetry dependencies
  - CF(s): CF4
  - Dimension(s): D13, D28
  - Files/Modules: `requirements.txt:48-52`
  - Change Summary: Replace opencensus packages with opentelemetry-sdk, opentelemetry-instrumentation-fastapi, azure-monitor-opentelemetry-exporter
  - Definition of Done: `_HAS_OTEL = True` at runtime; Azure Monitor shows distributed traces
  - Tests/Validation: Import test; smoke test asserting tracing is active
  - Observability: Traces visible in Azure Monitor
  - Rollback: Revert requirements.txt; graceful fallback via try/except
  - Risk of Change: Medium (dependency resolution)
  - Dependencies: None
  - Owner Role: Platform engineer
  - Risk Reduction: {REL}
  - ROI: {Quality uplift, Risk avoided}
  - Out-of-Scope: Custom span instrumentation; trace sampling tuning

- [P1] (Effort S) (PS=6.4) Assign tenant_id in portal endpoints
  - CF(s): CF3
  - Dimension(s): D24, D06
  - Files/Modules: `src/api/routes/employee_portal.py`
  - Change Summary: Set tenant_id on portal-created records from portal auth context
  - Definition of Done: All portal-created records have non-null tenant_id
  - Tests/Validation: Integration test asserting tenant_id populated
  - Observability: Audit event includes tenant_id
  - Rollback: Revert portal route changes
  - Risk of Change: Low
  - Dependencies: None
  - Owner Role: Backend engineer
  - Risk Reduction: {SEC, DATA}
  - ROI: {Risk avoided}
  - Out-of-Scope: Multi-tenant portal login

- [P1] (Effort S) (PS=5.0) Standardize auth errors to api_error()
  - CF(s): CF1
  - Dimension(s): D14, D10, D21
  - Files/Modules: `src/api/routes/auth.py`
  - Change Summary: Replace 7 plain-string HTTPException details with api_error(ErrorCode.*, ...)
  - Definition of Done: All auth error responses contain structured JSON envelope
  - Tests/Validation: Integration tests asserting 401/403 bodies have `code` field
  - Observability: N/A
  - Rollback: Revert auth.py
  - Risk of Change: Low
  - Dependencies: None
  - Owner Role: Backend engineer
  - Risk Reduction: {UX}
  - ROI: {Quality uplift}
  - Out-of-Scope: Changing auth flow logic

- [P1] (Effort M) (PS=5.0) Add 3 accessibility test files
  - CF(s): CF2a
  - Dimension(s): D03
  - Files/Modules: `frontend/src/pages/Dashboard.a11y.test.tsx`, `Login.a11y.test.tsx`, `Incidents.a11y.test.tsx`
  - Change Summary: Create axe-core-based a11y tests for 3 key pages
  - Definition of Done: `npm run test:a11y` passes with 0 violations
  - Tests/Validation: CI frontend-tests job includes a11y suite
  - Observability: Test results in JUnit XML
  - Rollback: Delete test files
  - Risk of Change: Low
  - Dependencies: None
  - Owner Role: Frontend engineer
  - Risk Reduction: {UX, GOV}
  - ROI: {Risk avoided, Quality uplift}
  - Out-of-Scope: WCAG AAA; fixing violations found (separate PR)

- [P1] (Effort S) (PS=4.6) Renumber ADRs sequentially
  - CF(s): —
  - Dimension(s): D29
  - Files/Modules: `docs/adr/ADR-0001-*.md` through `ADR-0008-*.md`
  - Change Summary: Rename files to sequential ADR-0001 through ADR-0008
  - Definition of Done: 8 unique ADR numbers; cross-references updated
  - Tests/Validation: Script to verify no duplicate numbers
  - Observability: N/A
  - Rollback: Rename back
  - Risk of Change: Low
  - Dependencies: None
  - Owner Role: Any engineer
  - Risk Reduction: {GOV}
  - ROI: {Quality uplift}
  - Out-of-Scope: Writing new ADRs

- [P1] (Effort S) (PS=4.6) Add Gitleaks secret scanning to CI
  - CF(s): CF5
  - Dimension(s): D06
  - Files/Modules: `.github/workflows/ci.yml`, `.gitleaks.toml` (new)
  - Change Summary: Add Gitleaks GitHub Action step; create allowlist config
  - Definition of Done: CI blocks on detected secrets; existing false positives in allowlist
  - Tests/Validation: CI passes with clean scan
  - Observability: Gitleaks scan results in CI logs
  - Rollback: Remove CI step
  - Risk of Change: Low
  - Dependencies: None
  - Owner Role: Platform engineer
  - Risk Reduction: {SEC}
  - ROI: {Risk avoided}
  - Out-of-Scope: Pre-commit hooks

- [P1] (Effort S) (PS=3.2) Add health check triage runbook
  - CF(s): CF5
  - Dimension(s): D23, D32
  - Files/Modules: `docs/runbooks/health-check-triage.md` (new)
  - Change Summary: Document /readyz failure → DB/Redis triage → escalation path
  - Definition of Done: Runbook covers all /readyz dependency failures
  - Tests/Validation: Peer review by ops
  - Observability: N/A
  - Rollback: N/A
  - Risk of Change: Low
  - Dependencies: None
  - Owner Role: SRE / DevOps
  - Risk Reduction: {REL}
  - ROI: {Time saved, Risk avoided}
  - Out-of-Scope: Automated remediation

- [P1] (Effort M) (PS=6.4) Resolve 15 mypy overrides
  - CF(s): CF2
  - Dimension(s): D21
  - Files/Modules: `pyproject.toml`, affected source modules
  - Change Summary: Fix type errors in 15 most critical modules; remove their override blocks
  - Definition of Done: `[[tool.mypy.overrides]]` count ≤ 15
  - Tests/Validation: `mypy src/` passes with fewer overrides
  - Observability: N/A
  - Rollback: Re-add overrides
  - Risk of Change: Medium
  - Dependencies: None
  - Owner Role: Backend engineer
  - Risk Reduction: {REL}
  - ROI: {Quality uplift}
  - Out-of-Scope: Zero overrides; third-party library stubs

- [P1] (Effort M) (PS=6.4) Add Playwright login + incident CRUD spec
  - CF(s): CF1, CF2a
  - Dimension(s): D15
  - Files/Modules: `frontend/e2e/incident-crud.spec.ts` (new)
  - Change Summary: Create Playwright test: login → create incident → verify in list → view detail
  - Definition of Done: Playwright test passes against staging
  - Tests/Validation: CI e2e-tests job green
  - Observability: Playwright trace artifacts
  - Rollback: Delete spec
  - Risk of Change: Low
  - Dependencies: Staging environment accessible from CI
  - Owner Role: QA / Frontend engineer
  - Risk Reduction: {REL}
  - ROI: {Quality uplift, Risk avoided}
  - Out-of-Scope: Full CRUD for all entities

### Priority 2 (Important)

- [P2] (Effort L) (PS=6.4) Run k6 load test + establish baselines
  - CF(s): CF2a-c
  - Dimension(s): D04, D25
  - Files/Modules: `tests/load/k6-scenarios.js` (new), `docs/evidence/load-test-results.md` (new)
  - Change Summary: Create k6 scenarios for list/create endpoints; run against staging; document P95/P99
  - Definition of Done: Load test report with baselines published
  - Tests/Validation: CI performance-budget job references baselines
  - Observability: Latency percentiles tracked
  - Rollback: N/A
  - Risk of Change: Low
  - Dependencies: Staging environment
  - Owner Role: SRE / Backend engineer
  - Risk Reduction: {PERF}
  - ROI: {Quality uplift}
  - Out-of-Scope: Performance optimization (separate work)

- [P2] (Effort M) (PS=6.4) Wire nh3 input sanitization into schemas
  - CF(s): CF3
  - Dimension(s): D06, D07
  - Files/Modules: `src/api/schemas/incident.py`, `complaint.py`, `risk.py`
  - Change Summary: Add Pydantic field_validator using nh3.clean() on description/notes fields
  - Definition of Done: HTML tags stripped from user text input
  - Tests/Validation: Unit test with XSS payload
  - Observability: Log sanitization events
  - Rollback: Remove validators
  - Risk of Change: Low
  - Dependencies: nh3 already installed
  - Owner Role: Backend engineer
  - Risk Reduction: {SEC}
  - ROI: {Risk avoided}
  - Out-of-Scope: Rich text support

- [P2] (Effort M) (PS=6.5) Cost analysis dashboard
  - CF(s): —
  - Dimension(s): D26
  - Files/Modules: `docs/operations/cost-analysis.md` (new)
  - Change Summary: Document Azure resource costs; identify optimization opportunities
  - Definition of Done: Monthly cost breakdown with 3 optimization recommendations
  - Tests/Validation: Review with finance/ops
  - Observability: Azure Cost Management alerts
  - Rollback: N/A
  - Risk of Change: Low
  - Dependencies: Azure billing access
  - Owner Role: Platform engineer
  - Risk Reduction: {COST}
  - ROI: {Cost reduction}
  - Out-of-Scope: Implementing optimizations

- [P2] (Effort M) (PS=5.0) Add backend error message i18n catalog
  - CF(s): —
  - Dimension(s): D27
  - Files/Modules: `src/core/i18n.py` (new), `src/api/schemas/error_codes.py`
  - Change Summary: Create message catalog; wire ErrorCode to locale-aware messages
  - Definition of Done: Error messages retrievable by locale key
  - Tests/Validation: Unit test with en/fr error messages
  - Observability: N/A
  - Rollback: Remove i18n module
  - Risk of Change: Low
  - Dependencies: None
  - Owner Role: Backend engineer
  - Risk Reduction: {UX}
  - ROI: {Quality uplift}
  - Out-of-Scope: Full backend translation; database content i18n

- [P2] (Effort L) (PS=4.1) Add circuit breaker for external services
  - CF(s): CF4
  - Dimension(s): D05, D25
  - Files/Modules: `src/infrastructure/circuit_breaker.py` (new), `azure_monitor.py`
  - Change Summary: Implement circuit breaker pattern for Azure Blob, email, monitoring calls
  - Definition of Done: Circuit opens after 5 consecutive failures; half-open retry after 30s
  - Tests/Validation: Unit test simulating failure cascade
  - Observability: Circuit state metric (open/closed/half-open)
  - Rollback: Remove circuit breaker; direct calls resume
  - Risk of Change: Medium
  - Dependencies: None
  - Owner Role: Backend engineer
  - Risk Reduction: {REL}
  - ROI: {Risk avoided}
  - Out-of-Scope: Bulkhead isolation; retry budgets

---

## 10. Acceptance-Test Matrix (World-Class Proof)

| CF | E2E Tests | Integration Tests | Unit Tests | Chaos/Failure | Observability Checks | Release Checks |
|----|-----------|-------------------|------------|---------------|---------------------|----------------|
| CF1 Auth | Login flow, token refresh (Playwright) | Auth endpoint 401/403 responses | JWT encode/decode, password hash | Invalid token flood | Auth success/fail rate metric | Gitleaks, signoff |
| CF2a Incidents | Create, list, update, status transition (Playwright) | CRUD with tenant isolation | Transition validation, ref number generation | DB connection drop during write | Incident count metric, latency P95 | Contract test, E2E baseline |
| CF2b Audits | Template create, run execute, complete (Playwright) | Service layer methods, scoring | Template validation, score calculation | Redis unavailable during cache invalidation | Audit completion rate, score distribution | Contract test |
| CF2c Risks | Create, update JSON fields, matrix view (Playwright) | CRUD with correct column mapping | JSON field mapping, risk level calculation | Concurrent risk updates (optimistic lock) | Risk level distribution metric | Contract test |
| CF3 Data writes | Portal submission end-to-end | Idempotency, tenant_id assignment | nh3 sanitization, audit trail | Duplicate POST with same Idempotency-Key | Write success/failure rate | Down-migration test |
| CF4 External | Azure Blob upload, monitoring init | OTel span creation, Azure Monitor export | Circuit breaker state machine | External service timeout | Span count, circuit breaker state | SBOM, pip-audit |
| CF5 Release | Full deploy staging→prod | Release signoff validation | Config failfast | Rollback drill | Deploy duration metric | All 22 CI gates, signoff |

---

## 11. World-Class Checklist (9.5+ Criteria)

| ID | Dimension | 9.5+ Observable Criteria |
|----|-----------|------------------------|
| D01 | Product clarity | Documented personas with journey maps; feature matrix maps to journeys; onboarding flow tested |
| D02 | UX quality | Design system with Storybook; consistent breadcrumbs, empty states, skeletons on all pages; Lighthouse UX score >90 |
| D03 | Accessibility | WCAG 2.1 AA automated scan 0 violations on all pages; keyboard navigation tested; screen reader tested |
| D04 | Performance | P95 API latency <200ms; LCP <2.5s; Lighthouse perf >90; load test report with baselines |
| D05 | Reliability | 99.9% availability SLO met; circuit breakers on all external calls; /readyz checks all dependencies; chaos test suite |
| D06 | Security | All errors structured; Gitleaks + Bandit + pip-audit in CI; pentest report <6 months old; rate limiter fully functional |
| D07 | Privacy | DPIA for all PII flows; nh3 sanitization on all user inputs; data retention policy enforced; GDPR erasure endpoint |
| D08 | Compliance | ISO audit evidence pack auto-generated; compliance dashboard live; evidence links to specific controls |
| D09 | Architecture | All routes through service layer; domain exceptions used everywhere; no direct DB queries in routes |
| D10 | API design | All errors use api_error(); consistent pagination; OpenAPI spec validated in CI; versioning strategy documented |
| D11 | Data model | All JSON columns correctly mapped; composite indexes on all tenant queries; soft delete on all entities |
| D12 | Schema | 100% of migrations reversible; migration test coverage; no manual DDL |
| D13 | Observability | OTel traces active; SLO burn-rate alerts; structured logs with correlation IDs; dashboards for all CFs |
| D14 | Error handling | Zero plain-string errors; user-facing errors translated; error rate <1% SLO met; toast on all API errors |
| D15 | Testing | Coverage ≥70%; Playwright specs for all CFs; mutation testing pilot; contract tests for all APIs |
| D16 | Test data | factory-boy factories for all models; test data seeder for staging; no production data in tests |
| D17 | CI gates | All current 22 gates + Gitleaks + performance budget + a11y gate |
| D18 | CD/release | Canary deployments; feature flags for rollout; automated rollback on error spike |
| D19 | Configuration | All secrets from Key Vault; config drift detection; no environment-specific code paths |
| D20 | Dependencies | All deps pinned with lockfile; automated PR for updates; no known CVEs |
| D21 | Code quality | Mypy overrides ≤5; consistent error patterns across all routes; cyclomatic complexity gates |
| D22 | Documentation | All ADRs sequential; API changelog per release; architecture diagram updated |
| D23 | Runbooks | Runbook for every alert; PagerDuty/OpsGenie integrated; quarterly runbook drills |
| D24 | Data integrity | Idempotency on all writes; status transitions validated everywhere; audit trail on all mutations |
| D25 | Scalability | Autoscaling configured; load test report quarterly; connection pool tuned to load |
| D26 | Cost | Monthly cost report; resource right-sizing; cost alerts on anomalies |
| D27 | I18n | Backend error catalog in 2+ locales; frontend 2+ locales; locale-aware formatting |
| D28 | Analytics | Web vitals dashboard; SLO dashboard; business metrics (incident MTTR, audit completion rate) |
| D29 | Governance | ADRs sequential and current; CHANGELOG automated; decision log reviewed quarterly |
| D30 | Build determinism | Docker digest pinned; lockfile-first; SBOM generated and signed |
| D31 | Environment parity | Staging mirrors production config; secrets from same Key Vault pattern; infra-as-code |
| D32 | Supportability | Request logging with user/tenant correlation; health endpoints comprehensive; support playbooks |

---

## Contradictions Resolver

| ID | Contradiction | Evidence | Resolution |
|----|--------------|----------|------------|
| C-001 | `requirements.txt` lists opencensus; `azure_monitor.py` imports opentelemetry | `requirements.txt:49-51`, `azure_monitor.py:11-19` | P1: Replace opencensus with opentelemetry packages |
| C-002 | `nh3` in requirements but no usage found in code | `requirements.txt:20`, grep for `nh3` in src/ | P2: Wire nh3.clean() into schema validators |
| C-003 | Auth route errors use plain strings while all other routes use api_error() | `auth.py:78-207` vs `incidents.py`, `risks.py` | P1: Standardize auth to api_error() |

---

## Evidence Index

### By Critical Function
- **CF1 (Auth):** `src/api/routes/auth.py`, `src/core/auth.py`, `src/api/dependencies/`, `src/infrastructure/middleware/rate_limiter.py`
- **CF2a (Incidents):** `src/api/routes/incidents.py`, `src/domain/models/incident.py`, `src/domain/services/incident_service.py`, `tests/unit/test_auth_enforcement.py`
- **CF2b (Audits):** `src/api/routes/audits.py`, `src/domain/models/audit.py`, `src/domain/services/audit_service.py`
- **CF2c (Risks):** `src/api/routes/risks.py`, `src/domain/models/risk.py`
- **CF3 (Data writes):** `src/api/middleware/idempotency.py`, `src/domain/models/base.py`, `src/api/routes/employee_portal.py`
- **CF4 (External):** `src/infrastructure/monitoring/azure_monitor.py`, `requirements.txt`, `src/core/config.py`
- **CF5 (Release):** `.github/workflows/ci.yml`, `.github/workflows/deploy-production.yml`, `scripts/governance/validate_release_signoff.py`, `docs/evidence/release_signoff.json`

### By Dimension
- **D01-D02:** `docs/user-journeys/`, `frontend/src/components/ui/Breadcrumbs.tsx`, `EmptyState.tsx`, `SkeletonLoader.tsx`
- **D03:** `frontend/package.json` (jest-axe, jsx-a11y), `docs/accessibility/wcag-checklist.md`, `frontend/src/components/ui/LiveAnnouncer.tsx`
- **D04:** `frontend/package.json` (web-vitals, size-limit, @lhci/cli), `src/main.py` (GZipMiddleware)
- **D05:** `src/main.py` (/readyz), `src/api/routes/health.py`, `src/infrastructure/middleware/request_logger.py`
- **D06:** `src/main.py` (SecurityHeadersMiddleware, CSP, CORS), `src/infrastructure/middleware/rate_limiter.py`, `requirements.txt` (nh3)
- **D07:** `docs/privacy/dpia-incidents.md`, `src/core/config.py` (pseudonymization_pepper)
- **D08:** `src/domain/models/` (ISO models), `docs/evidence/release_signoff.json`
- **D09-D10:** `src/api/__init__.py`, `src/domain/exceptions.py`, `src/api/utils/errors.py`, `src/api/middleware/error_handler.py`
- **D11-D12:** `src/domain/models/*.py`, `alembic/versions/` (63 migrations)
- **D13:** `src/infrastructure/monitoring/azure_monitor.py`, `src/infrastructure/middleware/request_logger.py`, `docs/observability/slo-definitions.md`
- **D14:** `src/api/routes/incidents.py`, `complaints.py`, `risks.py` (api_error, transitions), `src/domain/exceptions.py`
- **D15-D16:** `tests/`, `pyproject.toml:217` (fail_under=35), `frontend/package.json` (@playwright/test, factory-boy)
- **D17-D18:** `.github/workflows/ci.yml` (22 jobs), `deploy-staging.yml`, `deploy-production.yml`
- **D19:** `src/core/config.py`, `docker-compose.yml`
- **D20:** `requirements.txt`, `requirements.lock`, `frontend/package-lock.json`, `.github/dependabot.yml`
- **D21:** `pyproject.toml` (black, isort, mypy overrides)
- **D22:** `README.md`, `docs/adr/`, `docs/runbooks/`
- **D23:** `docs/runbooks/incident-response.md`, `docs/runbooks/escalation.md`
- **D24:** `src/api/middleware/idempotency.py`, `src/api/routes/incidents.py` (transitions), `src/domain/models/base.py` (AuditTrailMixin)
- **D25:** `src/infrastructure/database.py` (pool config), `Dockerfile` (single instance)
- **D26:** No evidence files
- **D27:** `frontend/src/i18n/`, `frontend/src/i18n/locales/en.json`
- **D28:** `frontend/src/hooks/useWebVitals.ts`, `src/api/routes/slo.py`, `src/api/routes/telemetry.py`
- **D29:** `docs/adr/` (8 files, 4 collisions), `CHANGELOG.md`
- **D30:** `Dockerfile` (digest pin), `requirements.lock`, `.github/workflows/ci.yml` (sbom job)
- **D31:** `docker-compose.yml`, `src/core/config.py` (app_env)
- **D32:** `src/infrastructure/middleware/request_logger.py`, `src/api/routes/health.py`, `src/main.py` (/readyz)
