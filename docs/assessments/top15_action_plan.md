# Quality Governance Platform — Top 15 World-Class Focus Areas

**Created**: 2026-03-07
**Input**: Full 32-dimension assessment (WCS avg 6.5/10.0, 3 of 32 at world-class)
**Method**: 3 rounds of check & challenge applied (documented below)

---

## Structure

15 focus areas grouped into 3 categories:
- **Category A (5): Low Effort / High Value** — maximum WCS lift per hour invested
- **Category B (5): Critical Workflows** — protect and harden the business-critical paths
- **Category C (5): UI & UX** — user-facing quality, accessibility, and measurement

Each focus area contains: rationale, specific tasks, files, DoD, WCS impact, and sequencing.

---

## Category A: Low Effort / High Value

### A1. Security Auth Hardening
**Priority**: P0 | **Effort**: Small | **WCS Impact**: D06 7.2 → ~8.6
**Why first**: Three P0 findings (F-001, F-002, F-003) represent the most severe gaps in the platform. Unauthenticated endpoints and cross-tenant data access are existential risks. Each fix is 1-3 lines of code per endpoint.

| Task | File(s) | Change |
|------|---------|--------|
| Restore auth guards on tenant endpoints | `src/api/routes/tenants.py` | Add `current_user: User = Depends(get_current_active_user)` to all functions; `CurrentSuperuser` on create/delete |
| Add auth to compliance endpoints | `src/api/routes/compliance.py` | Add `CurrentUser` dependency to unauthenticated endpoints |
| Create auth enforcement regression test | `tests/security/test_auth_enforcement.py` (new) | Iterate all registered routes → assert 401 without token; explicit exempt list |
| Create auth coverage CI script | `scripts/validate_auth_coverage.py` (new) | Parse route modules → verify auth dependency → CI gate |

**Definition of Done**: Zero unauthenticated non-exempt endpoints; CI regression test passes; Swagger UI confirms 401 on every protected route.
**Out of Scope**: RBAC/ABAC policy redesign; permission model changes.

---

### A2. Tenant Data Isolation
**Priority**: P0 | **Effort**: Medium | **WCS Impact**: D06 +0.4, D07 +0.3
**Why**: Cross-tenant data leakage on incidents and complaints = GDPR breach risk. The audit module already has correct tenant filtering — this applies the same proven pattern.

| Task | File(s) | Change |
|------|---------|--------|
| Add tenant_id filter to incident queries | `src/api/routes/incidents.py` | `.filter(Incident.tenant_id == current_user.tenant_id)` on list/get |
| Add tenant_id filter to complaint queries | `src/api/routes/complaints.py` | Same pattern |
| Backfill null tenant_ids | `alembic/versions/` (new migration) | UPDATE incidents SET tenant_id = (default tenant) WHERE tenant_id IS NULL |
| Multi-tenant isolation test | `tests/security/test_tenant_isolation.py` (new) | Create data in Tenant A and B; verify A cannot see B |
| Audit remaining route modules | All `src/api/routes/*.py` | Verify tenant_id filtering on every list endpoint |

**Definition of Done**: All list endpoints filter by tenant_id; integration test proves isolation between tenants; null tenant_ids backfilled.
**Out of Scope**: Row-Level Security at PostgreSQL level (Horizon B); tenant provisioning workflow.

---

### A3. Test Reliability Restoration
**Priority**: P1 | **Effort**: Medium | **WCS Impact**: D15 5.4 → ~7.0, D21 +0.5
**Why**: The test suite is the foundation for every other improvement. Currently it has a split personality: pyproject.toml says 50% coverage but CI enforces 35%; many tests silently skip on import errors giving a false green signal. Fix the harness before adding new tests.

| Task | File(s) | Change |
|------|---------|--------|
| Fix broken imports in unit tests | `tests/unit/test_models.py`, `test_services.py` | Update import paths to match current model/service exports |
| Remove skip_on_import_error decorators | Same files | Replace skip decorators with actual imports |
| Align CI coverage to 50% | `.github/workflows/ci.yml` | Change `--cov-fail-under=35` to `--cov-fail-under=50` |
| Add skipped test ceiling | `.github/workflows/ci.yml`, `scripts/validate_skipped_tests.py` (new) | CI gate: fail if skipped count > ceiling (ratchet down each sprint) |
| Write behavioral tests for 3 critical services | `tests/unit/` (new files) | Test incident reference generation, risk scoring logic, audit score calculation |

**Definition of Done**: CI enforces 50% coverage; zero unexplained skipped tests; 3 new behavioral unit tests for critical business logic.
**Out of Scope**: Reaching 80% coverage (Horizon C); mutation testing; new test framework adoption.

---

### A4. Governance Documentation Sprint
**Priority**: P1 | **Effort**: Small | **WCS Impact**: D23 3.0 → ~6.0, D29 5.4 → ~7.5, D22 5.4 → ~7.0
**Why**: The platform has mature CI/CD and governance *automation* but near-zero governance *documentation*. ADRs are referenced in code but don't exist. No runbooks. No changelog. All are small additive writes with outsized impact on 3 dimensions simultaneously.

| Task | File(s) | Change |
|------|---------|--------|
| Write ADR-0001: Production Dependencies | `docs/adr/ADR-0001-production-dependencies.md` (new) | Context, Decision, Consequences per code references |
| Write ADR-0002: Config Fail-Fast | `docs/adr/ADR-0002-config-failfast.md` (new) | Document production validation rules |
| Write ADR-0003: Readiness Probe | `docs/adr/ADR-0003-readiness-probe.md` (new) | Document DB check in /readyz |
| Create CHANGELOG.md | `CHANGELOG.md` (new) | Keep-a-Changelog format; v1.0.0 retroactive entry |
| Create 5 runbook skeletons | `docs/runbooks/` (new): `incident-response.md`, `deployment.md`, `rollback.md`, `database-recovery.md`, `escalation.md` | Trigger, procedure, contacts, verification per runbook |
| Add ADR reference validation | `scripts/validate_adr_references.py` (new) | CI check: all ADR-NNNN refs in code resolve to files |

**Definition of Done**: 3 ADRs written; CHANGELOG linked from README; 5 runbooks peer-reviewed; CI validates ADR references.
**Out of Scope**: Automated changelog generation; full architecture documentation; writing ADRs for every historical decision.

---

### A5. Environment & Config Hygiene
**Priority**: P1 | **Effort**: Small | **WCS Impact**: D31 5.4 → ~6.5, D12 +0.2
**Why**: Three contradictions (C-001, C-002, C-003) were identified during assessment. Each is a trivial fix but collectively they erode confidence in environment parity and can mask production issues.

| Task | File(s) | Change |
|------|---------|--------|
| Fix sandbox Postgres version | `docker-compose.sandbox.yml` | `postgres:15-alpine` → `postgres:16-alpine` |
| Clean alembic.ini placeholder | `alembic.ini` | Replace `driver://user:pass@localhost/dbname` with documented comment |
| Add env parity CI check | `scripts/verify_env_sync.py` (enhance), `.github/workflows/ci.yml` | Validate all docker-compose files use same PG major version |
| Define SLO/SLI document | `docs/observability/slo-definitions.md` (new) | Availability 99.9%, P95 latency <500ms, error rate <1%, auth success >99.5% |

**Definition of Done**: All docker-compose files on PG16; zero misleading placeholder configs; SLOs defined and measurable with existing Azure Monitor metrics.
**Out of Scope**: IaC/Terraform migration; dynamic config reload; error budget policies.

---

## Category B: Critical Workflows

### B1. API Contract Stability
**Priority**: P1 | **Effort**: Medium | **WCS Impact**: D15 +0.5, D10 +0.3
**Why**: Contract tests exist in CI but are stubs (`pass`). The platform has 48 route modules and an active frontend — any backend API change could silently break the frontend. The OpenAPI contract check job exists but needs real tests backing it.

| Task | File(s) | Change |
|------|---------|--------|
| Implement auth/login contract | `tests/contract/test_api_contracts.py` | Validate request schema, response shape (access_token, refresh_token, token_type), status codes (200, 401) |
| Implement incidents CRUD contract | Same file | Validate list pagination, create response, field presence (id, reference_number, status, created_at) |
| Implement audits/runs contract | Same file | Validate template list, run create, response shapes |
| Implement users list contract | Same file | Validate pagination, user shape (id, email, roles), 403 for non-superuser |
| Implement complaints contract | Same file | Validate create with external_ref idempotency (409 on dup), field shapes |
| Nightly contract verification | `.github/workflows/nightly-contract-verification.yml` (enhance) | Point to real tests |

**Definition of Done**: 5 endpoint contracts validate schemas, status codes, required fields; CI catches breaking changes; nightly verification runs.
**Out of Scope**: Consumer-driven contracts (Pact); GraphQL; full OpenAPI schema diffing (already exists).

---

### B2. Type Safety Remediation (GOVPLAT-004)
**Priority**: P1 | **Effort**: Medium-Large | **WCS Impact**: D21 6.0 → ~7.5, D09 +0.3
**Why**: 27 modules have mypy errors suppressed. These aren't cosmetic — `attr-defined`, `arg-type`, and `return-value` errors in `workflow_engine.py` and `risk_scoring.py` indicate potential runtime bugs in critical business logic. Fixing types also improves IDE support and refactoring confidence.

| Task | File(s) | Change |
|------|---------|--------|
| Fix workflow_engine types | `src/services/workflow_engine.py`, `pyproject.toml` | Resolve assignment, var-annotated, arg-type, operator errors; remove override |
| Fix risk_scoring types | `src/services/risk_scoring.py`, `pyproject.toml` | Resolve attr-defined, index, operator errors; remove override |
| Fix ai_predictive_service | `src/domain/services/ai_predictive_service.py`, `pyproject.toml` | Resolve attr-defined, arg-type, return-value errors |
| Fix redis_cache types | `src/infrastructure/cache/redis_cache.py`, `pyproject.toml` | Resolve misc, attr-defined, return-value, assignment errors |
| Fix 6 route modules | `src/api/routes/{uvdb,planet_mark,document_control,risk_register,near_miss,kri}.py` | Resolve route-specific type errors; remove overrides |
| Reduce override ceiling | `pyproject.toml` | Set ceiling comment: "Target: <15 by end of Q2" |

**Definition of Done**: Override count reduced from 27 to ≤17; fixed modules pass `mypy --strict`; existing tests pass.
**Out of Scope**: Full strict mypy across all modules; rewriting AI services; changing function signatures.

---

### B3. Data Write Safety
**Priority**: P1-P2 | **Effort**: Medium | **WCS Impact**: D24 +0.3, D04 +0.5, D25 +0.3
**Why**: Two architectural issues in the data write path: (1) idempotency only covers POST, not PUT/PATCH — partial updates can be duplicated; (2) the actions module fetches ALL records from 6 entity types into memory, then sorts and paginates in Python — this will fail silently on large datasets.

| Task | File(s) | Change |
|------|---------|--------|
| Extend idempotency to PUT/PATCH | `src/api/middleware/idempotency.py` | Include PUT/PATCH in method check when `Idempotency-Key` header present |
| Refactor actions pagination | `src/api/routes/actions.py` | Replace in-memory multi-entity fetch-sort-paginate with UNION ALL + ORDER BY + LIMIT/OFFSET at DB level |
| Add idempotency metrics | `src/infrastructure/monitoring/azure_monitor.py` | `idempotency.cache_hit`, `idempotency.conflict`, `idempotency.fallback` counters |
| Performance test actions endpoint | `tests/performance/test_actions_pagination.py` (new) | Verify response time with 1K, 5K, 10K records |

**Definition of Done**: PUT/PATCH with Idempotency-Key returns cached response; actions endpoint uses DB-level pagination; performance test shows <500ms at 10K records.
**Out of Scope**: Cursor-based pagination; distributed idempotency; CQRS.

---

### B4. Observability & Operational Readiness
**Priority**: P1 | **Effort**: Medium | **WCS Impact**: D13 7.2 → ~8.5, D23 +1.0, D32 +0.5
**Why**: The platform has excellent metric instrumentation (26+ counters in Azure Monitor) but no dashboards, no alerting rules in code, and no SLO tracking. This means the data exists but nobody is watching it. Connecting the dots turns passive instrumentation into active operations.

| Task | File(s) | Change |
|------|---------|--------|
| Create API health dashboard template | `docs/observability/dashboards/api-health.json` (new) | Request rate, P95/P99 latency, error rate, top 5 slowest endpoints |
| Create auth & security dashboard | `docs/observability/dashboards/auth-security.json` (new) | Login success/failure, rate limit hits, token refresh rate, auth errors |
| Create business metrics dashboard | `docs/observability/dashboards/business-metrics.json` (new) | Incidents created/resolved, audits completed, risk assessments, CAPA cycle time |
| Add DLQ depth alerting | `src/infrastructure/tasks/dlq.py` | Alert when DLQ depth > 10; metric `celery.dlq_depth` |
| Add circuit breaker state alerts | `src/infrastructure/resilience/` | Log + metric on state transitions (closed→open, open→half-open) |
| Flesh out deployment runbook | `docs/runbooks/deployment.md` | Full procedure from PR merge → staging → production with verification steps |

**Definition of Done**: 3 dashboard templates deployable to Azure Monitor; DLQ and circuit breaker alerts active; deployment runbook tested via tabletop.
**Out of Scope**: Custom alerting framework; PagerDuty integration; auto-remediation.

---

### B5. Schema & Migration Safety
**Priority**: P2 | **Effort**: Small | **WCS Impact**: D12 +0.3, D05 +0.2, D07 +0.5
**Why**: 62 migrations in 2 months is impressive velocity but down-migrations are never verified. If a production deploy fails after migration, the rollback path is unproven. Also, incident/complaint data contains PII with no formal DPIA — a compliance gap that a single document closes.

| Task | File(s) | Change |
|------|---------|--------|
| Add down migration CI check | `.github/workflows/ci.yml` (integration-tests job) | After `alembic upgrade head`, run `alembic downgrade -1`, verify success |
| Verify latest 5 migrations reversible | Manual verification | Run downgrade for each of the 5 most recent migrations |
| Write DPIA for incident data | `docs/privacy/dpia-incidents.md` (new) | Data inventory, processing purpose, legal basis, risk assessment, mitigations |
| Write data classification policy | `docs/privacy/data-classification.md` (new) | Classification levels (Public, Internal, Confidential, Restricted); model-level tagging |

**Definition of Done**: CI verifies latest migration is reversible; DPIA completed for incident/complaint modules; data classification levels defined.
**Out of Scope**: DSAR automation endpoint; full privacy-by-design retrofit; consent management platform.

---

## Category C: UI & UX

### C1. Accessibility Automation
**Priority**: P1 | **Effort**: Small-Medium | **WCS Impact**: D03 3.0 → ~5.5
**Why**: Accessibility is at WCS 3.0 — the joint-lowest score. The frontend already uses Radix UI (accessible primitives) and has jsx-a11y linting, but there's no runtime accessibility testing. Adding axe-core to CI catches 40-60% of WCAG 2.1 violations automatically with minimal setup.

| Task | File(s) | Change |
|------|---------|--------|
| Install vitest-axe | `frontend/package.json` | Add `vitest-axe` or `@axe-core/react` as dev dependency |
| Add axe assertions to component tests | `frontend/src/**/*.test.tsx` | Add `expect(container).toHaveNoViolations()` to existing render tests |
| Add a11y CI step | `.github/workflows/ci.yml` (frontend-tests job) | Run axe assertions; initially as warnings, blocking after 2 weeks |
| Create WCAG 2.1 AA checklist | `docs/accessibility/wcag-checklist.md` (new) | Audit current state against WCAG 2.1 AA; identify top 20 violations |
| Fix top 10 violations | Various frontend components | Address color contrast, missing labels, keyboard traps, aria attributes |

**Definition of Done**: axe-core runs in CI (blocking mode); WCAG checklist completed; top 10 violations fixed.
**Out of Scope**: Full WCAG AAA; screen reader testing lab; native mobile accessibility.

---

### C2. User Journey Clarity
**Priority**: P2 | **Effort**: Small | **WCS Impact**: D01 7.2 → ~8.2
**Why**: The platform serves 5 distinct user types across 82 pages, but there are no documented personas or journey maps. Without these, UX improvements are guesswork. This is a documentation exercise, not a code change — small effort, high strategic value.

| Task | File(s) | Change |
|------|---------|--------|
| Define 5 personas | `docs/user-journeys/personas.md` (new) | Incident Reporter (field worker), Auditor (quality manager), Risk Manager, Admin (system admin), Portal User (anonymous/external) |
| Map incident reporting journey | `docs/user-journeys/journey-incident.md` (new) | Entry point → form → submit → track → resolve; pain points and opportunities |
| Map audit lifecycle journey | `docs/user-journeys/journey-audit.md` (new) | Template build → schedule → execute (mobile) → findings → CAPA |
| Map risk assessment journey | `docs/user-journeys/journey-risk.md` (new) | Identify → assess (5x5 matrix) → control → monitor KRI → report |
| Map admin configuration journey | `docs/user-journeys/journey-admin.md` (new) | User management → form builder → lookup tables → system settings |
| Map portal submission journey | `docs/user-journeys/journey-portal.md` (new) | Anonymous access → incident/complaint form → track status |

**Definition of Done**: 5 personas defined with goals, frustrations, tech comfort; 5 journey maps with steps, touchpoints, pain points, improvement opportunities.
**Out of Scope**: Customer research interviews; survey design; A/B testing.

---

### C3. Information Architecture Audit
**Priority**: P2 | **Effort**: Small | **WCS Impact**: D02 4.5 → ~5.5
**Why**: The frontend has 82 lazy-loaded pages across 6 route groups (Portal, Core, Governance, Analytics, Workforce, Admin). Without an IA audit, it's unclear whether navigation makes sense to users or whether pages are discoverable. This is the diagnostic step before any UI redesign.

| Task | File(s) | Change |
|------|---------|--------|
| Map current IA from routes | `docs/ux/ia-current.md` (new) | Extract full sitemap from `frontend/src/App.tsx`; categorize by user role access |
| Identify navigation depth issues | Same document | Flag pages > 3 clicks from dashboard; flag orphan pages |
| Cross-reference with personas | Same document | Which persona uses which pages? Are core tasks within 2 clicks? |
| Propose IA improvements | `docs/ux/ia-recommendations.md` (new) | Recommended restructuring; quick-access shortcuts; role-based navigation |
| Validate with 3 representative users | Meeting notes / recorded sessions | Task-based usability test: "find and submit an incident", "create an audit template", "view risk heatmap" |

**Definition of Done**: Current IA documented; pain points identified; improvement recommendations prioritized; validated with at least 3 users.
**Out of Scope**: UI redesign implementation; new navigation component; mobile app IA.

---

### C4. Design System Foundation
**Priority**: P2 | **Effort**: Medium-Large | **WCS Impact**: D02 +1.0, D09 +0.2
**Why**: The frontend uses Radix UI + TailwindCSS + Lucide icons but has no Storybook, no design tokens, and no visual regression testing. A design system prevents UX inconsistency across 82 pages and speeds up feature development by providing documented, tested building blocks.

| Task | File(s) | Change |
|------|---------|--------|
| Set up Storybook | `frontend/.storybook/` (new config) | Storybook 8 + Vite builder + TailwindCSS integration |
| Document 20 core components | `frontend/src/components/**/*.stories.tsx` (new) | Buttons, inputs, selects, modals, tables, cards, badges, navigation, forms, alerts, toasts, loading states |
| Define design tokens | `frontend/src/lib/tokens.ts` (new) | Colors, spacing, typography, shadows, border radius — single source of truth |
| Add visual regression testing | `frontend/package.json`, CI config | Chromatic or Percy integration; snapshot on PR |
| Create component usage guide | `docs/ux/component-guide.md` (new) | When to use which component; composition patterns; dos and don'ts |

**Definition of Done**: Storybook deployed (Chromatic or static); 20 components documented with variants; visual regression in CI; design tokens extracted.
**Out of Scope**: Full rebrand; new icon set; component rewrite; mobile-specific components.

---

### C5. Frontend Quality & Measurement
**Priority**: P2 | **Effort**: Medium | **WCS Impact**: D28 5.4 → ~7.0, D04 +0.3
**Why**: The platform has web-vitals in `package.json` and a telemetry API route, but no product analytics tracking actual user behavior. Without measurement, you can't know which features are used, where users drop off, or whether UX changes improve anything.

| Task | File(s) | Change |
|------|---------|--------|
| Capture web-vitals baseline | `frontend/src/` (vitals reporter) | Send LCP, FID, CLS, TTFB to backend telemetry endpoint; establish baselines |
| Instrument top 5 user journeys | Frontend pages for incidents, audits, risks, portal, admin | Track page views, form starts/completions, time-on-task, error encounters |
| Create analytics dashboard | `docs/ux/analytics-baseline.md` (new) | Document baseline metrics; define improvement targets |
| Add Lighthouse CI | `.github/workflows/ci.yml` or separate workflow | Performance score ≥ 80, Accessibility ≥ 80, Best Practices ≥ 90 |
| Implement error boundary telemetry | `frontend/src/components/ErrorBoundary.tsx` (enhance) | Send error boundary catches to telemetry endpoint with route context |

**Definition of Done**: Web-vitals baseline captured and documented; Lighthouse CI gate active; error boundary telemetry operational; top 5 journeys instrumented.
**Out of Scope**: PostHog/Amplitude integration (evaluate later); A/B testing framework; user surveys.

---

## Three Rounds of Check & Challenge

### Round 1: Coverage Verification

| Concern | Covered By | Verdict |
|---------|-----------|---------|
| **Codebase quality** | A3 (test reliability), B2 (type safety), B1 (contracts) | ✓ Covered |
| **Workflows / business logic** | B1 (API contracts), B3 (data writes), B4 (observability) | ✓ Covered |
| **API layer** | A1 (auth), A2 (tenant isolation), B1 (contracts), B3 (idempotency) | ✓ Covered |
| **Frontend** | C1 (a11y), C3 (IA audit), C4 (design system), C5 (measurement) | ✓ Covered |
| **Backend** | A1-A2 (security), B2 (types), B3 (data), B5 (migrations/privacy) | ✓ Covered |
| **Infrastructure/DevOps** | A5 (env parity), B4 (dashboards), B5 (migration CI) | ✓ Covered |
| **Documentation/Governance** | A4 (ADRs, changelog, runbooks) | ✓ Covered |
| **Security** | A1 (auth), A2 (tenant), B5 (DPIA) | ✓ Covered |
| **All 3 P0 findings** | A1 (F-001, F-002), A2 (F-003) | ✓ Covered |
| **All 5 P1 findings** | A3 (F-004, F-006), A4 (F-007), B1 (F-005), B2 (F-008) | ✓ Covered |

**Round 1 Adjustments**: None needed — all areas covered. Verified each P0 and P1 finding maps to a focus area.

---

### Round 2: Sequencing & Dependency Validation

| Dependency | Valid? | Adjustment |
|-----------|--------|------------|
| A1 must complete before A2 | ✓ Yes — need auth working before adding tenant filters | No change |
| A3 must complete before B1 | ✓ Yes — fix test harness before adding new tests | No change |
| A5 SLOs inform B4 dashboards | ✓ Yes — define what to measure before building dashboards | No change |
| C1 axe-core informs C3 IA audit | ✓ Yes — accessibility data feeds into IA assessment | No change |
| C2 personas inform C3 IA audit | ✓ Yes — need to know users before auditing their navigation | No change |
| B2 type fixes could reveal B3 bugs | ⚠ Possible — type fixes in workflow_engine could surface data write issues | **Added note**: Run B3 data write tests after B2 type fixes |

**Recommended Execution Order**:
```
Week 1-2: A1 → A2 → A4 → A5 (parallel: C2)
Week 2-3: A3 → B1 (parallel: C1)
Week 3-4: B2 → B3 (parallel: C3)
Week 4-6: B4 → B5 (parallel: C4 → C5)
```

**Round 2 Adjustments**: Added B2→B3 coupling note. Verified no circular dependencies.

---

### Round 3: Effort-Value Reality Check

| Focus Area | Stated Effort | Challenge Question | Verdict |
|-----------|--------------|-------------------|---------|
| A1: Auth hardening | Small | "Is adding auth truly 1-3 lines per endpoint?" | ✓ Yes — FastAPI DI pattern, proven in other route modules |
| A2: Tenant isolation | Medium | "What about null tenant_ids in existing data?" | ✓ Covered — migration included in tasks; graceful null handling specified |
| A3: Test reliability | Medium | "Can you reach 50% coverage just by fixing skips?" | ⚠ Maybe not — added 3 behavioral test writes to ensure threshold is met |
| A4: Governance docs | Small | "Are 5 runbook skeletons enough?" | ✓ Yes for initial WCS lift — fleshing out is B4/B5 territory |
| A5: Config hygiene | Small | "Does changing PG 15→16 risk integration test breakage?" | ✓ No — PG16 is backward compatible; the rest of the stack already uses PG16 |
| B1: Contract tests | Medium | "5 contracts enough to catch real breakage?" | ✓ Yes — covers auth (most-used), the 3 core business entities, and users |
| B2: Type safety | Medium-Large | "Can you fix 10 modules without breaking things?" | ⚠ Risk — each module needs individual testing; added "existing tests pass" to DoD |
| B3: Data writes | Medium | "Is the UNION ALL refactor straightforward?" | ⚠ Medium risk — 6 entity types with different schemas; added performance test |
| B4: Observability | Medium | "Do you have Azure Monitor access to deploy dashboards?" | ⚠ Dependency — flagged as prerequisite; templates can be created regardless |
| B5: Schema safety | Small | "Is the DPIA really small effort?" | ⚠ Depends on legal review — added DPO dependency; template-based approach keeps it bounded |
| C1: Accessibility | Small-Medium | "Will axe-core generate too many violations to fix?" | ✓ Managed — start in warning mode, fix top 10, then switch to blocking |
| C2: Journey maps | Small | "Is this documentation fluff?" | ✓ No — directly enables C3 (IA audit) and C5 (measurement instrumentation) |
| C3: IA audit | Small | "Can you do meaningful IA analysis without analytics data?" | ✓ Yes — route analysis + persona cross-reference + user testing is sufficient |
| C4: Design system | Medium-Large | "Is Storybook 'medium-large' or 'large'?" | ⚠ Adjusted — initial setup is M; full 20-component documentation is L; split across sprints |
| C5: Measurement | Medium | "Why not just install PostHog?" | ✓ Start with native web-vitals + Lighthouse CI for zero external dependency; evaluate PostHog in Horizon C |

**Round 3 Adjustments**:
- A3: Added 3 behavioral test writes to task list to ensure 50% threshold is reachable
- B2: Added "existing tests must pass" as explicit DoD criterion
- B3: Performance test added as validation step
- B4: Azure Monitor access flagged as prerequisite
- C4: Noted as spanning 2 sprints (setup + full documentation)

---

## Summary Scorecard

| # | Focus Area | Category | Effort | Expected WCS Lift | Findings Addressed | CFs Protected |
|---|-----------|----------|--------|-------------------|--------------------|---------------|
| A1 | Auth Hardening | Low/High | S | D06 +1.4 | F-001, F-002 | CF1 |
| A2 | Tenant Isolation | Low/High | M | D06 +0.4, D07 +0.3 | F-003 | CF1, CF2 |
| A3 | Test Reliability | Low/High | M | D15 +1.6, D21 +0.5 | F-004, F-006 | CF2, CF5 |
| A4 | Governance Docs | Low/High | S | D23 +3.0, D29 +2.1, D22 +1.6 | F-007 | CF5 |
| A5 | Config Hygiene | Low/High | S | D31 +1.1, D12 +0.2 | C-002, C-003 | CF5 |
| B1 | API Contracts | Workflows | M | D15 +0.5, D10 +0.3 | F-005 | CF2, CF4 |
| B2 | Type Safety | Workflows | M-L | D21 +1.5, D09 +0.3 | F-008 | CF2, CF3 |
| B3 | Data Write Safety | Workflows | M | D24 +0.3, D04 +0.5, D25 +0.3 | — | CF3 |
| B4 | Observability | Workflows | M | D13 +1.3, D23 +1.0, D32 +0.5 | — | CF1-CF5 |
| B5 | Schema & Privacy | Workflows | S | D12 +0.3, D07 +0.5 | — | CF5 |
| C1 | Accessibility | UI/UX | S-M | D03 +2.5 | — | CF2 |
| C2 | Journey Clarity | UI/UX | S | D01 +1.0 | — | CF2 |
| C3 | IA Audit | UI/UX | S | D02 +1.0 | — | CF2 |
| C4 | Design System | UI/UX | M-L | D02 +1.0, D09 +0.2 | — | CF2 |
| C5 | FE Measurement | UI/UX | M | D28 +1.6, D04 +0.3 | — | CF2 |

**Projected WCS after all 15 complete**: ~7.8 average (up from 6.5)
**Dimensions moved above 8.0**: D06, D12, D13, D15, D21, D22, D23, D29 (8 additional dimensions)
**Remaining gap to 9.5**: Requires Horizon B (coverage 80%, chaos testing, load testing, full i18n, cost optimization) and Horizon C (design system maturity, product analytics, mutation testing).

---

## Execution Timeline

```
WEEK 1 ─────────────────────────────────────────
  A1: Auth Hardening (S)           ██████ DONE
  A4: Governance Docs (S)          ██████ DONE
  A5: Config Hygiene (S)           ██████ DONE
  C2: Journey Maps (S)             ██████ DONE

WEEK 2 ─────────────────────────────────────────
  A2: Tenant Isolation (M)         ████████████ DONE
  C1: Accessibility Automation (S) ██████ START → WEEK 3

WEEK 3 ─────────────────────────────────────────
  A3: Test Reliability (M)         ████████████ DONE
  C1: Accessibility (cont.)        ██████ DONE
  C3: IA Audit (S)                 ██████ DONE

WEEK 4 ─────────────────────────────────────────
  B1: API Contracts (M)            ████████████ DONE
  B5: Schema & Privacy (S)         ██████ DONE

WEEK 5 ─────────────────────────────────────────
  B2: Type Safety (M-L)            ████████████████ START → WEEK 6
  C5: FE Measurement (M)           ████████████ DONE

WEEK 6 ─────────────────────────────────────────
  B2: Type Safety (cont.)          ████████ DONE
  B3: Data Write Safety (M)        ████████████ DONE

WEEK 7-8 ───────────────────────────────────────
  B4: Observability (M)            ████████████ DONE
  C4: Design System (M-L)          ████████████████ DONE
```

**Total elapsed**: ~8 weeks with 2-3 engineers + 1 UX resource
**Quick wins (Week 1)**: A1, A4, A5, C2 — four S-effort items delivering immediate WCS lift across 8 dimensions
**Critical path**: A1 → A2 → A3 → B1 → B2 → B3 (security → testing → stability)
