# Quality Governance Platform — World-Class Uplift Plan (Round 2)

**Assessment Date**: 2026-03-07
**Target**: WCS 9.5+ across all 32 dimensions

---

## 6. Quick Wins Engine (Small Effort / High Value)

### QW-01: Fix Tenants Module Auth Guards
- **Linked CF**: CF1 | **Dimensions**: D06
- **Why high leverage**: Closes the highest-severity security gap with minimal code change — each endpoint needs one line added.
- **Exact change locations**: `src/api/routes/tenants.py` — add `current_user: User = Depends(get_current_active_user)` to all endpoint function signatures; add `CurrentSuperuser` to create/delete/modify.
- **Definition of Done**: All tenant endpoints return 401 without token; admin endpoints return 403 for non-superusers.
- **Validation**: Integration test `test_tenants_require_auth()`; manual verification via Swagger UI.
- **Rollback**: Revert commit.
- **Expected WCS lift**: D06 +0.4 to +0.8

### QW-02: Fix Compliance Endpoints Auth
- **Linked CF**: CF1 | **Dimensions**: D06
- **Why high leverage**: Second P0 security gap; same pattern as QW-01.
- **Exact change locations**: `src/api/routes/compliance.py` — add `current_user: User = Depends(get_current_active_user)` to unauthenticated endpoints.
- **Definition of Done**: All compliance endpoints return 401 without token.
- **Validation**: Integration test `test_compliance_endpoints_require_auth()`.
- **Rollback**: Revert commit.
- **Expected WCS lift**: D06 +0.2 to +0.4

### QW-03: Add Tenant Isolation to Incidents/Complaints
- **Linked CF**: CF1, CF2 | **Dimensions**: D06, D07
- **Why high leverage**: Prevents cross-tenant data leakage — GDPR breach risk elimination.
- **Exact change locations**: `src/api/routes/incidents.py` — add `.filter(Incident.tenant_id == current_user.tenant_id)` to list/get queries; same pattern in `src/api/routes/complaints.py`.
- **Definition of Done**: Tenant A user cannot see Tenant B incidents/complaints; null tenant_id records handled gracefully.
- **Validation**: Multi-tenant integration test; backfill null tenant_ids via migration.
- **Rollback**: Remove tenant filter; data migration is forward-only.
- **Expected WCS lift**: D06 +0.4, D07 +0.3

### QW-04: Align Coverage Threshold (35 → 50)
- **Linked CF**: CF5 | **Dimensions**: D15, D17
- **Why high leverage**: Restores documented quality bar; requires fixing existing skip decorators to pass.
- **Exact change locations**: `.github/workflows/ci.yml` — change `--cov-fail-under=35` to `--cov-fail-under=50` in unit-tests and integration-tests jobs.
- **Definition of Done**: CI enforces 50% coverage; all test suites pass at new threshold.
- **Validation**: CI pipeline runs green at 50% threshold.
- **Rollback**: Revert to 35 if blocking; write missing tests first.
- **Expected WCS lift**: D15 +0.6 to +1.0

### QW-05: Create ADR Documents (0001-0003)
- **Linked CF**: CF5 | **Dimensions**: D29, D22
- **Why high leverage**: Fills most impactful documentation gap; referenced decisions already exist in code.
- **Exact change locations**: Create `docs/adr/ADR-0001-production-dependencies.md`, `docs/adr/ADR-0002-config-failfast.md`, `docs/adr/ADR-0003-readiness-probe.md`.
- **Definition of Done**: Each ADR has Context, Decision, Status, Consequences sections; code references point to valid files.
- **Validation**: CI check validates ADR references resolve to files.
- **Rollback**: N/A (additive).
- **Expected WCS lift**: D29 +0.8 to +1.2, D22 +0.4

### QW-06: Fix Postgres Version in Sandbox
- **Linked CF**: CF5 | **Dimensions**: D31
- **Why high leverage**: One-line fix eliminates environment parity contradiction.
- **Exact change locations**: `docker-compose.sandbox.yml` — change `postgres:15-alpine` to `postgres:16-alpine`.
- **Definition of Done**: All docker-compose files use PostgreSQL 16.
- **Validation**: `docker-compose -f docker-compose.sandbox.yml up` succeeds; integration tests pass.
- **Rollback**: Revert to PG15.
- **Expected WCS lift**: D31 +0.3 to +0.5

### QW-07: Add Skipped Test Count CI Gate
- **Linked CF**: CF5 | **Dimensions**: D15, D21
- **Why high leverage**: Prevents test harness drift from worsening; forces fix of broken imports.
- **Exact change locations**: `.github/workflows/ci.yml` — add step after pytest: `grep -c "SKIPPED" junit-unit.xml | awk '{if ($1 > MAX_SKIPS) exit 1}'`; `scripts/validate_skipped_tests.py`.
- **Definition of Done**: CI fails if skipped test count exceeds ceiling (start at current count, reduce each sprint).
- **Validation**: Deliberately skip a test; verify CI fails.
- **Rollback**: Remove CI step.
- **Expected WCS lift**: D15 +0.3 to +0.6

### QW-08: Create CHANGELOG.md
- **Linked CF**: CF5 | **Dimensions**: D22, D29
- **Why high leverage**: Standard governance artifact; takes 30 minutes; enables release communication.
- **Exact change locations**: Create `CHANGELOG.md` at repo root using Keep-a-Changelog format.
- **Definition of Done**: CHANGELOG has entries for current version; linked from README; PR template includes "update CHANGELOG" checkbox.
- **Validation**: File exists and follows format.
- **Rollback**: N/A (additive).
- **Expected WCS lift**: D22 +0.3, D29 +0.2

### QW-09: Add axe-core to Frontend CI
- **Linked CF**: CF2 | **Dimensions**: D03
- **Why high leverage**: Automated accessibility scanning catches 40-60% of WCAG issues.
- **Exact change locations**: `frontend/package.json` — add `@axe-core/react` or `vitest-axe`; `ci.yml` frontend-tests job — add axe assertion.
- **Definition of Done**: CI fails on accessibility violations (initially warning mode, then blocking).
- **Validation**: Introduce a known violation; verify CI catches it.
- **Rollback**: Remove axe dependency and CI step.
- **Expected WCS lift**: D03 +1.0 to +2.0

### QW-10: Create Operational Runbook Skeleton
- **Linked CF**: CF1, CF2, CF5 | **Dimensions**: D23
- **Why high leverage**: D23 is the highest-PS dimension (13.0); even a skeleton runbook significantly reduces operational risk.
- **Exact change locations**: Create `docs/runbooks/` with: `incident-response.md`, `deployment.md`, `rollback.md`, `database-recovery.md`, `escalation.md`.
- **Definition of Done**: Each runbook has: trigger conditions, step-by-step procedures, contacts, verification steps.
- **Validation**: Peer review by ops team; tabletop exercise.
- **Rollback**: N/A (additive).
- **Expected WCS lift**: D23 +2.0 to +3.0

### QW-11: Implement 5 Critical Contract Tests
- **Linked CF**: CF2, CF4 | **Dimensions**: D15, D10
- **Why high leverage**: Replaces stub contract tests with real validations for top 5 endpoints.
- **Exact change locations**: `tests/contract/test_api_contracts.py` — implement contract assertions for `/auth/login`, `/incidents`, `/audits/runs`, `/users`, `/complaints`.
- **Definition of Done**: Each contract test validates response schema, status codes, required fields.
- **Validation**: Contract tests pass in CI; deliberately break an endpoint and verify test catches it.
- **Rollback**: Revert to stub tests.
- **Expected WCS lift**: D15 +0.4 to +0.6, D10 +0.2

### QW-12: Add SLO/SLI Definitions Document
- **Linked CF**: CF1, CF2 | **Dimensions**: D13, D05
- **Why high leverage**: Foundation for all observability maturity; takes ~2 hours to define.
- **Exact change locations**: Create `docs/observability/slo-definitions.md`.
- **Definition of Done**: SLOs defined for: availability (99.9%), API latency (P95 < 500ms), error rate (< 1%), auth success rate (> 99.5%).
- **Validation**: SLO targets are measurable with existing Azure Monitor metrics.
- **Rollback**: N/A (additive).
- **Expected WCS lift**: D13 +0.4 to +0.8

---

## 7. Critical Bars Hardening Plan

### Gate 1: Security Hardening (P0)

**Current State**: Strong scanning posture (6 security tools in CI), but 3 critical auth gaps allow unauthenticated/cross-tenant access.

**Gap**: F-001 (tenants auth), F-002 (compliance auth), F-003 (cross-tenant incidents/complaints).

**Implementation Steps**:
1. Fix `src/api/routes/tenants.py`: restore auth guards on all endpoints (QW-01)
2. Fix `src/api/routes/compliance.py`: add auth to all endpoints (QW-02)
3. Fix `src/api/routes/incidents.py` and `complaints.py`: add tenant_id filtering (QW-03)
4. Audit ALL 48 route modules for auth coverage: write script `scripts/validate_auth_coverage.py` that parses route files and verifies every endpoint has auth dependency
5. Add auth enforcement regression test: `tests/security/test_auth_enforcement.py` — iterate all registered routes and verify 401 without token
6. Add tenant isolation regression test: `tests/security/test_tenant_isolation.py` — multi-tenant scenario tests

**Done Criteria**: Zero unauthenticated endpoints (except explicit public: health, auth/login, auth/token-exchange, auth/password-reset); all list endpoints filter by tenant_id; auth enforcement CI test passes.

### Gate 2: Data Integrity (P0/P1)

**Current State**: Idempotency middleware for POST, optimistic locking on investigations, hash-chain audit trail. Good foundation.

**Gap**: No idempotency on PUT/PATCH; actions module uses in-memory pagination; no database-level check constraints for enum values.

**Implementation Steps**:
1. Extend idempotency middleware to support PUT/PATCH with `Idempotency-Key` header
2. Refactor actions module: replace in-memory pagination with database-level UNION ALL query with LIMIT/OFFSET
3. Add database CHECK constraints for critical enum columns (incident_status, audit_status, risk_status)
4. Add migration to backfill null `tenant_id` values on incidents and complaints

**Done Criteria**: All write operations support idempotency; actions pagination is database-backed; enum constraints enforced at DB level.

### Gate 3: Release Safety (P1)

**Current State**: Excellent — 5-phase deploy proof, deterministic SHA, release signoff. Minor gaps only.

**Gap**: Down migrations not verified in CI; rollback drill not evidence-tracked; alembic.ini has placeholder URL.

**Implementation Steps**:
1. Add CI job: verify `alembic downgrade -1` succeeds for latest migration
2. Schedule monthly rollback drill; generate evidence artifact
3. Clean up `alembic.ini` placeholder URL with documented comment

**Done Criteria**: Down migration test in CI passes; rollback drill evidence from last 30 days exists.

---

## 8. World-Class Roadmap (3 Horizons)

### Horizon A: Safety + Determinism + Testability (0-2 weeks)

**Entry Criteria**: Repository access, CI pipeline green.

| Epic | Dimensions | CFs | Tasks |
|------|-----------|-----|-------|
| A1: Close P0 Security Gaps | D06 | CF1, CF2 | QW-01, QW-02, QW-03; auth enforcement regression test; tenant isolation test |
| A2: Test Harness Stabilization | D15, D21 | CF2, CF5 | Fix skipped tests (F-006); align coverage 35→50 (QW-04); implement 5 contract tests (QW-11); add skipped test ceiling (QW-07) |
| A3: Governance Documentation | D22, D29 | CF5 | Create ADRs (QW-05); create CHANGELOG (QW-08); create runbook skeletons (QW-10) |
| A4: Environment Parity Fix | D31 | CF5 | Fix sandbox PG version (QW-06); fix alembic.ini placeholder (C-003) |

**Exit Criteria**:
- Zero P0 findings open
- Auth enforcement test passes on all 48 route modules
- Coverage at 50%+ with zero unexplained skips
- ADR-0001 through ADR-0003 written
- CHANGELOG.md exists
- Runbook skeletons created for 5 operational scenarios

**Dependencies**: None (all self-contained).

**Risks**: Coverage threshold increase may block CI → Mitigation: write tests for critical paths first, then raise threshold.

---

### Horizon B: Core Quality Uplift (2-6 weeks)

**Entry Criteria**: All Horizon A exit criteria met; P0 findings closed.

| Epic | Dimensions | CFs | Tasks |
|------|-----------|-----|-------|
| B1: Type Safety Remediation (GOVPLAT-004) | D21, D09 | CF2, CF3 | Fix mypy errors in top 10 modules (workflow_engine, risk_scoring, audit_service first); reduce override count from 27 to <15 |
| B2: Observability Maturity | D13, D05 | CF1-CF5 | Define SLOs (QW-12); create Grafana/Azure dashboard templates; add alerting rules for SLO breaches; instrument DLQ depth alerts |
| B3: Testing Depth | D15, D16 | CF2 | Write behavioral unit tests for incident/audit/risk services (not just imports); expand factories; add property-based tests for risk scoring; raise coverage to 60% |
| B4: Accessibility | D03 | CF2 | Add axe-core (QW-09); WCAG 2.1 AA audit; fix top 20 violations; add Playwright a11y assertions |
| B5: Performance Baseline | D04, D25 | CF2, CF4 | Set up k6/Locust load tests; benchmark top 10 endpoints; fix actions in-memory pagination; add P95 latency SLO checks |
| B6: Privacy & GDPR | D07 | CF2, CF3 | Write DPIA for incident/complaint data; implement DSAR endpoint; document data classification; add consent tracking if needed |
| B7: Operational Runbooks | D23 | CF1-CF5 | Flesh out runbook skeletons with tested procedures; conduct tabletop exercise; document on-call rotation |

**Exit Criteria**:
- Mypy overrides < 15
- SLOs defined and dashboards operational
- Coverage at 60%+ with behavioral tests
- axe-core in CI (blocking mode)
- Load test baselines established
- DPIA completed
- Runbooks peer-reviewed and tested

**Dependencies**: Horizon A complete; ops team availability for runbook review.

**Risks**: GOVPLAT-004 fixes may reveal runtime bugs → Mitigation: fix behind feature flags, extensive testing.

---

### Horizon C: Automation, Resilience, and "5/5" Completion (6-12 weeks)

**Entry Criteria**: All Horizon B exit criteria met.

| Epic | Dimensions | CFs | Tasks |
|------|-----------|-----|-------|
| C1: Chaos Engineering | D05, D25 | CF1-CF5 | Implement chaos tests (DB disconnect, Redis failure, Azure AD outage); verify circuit breakers activate; document blast radius |
| C2: Coverage to 80%+ | D15, D16 | CF2 | Mutation testing (mutmut); expand to 80% line coverage; comprehensive integration tests for all CFs |
| C3: Full i18n | D27 | CF2 | Backend i18n support; verify all frontend strings translated; RTL support if needed |
| C4: Cost Optimization | D26 | CF4, CF5 | Azure cost analysis; right-sizing report; implement auto-scaling policies; document FinOps practices |
| C5: Product Analytics | D28 | CF2 | Implement product analytics (PostHog/Amplitude); A/B testing framework; user behavior tracking (with consent) |
| C6: UX Design System | D02 | CF2 | Storybook component library; design tokens; UX audit; user testing |
| C7: Advanced API | D10, D24 | CF2, CF4 | API versioning strategy doc; GraphQL exploration; cursor-based pagination everywhere; comprehensive idempotency |
| C8: Full Governance | D29, D22 | CF5 | ADR process formalized; monthly architecture review; complete API documentation; developer onboarding guide |

**Exit Criteria**:
- Chaos tests pass for all CFs
- Coverage ≥ 80% with mutation testing
- All dimensions at WCS ≥ 8.0
- Cost baseline established with optimization plan
- Design system published

**Dependencies**: Horizon B complete; design resources for C6; product team for C5.

**Risks**: Scope creep on C6/C7 → Mitigation: strict timeboxing, MVP scope per epic.

---

## 9. PR-Ready Backlog (Sorted by Priority Score desc, then Effort asc)

### P0 Items

1. **[P0] (Effort S) (PS=13.0) Create Operational Runbook Skeletons**
   - CF(s): CF1, CF2, CF5
   - Dimension(s): D23
   - Files/Modules: Create `docs/runbooks/` — `incident-response.md`, `deployment.md`, `rollback.md`, `database-recovery.md`, `escalation.md`
   - Change Summary: Write 5 operational runbooks with trigger conditions, step-by-step procedures, contacts, verification steps
   - Definition of Done: Each runbook has complete procedure; peer-reviewed by ops team
   - Tests/Validation: Tabletop walkthrough of incident-response runbook
   - Observability: N/A (documentation)
   - Rollback: N/A (additive)
   - Risk of Change: Low
   - Dependencies: None
   - Owner Role: Platform Engineer / SRE
   - Risk Reduction: {REL}
   - ROI: {Risk avoided}
   - Out-of-Scope: Automated runbook execution; PagerDuty integration

2. **[P0] (Effort S) (PS=6.9) Fix Tenants Module Auth Guards**
   - CF(s): CF1
   - Dimension(s): D06
   - Files/Modules: `src/api/routes/tenants.py`
   - Change Summary: Add `CurrentActiveUser` dependency to all endpoints; add `CurrentSuperuser` to create/delete/modify
   - Definition of Done: All tenant endpoints return 401 without token; admin endpoints return 403 for non-superusers
   - Tests/Validation: `tests/security/test_tenants_auth.py` — 401/403 assertions
   - Observability: `tenant.auth_bypass_attempt` counter
   - Rollback: Revert commit
   - Risk of Change: Low
   - Dependencies: None
   - Owner Role: Backend Engineer
   - Risk Reduction: {SEC}
   - ROI: {Risk avoided}
   - Out-of-Scope: ABAC policy changes; tenant provisioning workflow

3. **[P0] (Effort S) (PS=6.9) Fix Compliance Endpoints Auth**
   - CF(s): CF1
   - Dimension(s): D06
   - Files/Modules: `src/api/routes/compliance.py`
   - Change Summary: Add `CurrentUser` dependency to all unauthenticated endpoints
   - Definition of Done: All compliance endpoints return 401 without token
   - Tests/Validation: `tests/security/test_compliance_auth.py`
   - Observability: Log unauthenticated access attempts
   - Rollback: Revert commit; verify frontend sends JWT
   - Risk of Change: Low — may require frontend fix if not sending auth header
   - Dependencies: Verify frontend sends Authorization header on compliance calls
   - Owner Role: Backend Engineer
   - Risk Reduction: {SEC}
   - ROI: {Risk avoided}
   - Out-of-Scope: Public API tier design

4. **[P0] (Effort M) (PS=6.9) Add Tenant Isolation to Incidents/Complaints**
   - CF(s): CF1, CF2
   - Dimension(s): D06, D07
   - Files/Modules: `src/api/routes/incidents.py`, `src/api/routes/complaints.py`
   - Change Summary: Add `.filter(Model.tenant_id == current_user.tenant_id)` to all list/get queries; create migration to backfill null tenant_ids
   - Definition of Done: Multi-tenant test proves isolation; null tenant_ids handled
   - Tests/Validation: `tests/security/test_tenant_isolation.py` — create data in 2 tenants, verify isolation
   - Observability: `tenant.cross_tenant_query_blocked` counter
   - Rollback: Remove filter; keep backfill migration (forward-only)
   - Risk of Change: Medium — null tenant_id records need backfill
   - Dependencies: Data migration for existing records
   - Owner Role: Backend Engineer
   - Risk Reduction: {SEC, DATA}
   - ROI: {Risk avoided, Revenue protection}
   - Out-of-Scope: RLS enforcement at database level (separate epic)

5. **[P0] (Effort S) (PS=6.9) Create Auth Enforcement Regression Test**
   - CF(s): CF1
   - Dimension(s): D06, D15
   - Files/Modules: Create `tests/security/test_auth_enforcement.py`; create `scripts/validate_auth_coverage.py`
   - Change Summary: Iterate all registered FastAPI routes; verify every non-exempt endpoint returns 401 without token
   - Definition of Done: Test discovers all routes; exempt list is explicit and minimal (/healthz, /readyz, /auth/login, /auth/token-exchange, /auth/password-reset/*)
   - Tests/Validation: Self-testing — add an unprotected route and verify test catches it
   - Observability: CI job produces auth coverage report
   - Rollback: Remove test (but why would you)
   - Risk of Change: Low
   - Dependencies: QW-01, QW-02 must be done first
   - Owner Role: Security Engineer
   - Risk Reduction: {SEC}
   - ROI: {Risk avoided}
   - Out-of-Scope: Authorization (RBAC) testing; only covers authentication

### P1 Items

6. **[P1] (Effort S) (PS=12.3) Align CI Coverage Threshold to 50%**
   - CF(s): CF5
   - Dimension(s): D15
   - Files/Modules: `.github/workflows/ci.yml` (unit-tests, integration-tests jobs)
   - Change Summary: Change `--cov-fail-under=35` to `--cov-fail-under=50`
   - Definition of Done: CI enforces 50% coverage; pipeline passes
   - Tests/Validation: Lower coverage and verify CI fails
   - Observability: Coverage % in quality trend report
   - Rollback: Revert to 35 if blocking
   - Risk of Change: Medium — may require writing tests to reach 50%
   - Dependencies: Fix skip_on_import_error tests first (item #8)
   - Owner Role: QA Engineer
   - Risk Reduction: {REL}
   - ROI: {Quality uplift}
   - Out-of-Scope: Raising to 60%+ (Horizon B)

7. **[P1] (Effort S) (PS=8.2) Create ADR-0001 through ADR-0003**
   - CF(s): CF5
   - Dimension(s): D29, D22
   - Files/Modules: Create `docs/adr/ADR-0001-production-dependencies.md`, `ADR-0002-config-failfast.md`, `ADR-0003-readiness-probe.md`
   - Change Summary: Write retrospective ADRs based on code references; use standard ADR template
   - Definition of Done: Each ADR has Context, Decision, Status, Consequences; all code ADR references resolve
   - Tests/Validation: CI check: `scripts/validate_adr_references.py`
   - Observability: N/A
   - Rollback: N/A
   - Risk of Change: Low
   - Dependencies: None
   - Owner Role: Tech Lead
   - Risk Reduction: {GOV}
   - ROI: {Quality uplift, Time saved}
   - Out-of-Scope: Writing ADRs for all past decisions; only the 3 referenced ones

8. **[P1] (Effort M) (PS=8.2) Fix Test Harness Drift (skip_on_import_error)**
   - CF(s): CF2, CF5
   - Dimension(s): D15, D21
   - Files/Modules: `tests/unit/test_models.py`, `tests/unit/test_services.py`, all files using skip decorators
   - Change Summary: Fix broken import paths; update enum references; remove skip decorators; add CI ceiling for skipped tests
   - Definition of Done: Zero unexplained skipped tests; skip count ceiling in CI
   - Tests/Validation: All previously skipped tests now run and pass
   - Observability: Skipped test count in quality trend
   - Rollback: Re-add skip decorators for individual tests
   - Risk of Change: Low — mechanical import fixes
   - Dependencies: None
   - Owner Role: QA Engineer
   - Risk Reduction: {REL}
   - ROI: {Quality uplift}
   - Out-of-Scope: Writing new behavioral tests (separate item)

9. **[P1] (Effort S) (PS=8.2) Create CHANGELOG.md**
   - CF(s): CF5
   - Dimension(s): D22, D29
   - Files/Modules: Create `CHANGELOG.md` at repo root
   - Change Summary: Keep-a-Changelog format; retroactive v1.0.0 entry; link from README
   - Definition of Done: CHANGELOG exists with v1.0.0 entry; PR template updated with "update CHANGELOG" checkbox
   - Tests/Validation: File format validation
   - Rollback: N/A
   - Risk of Change: Low
   - Dependencies: None
   - Owner Role: Tech Lead
   - Risk Reduction: {GOV}
   - ROI: {Quality uplift}
   - Out-of-Scope: Automated changelog generation

10. **[P1] (Effort S) (PS=8.2) Fix Sandbox Postgres Version (15→16)**
    - CF(s): CF5
    - Dimension(s): D31
    - Files/Modules: `docker-compose.sandbox.yml`
    - Change Summary: Change `postgres:15-alpine` to `postgres:16-alpine`
    - Definition of Done: All docker-compose files use PG16; integration tests pass
    - Tests/Validation: `docker-compose -f docker-compose.sandbox.yml up -d` succeeds
    - Observability: N/A
    - Rollback: Revert to PG15
    - Risk of Change: Low
    - Dependencies: None
    - Owner Role: DevOps Engineer
    - Risk Reduction: {REL}
    - ROI: {Risk avoided}
    - Out-of-Scope: PG16-specific feature adoption

11. **[P1] (Effort M) (PS=8.2) Define SLO/SLI Document**
    - CF(s): CF1, CF2
    - Dimension(s): D13, D05
    - Files/Modules: Create `docs/observability/slo-definitions.md`
    - Change Summary: Define SLOs: availability (99.9%), P95 latency (<500ms), error rate (<1%), auth success (>99.5%); map to Azure Monitor queries
    - Definition of Done: SLOs documented; measurable with existing metrics; team sign-off
    - Tests/Validation: Run sample Azure Monitor queries to verify metrics exist
    - Observability: SLO dashboard in Azure Monitor
    - Rollback: N/A
    - Risk of Change: Low
    - Dependencies: Azure Monitor access
    - Owner Role: SRE / Platform Engineer
    - Risk Reduction: {REL}
    - ROI: {Quality uplift, Risk avoided}
    - Out-of-Scope: Error budget policies; SLO-based release gating

12. **[P1] (Effort S) (PS=8.2) Add axe-core to Frontend CI**
    - CF(s): CF2
    - Dimension(s): D03
    - Files/Modules: `frontend/package.json`, `.github/workflows/ci.yml` (frontend-tests job)
    - Change Summary: Install `vitest-axe` or `@axe-core/react`; add accessibility assertions to existing component tests
    - Definition of Done: CI runs axe-core; initially warning mode, blocking after 2 weeks
    - Tests/Validation: Introduce known a11y violation; verify detection
    - Observability: a11y violation count in CI artifacts
    - Rollback: Remove package and test assertions
    - Risk of Change: Low
    - Dependencies: None
    - Owner Role: Frontend Engineer
    - Risk Reduction: {UX}
    - ROI: {Risk avoided, Quality uplift}
    - Out-of-Scope: Full WCAG audit; screen reader testing

13. **[P1] (Effort M) (PS=8.2) Write Privacy Impact Assessment (DPIA)**
    - CF(s): CF2, CF3
    - Dimension(s): D07
    - Files/Modules: Create `docs/privacy/dpia-incidents.md`, `docs/privacy/data-classification.md`
    - Change Summary: DPIA for incident/complaint data (includes employee PII, health data); data classification policy; DSAR process documentation
    - Definition of Done: DPIA completed for incident and complaint modules; data classification levels defined; DSAR response timeline documented
    - Tests/Validation: Legal/DPO review
    - Observability: N/A
    - Rollback: N/A
    - Risk of Change: Low
    - Dependencies: DPO/legal availability
    - Owner Role: Data Protection Officer / Tech Lead
    - Risk Reduction: {DATA, SEC}
    - ROI: {Risk avoided, Revenue protection}
    - Out-of-Scope: DSAR automation endpoint; consent management platform

14. **[P1] (Effort M) (PS=7.0) Fix Top 10 Mypy Override Modules**
    - CF(s): CF2, CF3
    - Dimension(s): D21, D09
    - Files/Modules: `src/services/workflow_engine.py`, `src/services/risk_scoring.py`, `src/domain/services/ai_predictive_service.py`, `src/domain/services/ai_audit_service.py`, `src/infrastructure/cache/redis_cache.py`, `src/api/routes/uvdb.py`, `src/api/routes/planet_mark.py`, plus 3 others with most error codes suppressed
    - Change Summary: Fix type annotations; add proper return types; resolve attr-defined and arg-type errors; remove corresponding pyproject.toml overrides
    - Definition of Done: Mypy override count reduced from 27 to ≤17; fixed modules pass mypy strict
    - Tests/Validation: `mypy src/` passes with reduced overrides; existing tests still pass
    - Observability: Override count in quality trend
    - Rollback: Re-add overrides for specific modules
    - Risk of Change: Medium — type fixes may reveal runtime bugs
    - Dependencies: None
    - Owner Role: Backend Engineer
    - Risk Reduction: {REL}
    - ROI: {Quality uplift}
    - Out-of-Scope: Full mypy strict mode across all modules

15. **[P1] (Effort M) (PS=6.9) Implement Auth Coverage Validation Script**
    - CF(s): CF1
    - Dimension(s): D06
    - Files/Modules: Create `scripts/validate_auth_coverage.py`; add CI job in `ci.yml`
    - Change Summary: Parse all route modules; verify auth dependency in function signatures; maintain explicit exempt list; fail on unprotected endpoints
    - Definition of Done: Script discovers all routes; reports auth coverage percentage; CI job runs on every PR
    - Tests/Validation: Add unprotected endpoint; verify script catches it
    - Observability: Auth coverage % in CI summary
    - Rollback: Remove CI job
    - Risk of Change: Low
    - Dependencies: QW-01, QW-02 complete
    - Owner Role: Security Engineer
    - Risk Reduction: {SEC}
    - ROI: {Risk avoided}
    - Out-of-Scope: RBAC policy validation

16. **[P1] (Effort M) (PS=5.4) Implement 5 Contract Tests**
    - CF(s): CF2, CF4
    - Dimension(s): D15, D10
    - Files/Modules: `tests/contract/test_api_contracts.py`
    - Change Summary: Replace stub tests with real contract validations for auth/login, incidents CRUD, audit runs, users list, complaints CRUD
    - Definition of Done: 5 contract tests validate response schemas, status codes, required fields; tests catch breaking changes
    - Tests/Validation: Deliberately modify endpoint response; verify contract test fails
    - Observability: Contract test results in CI artifacts
    - Rollback: Revert to stubs
    - Risk of Change: Low
    - Dependencies: None
    - Owner Role: QA Engineer
    - Risk Reduction: {REL}
    - ROI: {Quality uplift, Risk avoided}
    - Out-of-Scope: Consumer-driven contract testing; Pact framework

### P2 Items

17. **[P2] (Effort L) (PS=8.2) Establish Load Testing Baseline**
    - CF(s): CF2, CF4
    - Dimension(s): D04, D25
    - Files/Modules: Create `tests/performance/` with k6 scripts; create `docs/performance/baseline.md`
    - Change Summary: k6 load tests for top 10 endpoints; baseline P95/P99 latency, throughput, error rate; fix actions in-memory pagination
    - Definition of Done: Load test suite runnable locally and in CI; baseline documented; actions pagination refactored to DB-level
    - Tests/Validation: Load test passes SLO thresholds
    - Observability: Performance metrics in Azure Monitor
    - Rollback: Revert actions pagination changes if regression
    - Risk of Change: Medium (actions refactoring)
    - Dependencies: SLO definitions (item #11)
    - Owner Role: Performance Engineer
    - Risk Reduction: {PERF, REL}
    - ROI: {Quality uplift, Risk avoided}
    - Out-of-Scope: Capacity planning; auto-scaling policies

18. **[P2] (Effort M) (PS=8.2) Comprehensive Environment Parity Validation**
    - CF(s): CF5
    - Dimension(s): D31
    - Files/Modules: `scripts/verify_env_sync.py`, docker-compose files, deploy workflows
    - Change Summary: Validate all config keys present across dev/staging/prod; verify PG versions match; add IaC for environment provisioning
    - Definition of Done: Environment parity script validates 100% config key coverage; all docker-compose files use same versions
    - Tests/Validation: Environment parity check in CI
    - Observability: Config drift alerts
    - Rollback: N/A (additive)
    - Risk of Change: Low
    - Dependencies: QW-06 (PG version fix)
    - Owner Role: DevOps Engineer
    - Risk Reduction: {REL}
    - ROI: {Risk avoided}
    - Out-of-Scope: Full Terraform/IaC migration

19. **[P2] (Effort M) (PS=8.2) Flesh Out Operational Runbooks**
    - CF(s): CF1, CF2, CF5
    - Dimension(s): D23, D32
    - Files/Modules: `docs/runbooks/` (expand skeletons)
    - Change Summary: Add detailed procedures, decision trees, screenshots, verification commands; add troubleshooting guides for common issues
    - Definition of Done: Each runbook tested via tabletop exercise; feedback incorporated
    - Tests/Validation: Tabletop exercise with on-call team
    - Observability: N/A
    - Rollback: N/A
    - Risk of Change: Low
    - Dependencies: QW-10 (skeleton creation)
    - Owner Role: SRE / Platform Engineer
    - Risk Reduction: {REL}
    - ROI: {Risk avoided, Time saved}
    - Out-of-Scope: Automated runbook execution

20. **[P2] (Effort M) (PS=8.2) Add Support Documentation**
    - CF(s): CF2
    - Dimension(s): D32
    - Files/Modules: Create `docs/support/`, `docs/troubleshooting/`
    - Change Summary: FAQ, common issues, diagnostic queries, log analysis guide
    - Definition of Done: Support docs cover top 10 support scenarios
    - Tests/Validation: Support team review
    - Observability: N/A
    - Rollback: N/A
    - Risk of Change: Low
    - Dependencies: None
    - Owner Role: Tech Lead / Support Engineer
    - Risk Reduction: {REL}
    - ROI: {Time saved}
    - Out-of-Scope: Self-service portal; chatbot

21. **[P2] (Effort S) (PS=6.5) Add WCAG 2.1 AA Checklist**
    - CF(s): CF2
    - Dimension(s): D03
    - Files/Modules: Create `docs/accessibility/wcag-checklist.md`
    - Change Summary: Document current a11y status against WCAG 2.1 AA criteria; identify gaps; prioritize fixes
    - Definition of Done: Checklist completed; top 10 violations identified
    - Tests/Validation: Manual screen reader testing of 3 critical flows
    - Observability: N/A
    - Rollback: N/A
    - Risk of Change: Low
    - Dependencies: QW-09 (axe-core results)
    - Owner Role: Frontend Engineer / UX Designer
    - Risk Reduction: {UX}
    - ROI: {Risk avoided, Quality uplift}
    - Out-of-Scope: Full WCAG AAA compliance

22. **[P2] (Effort M) (PS=6.5) Cost Optimization Analysis**
    - CF(s): CF4, CF5
    - Dimension(s): D26
    - Files/Modules: Create `docs/cost/azure-cost-analysis.md`
    - Change Summary: Azure spend breakdown; right-sizing recommendations; reserved instance analysis; FinOps practices document
    - Definition of Done: Monthly cost report process; optimization opportunities identified with $ impact
    - Tests/Validation: Cost alert thresholds validated
    - Observability: Azure Cost Management dashboard
    - Rollback: N/A
    - Risk of Change: Low
    - Dependencies: Azure billing access
    - Owner Role: DevOps / Finance
    - Risk Reduction: {COST}
    - ROI: {Cost reduction}
    - Out-of-Scope: Multi-cloud cost analysis

23. **[P2] (Effort M) (PS=5.4) Implement Backend i18n**
    - CF(s): CF2
    - Dimension(s): D27
    - Files/Modules: `src/core/i18n.py` (create), error messages, email templates
    - Change Summary: Add python-i18n or gettext; externalize user-facing strings in error responses and email templates
    - Definition of Done: All user-facing backend strings externalized; English locale file complete
    - Tests/Validation: Test with different locale settings
    - Observability: N/A
    - Rollback: Revert to hardcoded strings
    - Risk of Change: Medium — touches error handling and email service
    - Dependencies: None
    - Owner Role: Backend Engineer
    - Risk Reduction: {UX}
    - ROI: {Quality uplift}
    - Out-of-Scope: Full translation to other languages

24. **[P2] (Effort L) (PS=5.4) Implement Product Analytics**
    - CF(s): CF2
    - Dimension(s): D28
    - Files/Modules: Frontend analytics integration, backend event tracking
    - Change Summary: Integrate PostHog or Amplitude; track user journeys, feature usage, funnel completion; with GDPR consent
    - Definition of Done: Top 5 user journeys instrumented; dashboard available; consent mechanism in place
    - Tests/Validation: Verify events fire in staging; verify consent flow
    - Observability: Analytics dashboard
    - Rollback: Remove analytics SDK
    - Risk of Change: Low
    - Dependencies: Product team to define tracked events; legal for consent
    - Owner Role: Product Engineer
    - Risk Reduction: {UX}
    - ROI: {Revenue protection, Quality uplift}
    - Out-of-Scope: A/B testing framework

25. **[P2] (Effort S) (PS=5.0) UX Information Architecture Audit**
    - CF(s): CF2
    - Dimension(s): D02
    - Files/Modules: `frontend/src/App.tsx`, `frontend/src/components/`
    - Change Summary: Audit route structure and navigation; identify IA issues; propose improvements; document in `docs/ux/ia-audit.md`
    - Definition of Done: IA audit document with findings and recommendations
    - Tests/Validation: User testing with 3 representative users
    - Observability: N/A
    - Rollback: N/A
    - Risk of Change: Low (documentation only)
    - Dependencies: None
    - Owner Role: UX Designer
    - Risk Reduction: {UX}
    - ROI: {Quality uplift}
    - Out-of-Scope: UI redesign; component library

26. **[P2] (Effort S) (PS=4.6) Document User Journey Maps**
    - CF(s): CF2
    - Dimension(s): D01
    - Files/Modules: Create `docs/user-journeys/`
    - Change Summary: Define personas; map top 5 user journeys (incident reporter, auditor, risk manager, admin, portal user)
    - Definition of Done: Journey maps with steps, touchpoints, pain points, opportunities
    - Tests/Validation: Stakeholder review
    - Observability: N/A
    - Rollback: N/A
    - Risk of Change: Low
    - Dependencies: None
    - Owner Role: Product Manager / UX
    - Risk Reduction: {UX}
    - ROI: {Quality uplift}
    - Out-of-Scope: Customer research; survey design

27. **[P2] (Effort M) (PS=4.6) Compliance Certification Evidence Pack**
    - CF(s): CF2
    - Dimension(s): D08
    - Files/Modules: Create `docs/compliance/certification-status.md`, `docs/compliance/evidence-pack/`
    - Change Summary: Document ISO certification status; compile evidence pack; identify gaps for external audit
    - Definition of Done: Evidence pack ready for external auditor review
    - Tests/Validation: Internal audit review
    - Observability: N/A
    - Rollback: N/A
    - Risk of Change: Low
    - Dependencies: Compliance team
    - Owner Role: Compliance Manager
    - Risk Reduction: {GOV}
    - ROI: {Revenue protection}
    - Out-of-Scope: Actual certification audit

28. **[P2] (Effort M) (PS=4.6) Observability Dashboards**
    - CF(s): CF1-CF5
    - Dimension(s): D13
    - Files/Modules: Create `docs/observability/dashboards/`, Azure Monitor/Grafana templates
    - Change Summary: Create dashboard templates for: API health, DB performance, auth events, business metrics, SLO tracking
    - Definition of Done: 5 dashboards deployed and accessible to ops team
    - Tests/Validation: Dashboards show real data from staging
    - Observability: Meta-monitoring (dashboard health check)
    - Rollback: Remove dashboard definitions
    - Risk of Change: Low
    - Dependencies: SLO definitions (item #11)
    - Owner Role: SRE
    - Risk Reduction: {REL}
    - ROI: {Time saved, Risk avoided}
    - Out-of-Scope: Custom alerting rules (separate item)

29. **[P2] (Effort S) (PS=4.5) Add Down Migration CI Check**
    - CF(s): CF5
    - Dimension(s): D12, D05
    - Files/Modules: `.github/workflows/ci.yml` — add step in integration-tests job
    - Change Summary: After `alembic upgrade head`, run `alembic downgrade -1` and verify success
    - Definition of Done: CI verifies latest migration is reversible
    - Tests/Validation: Create non-reversible migration; verify CI catches it
    - Observability: CI artifacts
    - Rollback: Remove CI step
    - Risk of Change: Low
    - Dependencies: None
    - Owner Role: Backend Engineer
    - Risk Reduction: {REL, DATA}
    - ROI: {Risk avoided}
    - Out-of-Scope: Full migration chain reversibility testing

30. **[P2] (Effort M) (PS=4.5) Extend Idempotency to PUT/PATCH**
    - CF(s): CF3
    - Dimension(s): D24
    - Files/Modules: `src/api/middleware/idempotency.py`
    - Change Summary: Support `Idempotency-Key` header on PUT and PATCH methods; same Redis-backed caching and SHA-256 payload comparison
    - Definition of Done: PUT/PATCH with same Idempotency-Key returns cached response; 409 on payload mismatch
    - Tests/Validation: Integration tests for PUT/PATCH idempotency
    - Observability: `idempotency.cache_hit` and `idempotency.conflict` metrics
    - Rollback: Revert middleware change
    - Risk of Change: Low — backward compatible (only activates when header present)
    - Dependencies: None
    - Owner Role: Backend Engineer
    - Risk Reduction: {DATA, REL}
    - ROI: {Risk avoided}
    - Out-of-Scope: Distributed idempotency across services

31. **[P2] (Effort M) (PS=4.5) Chaos Test Suite for Circuit Breakers**
    - CF(s): CF1, CF4
    - Dimension(s): D05
    - Files/Modules: Create `tests/chaos/`, `tests/chaos/test_circuit_breakers.py`
    - Change Summary: Test DB disconnect, Redis failure, Azure AD outage scenarios; verify circuit breakers activate and services degrade gracefully
    - Definition of Done: Chaos tests for all 5 external integrations; all pass
    - Tests/Validation: Tests run in CI (optional/manual trigger)
    - Observability: Circuit breaker state changes logged
    - Rollback: Remove tests
    - Risk of Change: Low (test-only)
    - Dependencies: None
    - Owner Role: SRE
    - Risk Reduction: {REL}
    - ROI: {Risk avoided}
    - Out-of-Scope: Production chaos engineering; Chaos Monkey

32. **[P2] (Effort S) (PS=4.1) Refactor Actions In-Memory Pagination**
    - CF(s): CF2, CF3
    - Dimension(s): D04, D25
    - Files/Modules: `src/api/routes/actions.py`
    - Change Summary: Replace in-memory multi-entity fetch-sort-paginate with database-level UNION ALL + ORDER BY + LIMIT/OFFSET
    - Definition of Done: Actions list endpoint uses DB pagination; response identical to current for small datasets
    - Tests/Validation: Performance test with 10K actions; compare response time before/after
    - Observability: `actions.query_time_ms` histogram
    - Rollback: Revert to in-memory pagination
    - Risk of Change: Medium — query correctness across 6 entity types
    - Dependencies: None
    - Owner Role: Backend Engineer
    - Risk Reduction: {PERF, REL}
    - ROI: {Quality uplift}
    - Out-of-Scope: Cursor-based pagination

33. **[P2] (Effort S) (PS=3.0) API Pagination Audit**
    - CF(s): CF2
    - Dimension(s): D10
    - Files/Modules: All route files in `src/api/routes/`
    - Change Summary: Audit all list endpoints; ensure consistent pagination (limit/offset with max_limit=100); document in API standards
    - Definition of Done: All list endpoints have pagination; API standards document updated
    - Tests/Validation: Contract tests verify pagination parameters
    - Observability: N/A
    - Rollback: N/A (additive)
    - Risk of Change: Low
    - Dependencies: None
    - Owner Role: Backend Engineer
    - Risk Reduction: {PERF}
    - ROI: {Quality uplift}
    - Out-of-Scope: Cursor-based pagination migration

34. **[P2] (Effort S) (PS=3.0) Clean Up alembic.ini Placeholder**
    - CF(s): CF5
    - Dimension(s): D12
    - Files/Modules: `alembic.ini`
    - Change Summary: Replace `sqlalchemy.url = driver://user:pass@localhost/dbname` with comment explaining runtime override
    - Definition of Done: No misleading placeholder; comment documents env.py override mechanism
    - Tests/Validation: `alembic upgrade head` still works
    - Observability: N/A
    - Rollback: Revert
    - Risk of Change: Low
    - Dependencies: None
    - Owner Role: Backend Engineer
    - Risk Reduction: {GOV}
    - ROI: {Quality uplift}
    - Out-of-Scope: Alembic configuration refactoring

35. **[P2] (Effort L) (PS=3.0) Storybook Component Library**
    - CF(s): CF2
    - Dimension(s): D02, D09
    - Files/Modules: `frontend/`, create `.storybook/` config
    - Change Summary: Set up Storybook; document top 20 reusable components; add visual regression tests
    - Definition of Done: Storybook published; 20 components documented; visual tests in CI
    - Tests/Validation: Chromatic or Percy visual regression
    - Observability: N/A
    - Rollback: Remove Storybook config
    - Risk of Change: Low (additive)
    - Dependencies: Design system decisions
    - Owner Role: Frontend Engineer
    - Risk Reduction: {UX}
    - ROI: {Quality uplift, Time saved}
    - Out-of-Scope: Design tokens; full design system

---

## 10. Acceptance-Test Matrix (World-Class Proof)

| CF | E2E Tests | Integration Tests | Unit Tests | Chaos/Failure Tests | Observability Checks | Release Checks |
|----|-----------|-------------------|------------|--------------------|--------------------|----------------|
| **CF1: Auth** | Login→token→access→refresh→logout; Azure AD SSO flow; password reset E2E | Multi-tenant isolation; role-based access for all 48 route modules; token expiry handling | JWT encode/decode; password hashing; Azure AD JWKS validation; rate limiter logic | Redis down → fallback; Azure AD JWKS unreachable → cached keys; brute-force protection | auth.login_success/failure counters; auth.token_refresh; rate_limit.exceeded | Post-deploy auth enforcement check; security headers validated; CVE fix verification |
| **CF2: Business Workflows** | Incident lifecycle E2E (report→investigate→action→close); audit lifecycle (template→run→finding→CAPA); risk assessment workflow | Reference number generation with concurrency; investigation optimistic locking; CAPA state machine transitions | Risk scoring engine; workflow engine state transitions; email service templating | DB disconnect during incident save → circuit breaker; blob storage failure → evidence upload retry | business.incident_created; business.audit_completed; business.risk_assessed; API P95 latency | Post-deploy smoke: health, incident create, audit template list |
| **CF3: Data Writes** | Multi-step write with idempotency key; concurrent investigation edit (409 conflict) | Idempotency middleware with payload hash; optimistic locking with version mismatch; transaction rollback | SHA-256 hash computation; audit trail hash chain; enum constraint validation | Redis down during idempotency check → passthrough; DB transaction timeout → rollback | data.idempotency_hit/conflict; data.optimistic_lock_retry; data.write_duration_ms | Post-deploy: verify idempotency middleware active |
| **CF4: External Integrations** | Email round-trip (send→receive); blob upload→download | Azure AD token exchange; blob storage upload/download/SAS; email SMTP delivery | Circuit breaker state machine; retry with backoff logic; timeout wrapper | Azure Blob 503 → circuit opens → fallback; Gemini AI timeout → graceful degradation | integration.azure_blob.latency; integration.email.delivery_rate; circuit_breaker.state_change | Post-deploy: Azure AD token exchange functional; blob storage accessible |
| **CF5: Release/Deploy** | Staging deploy→smoke→E2E→production deploy→verify; rollback drill | Migration up/down; config fail-fast; deterministic build verification | Release signoff validation; security waiver parsing; gate summary generation | Migration failure → deploy abort → rollback; health check timeout → deploy fail | deploy.duration_ms; deploy.health_check_attempts; deploy.rollback_count | 5-phase deploy proof; deterministic SHA (3 matches); post-deploy security checks |

---

## 11. World-Class Checklist (9.5+ Observable Criteria)

| ID | Dimension | Observable 9.5+ Criteria |
|----|-----------|------------------------|
| D01 | Product clarity | Documented personas + top 5 journey maps with measured NPS/CSAT; OpenAPI 100% coverage with examples; user story acceptance criteria in all PRs |
| D02 | UX quality | Storybook with 80%+ component coverage; design tokens documented; Lighthouse UX score ≥ 90; user testing evidence for all major flows |
| D03 | Accessibility | WCAG 2.1 AA certified; axe-core zero violations in CI; screen reader testing evidence; keyboard navigation verified on all forms |
| D04 | Performance | P95 latency < 200ms for top 10 endpoints (load test evidence); Lighthouse perf ≥ 90; zero in-memory pagination; CDN for static assets |
| D05 | Reliability | Chaos tests pass for all external dependencies; SLO ≥ 99.9% measured over 90 days; automated failover for DB + Redis; DLQ depth always < 10 |
| D06 | Security | Zero unauthenticated endpoints (proven by regression test); zero cross-tenant queries (proven by isolation test); annual penetration test report; OWASP Top 10 mitigation evidence |
| D07 | Privacy | DPIA for all PII-processing modules; DSAR endpoint with <72h SLA; data classification applied to all models; consent tracking operational |
| D08 | Compliance | External audit report with zero major findings; cross-standard gap analysis at 95%+ coverage; management review evidence < 90 days old |
| D09 | Architecture | Zero mypy overrides (all modules type-safe); all business logic in service layer (zero in route handlers); dependency injection audit clean; module coupling metrics |
| D10 | API design | OpenAPI spec validated in CI; cursor-based pagination on all list endpoints; 100% idempotency coverage on mutations; versioning strategy documented and enforced |
| D11 | Data model | Zero JSON columns for structured data (all normalized); all models have audit trail mixin; data dictionary documented; ERD auto-generated and current |
| D12 | Schema versioning | All migrations reversible (CI-verified); migration naming convention enforced; zero placeholder configs; schema diff report per PR |
| D13 | Observability | SLOs defined and tracked with dashboards; alerting on SLO breach < 5min; distributed tracing with 100% coverage in staging; log-based metrics for all CFs |
| D14 | Error handling | Unified error envelope on 100% of endpoints; zero unhandled exceptions in production (tracked via error budget); circuit breaker coverage for all external calls |
| D15 | Testing | Coverage ≥ 80% with behavioral tests; mutation testing score ≥ 70%; contract tests for all public API endpoints; E2E covering all CFs; zero flaky tests |
| D16 | Test data | Factory coverage for all 27 domain models; PII-safe test data generation; seed data scripts for all environments; snapshot testing for complex queries |
| D17 | CI quality | All quality gates blocking; zero allowed-failure jobs; custom validation scripts for all governance rules; CI runtime < 15min | ✅ AT 10.0
| D18 | CD/release | Blue/green or canary deployment; automated rollback on health check failure; feature flag-gated releases; zero-downtime deploys proven | ✅ AT 10.0
| D19 | Config management | Dynamic config reload without restart; feature flags with analytics; config versioning with audit trail; environment config drift detection |
| D20 | Dependency management | Lockfile committed and verified; automated dependency updates with test verification; license compliance check; SBOM published per release |
| D21 | Code quality | Zero mypy overrides; zero type-ignore pragmas above ceiling; Semgrep zero findings; cognitive complexity limits enforced; code review SLA < 24h |
| D22 | Documentation | ADR for every architectural decision; API guide with examples; developer onboarding guide < 1 day; runbooks for all operational scenarios; CHANGELOG automated |
| D23 | Operational runbooks | Runbooks for all CFs; tested via quarterly drills; incident response SLA defined and measured; on-call rotation documented |
| D24 | Data integrity | Idempotency on all mutations; database-level constraints for all enums; automated data consistency checks; zero orphaned records |
| D25 | Scalability | Load test evidence for 10x current traffic; horizontal scaling verified; database sharding strategy documented; capacity planning reviewed quarterly |
| D26 | Cost efficiency | Monthly FinOps review; right-sizing recommendations implemented; cost per transaction tracked; reserved instance coverage > 70% |
| D27 | I18n/L10n | Backend + frontend i18n; 100% string externalization; RTL support verified; 2+ language support with CI key validation |
| D28 | Analytics/telemetry | Product analytics on all user journeys; funnel conversion tracked; A/B testing framework operational; data-driven feature prioritization evidence |
| D29 | Governance | ADR for all decisions; CHANGELOG automated; quarterly architecture review; governance dashboard with compliance metrics |
| D30 | Build determinism | Lockfile committed; digest-pinned images; SBOM per release; reproducible build verification (bit-for-bit where possible) | ✅ AT 10.0
| D31 | Environment parity | IaC for all environments; drift detection in CI; identical versions across dev/staging/prod; config key coverage 100% |
| D32 | Supportability | Support runbooks for top 20 issues; diagnostic API endpoints; log analysis guide; mean-time-to-diagnose tracked |

---

## Appendix B: Risk & ROI Tags Summary

| Risk Reduction Tag | Count | Backlog Items |
|-------------------|-------|---------------|
| SEC (Security) | 7 | #2, #3, #4, #5, #13, #15 |
| REL (Reliability) | 12 | #1, #6, #8, #10, #11, #14, #17, #18, #19, #28, #29, #31 |
| DATA (Data Integrity) | 3 | #4, #29, #30 |
| PERF (Performance) | 3 | #17, #32, #33 |
| GOV (Governance) | 4 | #7, #9, #27, #34 |
| UX (User Experience) | 6 | #12, #21, #23, #24, #25, #26 |
| COST (Cost) | 1 | #22 |

| ROI Tag | Count |
|---------|-------|
| Risk avoided | 16 |
| Quality uplift | 14 |
| Time saved | 4 |
| Revenue protection | 3 |
| Cost reduction | 1 |

---

## Appendix C: No-Scope-Creep Guardrails

Each backlog item includes an explicit "Out-of-Scope" line. Key guardrails:
- Security fixes (items #2-5) scope to auth enforcement only, NOT RBAC policy redesign
- Testing items (#6, #8, #16) scope to current test framework, NOT new testing framework adoption
- Documentation items (#7, #9, #10) scope to specific documents, NOT comprehensive documentation overhaul
- Infrastructure items (#17, #18) scope to validation, NOT IaC migration
- Performance items (#17, #32) scope to measurement + specific fixes, NOT architecture redesign
