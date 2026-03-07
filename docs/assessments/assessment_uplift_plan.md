# Quality Governance Platform — World-Class Uplift Plan (Round 2)

**Date:** 2026-03-07 (Post Week-1 Uplift)
**Prior:** assessment_current.md (same date)
**Target:** WCS 9.5+ across all 32 dimensions

---

## 6. Quick Wins Engine (Top 12 — Small Effort / High Value)

### QW-01: Fix rate limiter authenticated multiplier

| Field | Detail |
|-------|--------|
| **Linked CF** | CF1 |
| **Dimensions** | D06, D05 |
| **Why High Leverage** | Single-line fix restores 2x rate limits for authenticated users — protects business endpoints from abuse |
| **Exact Change** | `src/infrastructure/middleware/rate_limiter.py` L253: change `"user:"` to `"token:"` |
| **DoD** | Rate limiter correctly applies 2x multiplier for token-authenticated requests |
| **Validation** | Unit test: mock `client_id="token:abc"` → `is_authenticated=True`; mock `client_id="ip:1.2.3.4"` → `is_authenticated=False` |
| **Rollback** | Revert single line |
| **Expected WCS Lift** | D06: +0.2 (9.0→9.2) |
| **Risk** | {SEC, REL} |
| **ROI** | {Risk avoided} |
| **Out-of-Scope** | Does NOT change rate limit values themselves |

### QW-02: Mount SLO router in API

| Field | Detail |
|-------|--------|
| **Linked CF** | CF4 |
| **Dimensions** | D13, D28 |
| **Why High Leverage** | Activates existing SLO endpoints — zero new code, just wiring |
| **Exact Change** | `src/api/__init__.py`: add `from src.api.routes import slo` + `api_router.include_router(slo.router, prefix="/slo", tags=["SLO"])` |
| **DoD** | `GET /api/v1/slo/current` returns 200 (or 401 without auth) |
| **Validation** | Integration test: SLO endpoints return valid JSON; contract test for response schema |
| **Rollback** | Remove the include_router line |
| **Expected WCS Lift** | D13: +0.4 (7.2→7.6); D28: +0.4 (5.4→5.8) |
| **Risk** | {REL} |
| **ROI** | {Quality uplift} |
| **Out-of-Scope** | Does NOT implement new SLO metrics |

### QW-03: Renumber ADRs + create index

| Field | Detail |
|-------|--------|
| **Linked CF** | CF5 |
| **Dimensions** | D29, D22 |
| **Why High Leverage** | Resolves governance confusion from duplicate ADR numbering; prevents future collisions |
| **Exact Change** | Renumber `docs/adr/ADR-*.md` to sequential ADR-0001 through ADR-0009; create `docs/adr/README.md` with index table |
| **DoD** | No duplicate ADR numbers; index file lists all ADRs with title, date, status |
| **Validation** | CI script: `ls docs/adr/ADR-*.md | sed 's/.*ADR-//' | sort | uniq -d` returns empty |
| **Rollback** | Revert renames |
| **Expected WCS Lift** | D29: +0.3 (7.2→7.5) |
| **Risk** | {GOV} |
| **ROI** | {Quality uplift} |
| **Out-of-Scope** | Does NOT create new ADRs |

### QW-04: Swap OpenCensus → OpenTelemetry deps

| Field | Detail |
|-------|--------|
| **Linked CF** | CF4 |
| **Dimensions** | D13, D20, D28 |
| **Why High Leverage** | Activates distributed tracing that's already coded but never runs due to missing deps |
| **Exact Change** | `requirements.txt`: remove `opencensus*`; add `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy`, `azure-monitor-opentelemetry-exporter`; regenerate `requirements.lock` |
| **DoD** | `_HAS_OTEL = True` in startup logs; traces visible in Azure Monitor |
| **Validation** | Integration test: import opentelemetry succeeds; verify trace_id in structured logs |
| **Rollback** | Revert to opencensus deps |
| **Expected WCS Lift** | D13: +0.8 (7.2→8.0); D28: +0.6 (5.4→6.0) |
| **Risk** | {REL} |
| **ROI** | {Quality uplift, Risk avoided} |
| **Out-of-Scope** | Does NOT add custom spans beyond what instrumentation provides automatically |

### QW-05: Remove flake8 F401/F841 global ignores

| Field | Detail |
|-------|--------|
| **Linked CF** | CF2 |
| **Dimensions** | D21 |
| **Why High Leverage** | Exposes dead imports and unused variables — improves code health with no runtime risk |
| **Exact Change** | `.flake8`: remove `F401, F841` from `extend-ignore`; fix all violations (remove unused imports/vars) |
| **DoD** | `flake8` passes without F401/F841 ignores; no new `# noqa: F401` added (except `__init__.py` re-exports) |
| **Validation** | CI code-quality job passes |
| **Rollback** | Re-add ignores |
| **Expected WCS Lift** | D21: +0.5 (6.0→6.5) |
| **Risk** | {GOV} |
| **ROI** | {Quality uplift} |
| **Out-of-Scope** | Does NOT reduce max-complexity (separate item) |

### QW-06: Add tenant_id to portal-created records

| Field | Detail |
|-------|--------|
| **Linked CF** | CF3 |
| **Dimensions** | D24, D06 |
| **Why High Leverage** | Prevents orphaned records from public portal; ensures data integrity |
| **Exact Change** | `src/api/routes/employee_portal.py` L195-250: add configurable `DEFAULT_PORTAL_TENANT_ID` from settings; set `tenant_id=settings.default_portal_tenant_id` on Incident/Complaint creation |
| **DoD** | Portal-created records have valid `tenant_id`; visible in tenant-scoped queries |
| **Validation** | Integration test: `POST /api/v1/portal/reports/` → verify `tenant_id` is set on created record |
| **Rollback** | Remove tenant_id assignment |
| **Expected WCS Lift** | D24: +0.3 (9.0→9.3) |
| **Risk** | {DATA, SEC} |
| **ROI** | {Risk avoided} |
| **Out-of-Scope** | Does NOT add auth to portal endpoint |

### QW-07: Raise coverage threshold to 50%

| Field | Detail |
|-------|--------|
| **Linked CF** | CF2 |
| **Dimensions** | D15 |
| **Why High Leverage** | Progressive coverage floor prevents regression; forces new code to be tested |
| **Exact Change** | `pyproject.toml`: `fail_under = 50`; write tests for: `incident_service.py`, `audit_service.py`, `reference_number.py` to bridge gap |
| **DoD** | `pytest --cov=src --cov-fail-under=50` passes |
| **Validation** | CI unit-tests job passes at 50% |
| **Rollback** | Lower threshold temporarily |
| **Expected WCS Lift** | D15: +0.5 (6.3→6.8) |
| **Risk** | {REL} |
| **ROI** | {Quality uplift, Risk avoided} |
| **Out-of-Scope** | Does NOT target 80%+ (that's Horizon C) |

### QW-08: Create 3 Playwright E2E specs

| Field | Detail |
|-------|--------|
| **Linked CF** | CF2 |
| **Dimensions** | D15, D02 |
| **Why High Leverage** | Validates top user journeys end-to-end in a real browser; catches integration bugs CI can't |
| **Exact Change** | `frontend/tests/e2e/`: create `login.spec.ts`, `incident-crud.spec.ts`, `dashboard.spec.ts` |
| **DoD** | `npx playwright test` passes for 3 specs covering login → dashboard → create incident → verify in list |
| **Validation** | CI Playwright job passes; screenshots on failure stored as artifacts |
| **Rollback** | N/A (additive) |
| **Expected WCS Lift** | D15: +0.4 (6.3→6.7); D02: +0.3 (7.2→7.5) |
| **Risk** | {UX, REL} |
| **ROI** | {Quality uplift} |
| **Out-of-Scope** | Does NOT cover all 71 pages; 3 critical paths only |

### QW-09: Add optimistic locking to AuditRun

| Field | Detail |
|-------|--------|
| **Linked CF** | CF2, CF3 |
| **Dimensions** | D24, D11 |
| **Why High Leverage** | Prevents concurrent audit edits from silently overwriting each other; InvestigationRun already has it |
| **Exact Change** | `src/domain/models/audit.py`: add `version: Mapped[int] = mapped_column(Integer, default=1)` to AuditRun; add Alembic migration; update `src/api/routes/audits.py` to check version on PUT/PATCH |
| **DoD** | Concurrent PUT with stale version returns 409 Conflict |
| **Validation** | Integration test: two concurrent updates → one gets 409 |
| **Rollback** | Revert migration + model change |
| **Expected WCS Lift** | D24: +0.2 (9.0→9.2) |
| **Risk** | {DATA} |
| **ROI** | {Risk avoided} |
| **Out-of-Scope** | Does NOT add optimistic locking to all models (only AuditRun) |

### QW-10: Create environment parity doc

| Field | Detail |
|-------|--------|
| **Linked CF** | CF5 |
| **Dimensions** | D31 |
| **Why High Leverage** | Documents staging vs production differences; prevents config drift incidents |
| **Exact Change** | Create `docs/infrastructure/environment-parity.md` with table: env var, staging value, prod value, notes |
| **DoD** | Document covers compute, DB tier, Redis tier, feature flags, external integrations |
| **Validation** | CI script compares env var lists between staging and prod config |
| **Rollback** | N/A (documentation) |
| **Expected WCS Lift** | D31: +0.6 (6.3→6.9) |
| **Risk** | {REL} |
| **ROI** | {Risk avoided} |
| **Out-of-Scope** | Does NOT change infrastructure |

### QW-11: Write 5 accessibility test files

| Field | Detail |
|-------|--------|
| **Linked CF** | CF2 |
| **Dimensions** | D03 |
| **Why High Leverage** | jest-axe is installed but zero a11y tests exist; activates existing tooling |
| **Exact Change** | Create `frontend/src/pages/__tests__/Dashboard.a11y.test.tsx`, `Login.a11y.test.tsx`, `Incidents.a11y.test.tsx`, `Complaints.a11y.test.tsx`, `AuditExecution.a11y.test.tsx` |
| **DoD** | `npm run test:a11y` passes with 5 test files; axe-core reports zero critical violations |
| **Validation** | CI frontend-tests job includes a11y check |
| **Rollback** | N/A (additive) |
| **Expected WCS Lift** | D03: +1.0 (4.5→5.5) |
| **Risk** | {UX} |
| **ROI** | {Quality uplift, Risk avoided} |
| **Out-of-Scope** | Does NOT fix accessibility violations (only detects them) |

### QW-12: Flesh out thin runbooks

| Field | Detail |
|-------|--------|
| **Linked CF** | CF5 |
| **Dimensions** | D23 |
| **Why High Leverage** | Contacts/on-call now filled but some runbooks are template-level; adding decision trees makes them usable |
| **Exact Change** | Enhance 5 highest-impact runbooks: `incident-response.md`, `deployment.md`, `rollback.md`, `database-recovery.md`, `security-monitoring.md` — add decision trees, command snippets, verification steps |
| **DoD** | Each runbook has: trigger criteria, step-by-step commands, verification checks, escalation criteria |
| **Validation** | Tabletop exercise: team can follow runbook for simulated SEV-1 |
| **Rollback** | N/A (documentation) |
| **Expected WCS Lift** | D23: +0.6 (6.3→6.9) |
| **Risk** | {REL} |
| **ROI** | {Risk avoided, Time saved} |
| **Out-of-Scope** | Does NOT create new runbooks; only enhances existing ones |

---

## 7. Critical Bars Hardening Plan (P0 First)

### Gate 1: Security Hardening (D06 → 9.5+)

| Aspect | Current State | Gap | Implementation | Done Criteria |
|--------|--------------|-----|----------------|---------------|
| Auth coverage | All business endpoints guarded; 46+ test pairs | Rate limiter `startsWith` bug | Fix L253 in `rate_limiter.py` | Unit test passes; authenticated users get 2x limit |
| CSP | Strict CSP in SecurityHeadersMiddleware | `'unsafe-inline'` in style-src | Migrate to CSP nonces or hashes for styles | CSP header has no `'unsafe-inline'` |
| Portal tenant isolation | Public `submit_quick_report` creates records without `tenant_id` | Orphaned records | Add `DEFAULT_PORTAL_TENANT_ID` from config | Portal records have valid `tenant_id` |
| Dependency scanning | Bandit, pip-audit, Safety, Semgrep, npm audit | No DAST / no pentest | Schedule quarterly pentest; add OWASP ZAP to CI | Pentest report on file; ZAP baseline scan in CI |

### Gate 2: Data Integrity (D24 → 9.5+)

| Aspect | Current State | Gap | Implementation | Done Criteria |
|--------|--------------|-----|----------------|---------------|
| Idempotency | SHA-256 + Redis 24h | Covers POST/PUT/PATCH only | Sufficient for write operations | N/A (current is adequate) |
| Optimistic locking | InvestigationRun only | AuditRun, Risk, Incident missing | Add `version` column + migration + check on update | Concurrent update returns 409 |
| Ref number generation | MAX/COUNT hybrid | Not load-tested | Run k6 concurrent-write test against ref number endpoints | Zero duplicates under 50 concurrent writers |
| Portal records | No `tenant_id` | Orphaned data | Add default tenant config | All records have `tenant_id` |

### Gate 3: Release Safety (D18 maintained at 10.0)

| Aspect | Current State | Gap | Implementation | Done Criteria |
|--------|--------------|-----|----------------|---------------|
| Governance signoff | `release_signoff.json` SHA-validated | SHA mismatch requires manual `workflow_dispatch` | Automate SHA update in signoff step | Zero manual overrides needed |
| Canary/blue-green | None | Full cutover deploys | Implement Azure ACA revision splitting (10%/50%/100%) | Canary config in deploy workflow |
| Rollback verification | Rollback workflow exists | No automated rollback test | Add post-rollback health check in CI | Rollback E2E passes in staging |
| Config validation | Pydantic validates at startup | No pre-deploy config check | Add `python -c "from src.core.config import get_settings; get_settings()"` as deploy step | Config validated before container swap |

---

## 8. World-Class Roadmap (3 Horizons)

### Horizon A: Safety + Determinism + Testability (0–2 weeks)

| Epic | Dimensions | CF | Entry Criteria | Exit Criteria | Dependencies | Risks |
|------|-----------|-----|----------------|---------------|-------------|-------|
| **A1: Fix security bugs** (QW-01, QW-06, F-008, F-011) | D06, D24 | CF1, CF3 | Code access | Rate limiter fix deployed; portal records have tenant_id | None | Low — single-line fix + config addition |
| **A2: Wire dead code** (QW-02, QW-04, F-009, F-010) | D13, D20, D28 | CF4 | Code access | SLO endpoints reachable; OpenTelemetry active | Azure Monitor connection string | Medium — dep swap needs integration testing |
| **A3: Coverage to 50%** (QW-07) | D15 | CF2 | Existing test infra | `--cov-fail-under=50` passes in CI | None | Medium — may surface untestable code |
| **A4: Governance cleanup** (QW-03, F-012) | D29, D22 | CF5 | ADR files accessible | Sequential ADR numbering; index file | None | Low |

### Horizon B: Core Quality Uplift (2–6 weeks)

| Epic | Dimensions | CF | Entry Criteria | Exit Criteria | Dependencies | Risks |
|------|-----------|-----|----------------|---------------|-------------|-------|
| **B1: E2E test suite** (QW-08, QW-11) | D15, D02, D03 | CF2 | Horizon A complete | 5 Playwright specs + 5 a11y tests passing in CI | Playwright CI job configured | Medium — E2E tests can be flaky |
| **B2: Code quality tightening** (QW-05, F-005, F-007) | D21 | CF2 | Horizon A complete | flake8 F401/F841 fixed; mypy overrides reduced to 20; max-complexity=15 | None | Low-Medium |
| **B3: Operational maturity** (QW-10, QW-12) | D23, D31 | CF5 | Contacts/on-call defined (done) | 5 runbooks enhanced; env parity documented | Staging env access for verification | Low |
| **B4: Optimistic locking expansion** (QW-09) | D24, D11 | CF3 | Migration framework ready | AuditRun, Risk, Incident have version columns; 409 on stale updates | Alembic migration | Low-Medium |
| **B5: Performance baseline** | D04, D25 | CF2 | Staging env available | k6 load test results for top 5 endpoints; P95 < 500ms documented | k6 or Locust installed | Medium — may reveal bottlenecks |

### Horizon C: Automation, Resilience, and 5/5 Completion (6–12 weeks)

| Epic | Dimensions | CF | Entry Criteria | Exit Criteria | Dependencies | Risks |
|------|-----------|-----|----------------|---------------|-------------|-------|
| **C1: Coverage to 75%+** | D15, D16 | CF2 | Coverage at 50%+ | `--cov-fail-under=75` passes; mutation testing baseline | Horizon A3 complete | High — significant test writing effort |
| **C2: Frontend test coverage to 40%+** | D15, D02 | CF2 | Vitest configured | Frontend coverage ≥40%; 30+ component tests | None | Medium |
| **C3: Canary deployments** | D18, D05 | CF5 | ACA revision splitting supported | 10%→50%→100% canary with automated rollback | Azure ACA configuration | Medium |
| **C4: DAST integration** | D06 | CF1 | CI pipeline access | OWASP ZAP baseline scan in CI; zero high-severity findings | ZAP Docker image | Low |
| **C5: FinOps baseline** | D26 | CF5 | Azure cost data access | Monthly cost report; budget alerts; right-sizing recommendations | Azure Cost Management API | Low |
| **C6: Backend i18n** | D27 | CF2 | Frontend i18n stable | Backend error messages/emails i18n-ready; 2nd locale added | gettext or equivalent | Medium |
| **C7: Chaos engineering** | D05, D25 | CF2, CF4 | Monitoring active (Horizon A2) | Quarterly chaos test; circuit breaker validated under failure | Azure Chaos Studio or Litmus | Medium-High |
| **C8: Full observability** | D13, D28, D32 | CF4 | OpenTelemetry active | Custom spans on critical paths; SLO dashboard live; ops dashboard | Horizon A2 complete | Medium |

---

## 9. PR-Ready Backlog (Sorted by Priority Score desc, then Effort asc)

### [P1] (Effort S) (PS=9.6) Fix rate limiter authenticated multiplier bug
- CF(s): CF1
- Dimension(s): D06, D05
- Files/Modules: `src/infrastructure/middleware/rate_limiter.py` L253
- Change Summary: Change `client_id.startswith("user:")` to `client_id.startswith("token:")`
- Definition of Done: Authenticated users get 2x rate limit multiplier
- Tests/Validation: Unit test for `is_authenticated` with both `token:` and `ip:` prefixes
- Observability: Log rate limit hits with `is_authenticated` flag
- Rollback: Revert single line
- Risk of Change: Low
- Risk Reduction: {SEC, REL}
- ROI: {Risk avoided}
- Dependencies: None
- Out-of-Scope: Does NOT change limit values
- Owner Role: Backend Engineer

### [P1] (Effort S) (PS=9.6) Mount SLO router in API
- CF(s): CF4
- Dimension(s): D13, D28
- Files/Modules: `src/api/__init__.py`
- Change Summary: Add `from src.api.routes import slo` + `api_router.include_router(slo.router, prefix="/slo", tags=["SLO"])`
- Definition of Done: `GET /api/v1/slo/current` returns valid response
- Tests/Validation: Integration test for SLO endpoints; contract test for response schema
- Observability: SLO endpoint response time metric
- Rollback: Remove include_router line
- Risk of Change: Low
- Risk Reduction: {REL, GOV}
- ROI: {Quality uplift}
- Dependencies: None
- Out-of-Scope: Does NOT implement new SLO metrics
- Owner Role: Backend Engineer

### [P1] (Effort S) (PS=8.2) Add tenant_id to portal-created records
- CF(s): CF3
- Dimension(s): D24, D06
- Files/Modules: `src/api/routes/employee_portal.py` L195-250; `src/core/config.py`
- Change Summary: Add `default_portal_tenant_id` to Settings; set on Incident/Complaint creation
- Definition of Done: Portal records have valid tenant_id
- Tests/Validation: Integration test: POST portal report → record has tenant_id
- Observability: Alert on records with null tenant_id
- Rollback: Remove tenant_id assignment
- Risk of Change: Low
- Risk Reduction: {DATA, SEC}
- ROI: {Risk avoided}
- Dependencies: None
- Out-of-Scope: Does NOT add auth to portal
- Owner Role: Backend Engineer

### [P1] (Effort S) (PS=7.0) Remove flake8 F401/F841 global ignores
- CF(s): CF2
- Dimension(s): D21
- Files/Modules: `.flake8`; all files with unused imports/variables
- Change Summary: Remove F401, F841 from extend-ignore; fix violations
- Definition of Done: flake8 passes without F401/F841 ignores
- Tests/Validation: CI code-quality job passes
- Observability: Track flake8 violation count
- Rollback: Re-add ignores
- Risk of Change: Low
- Risk Reduction: {GOV}
- ROI: {Quality uplift}
- Dependencies: None
- Out-of-Scope: Does NOT reduce max-complexity
- Owner Role: Backend Engineer

### [P1] (Effort S) (PS=4.6) Renumber ADRs + create index
- CF(s): CF5
- Dimension(s): D29, D22
- Files/Modules: `docs/adr/ADR-*.md`; create `docs/adr/README.md`
- Change Summary: Renumber to ADR-0001 through ADR-0009; create index
- Definition of Done: No duplicate ADR numbers; index file complete
- Tests/Validation: CI script validates no duplicate numbers
- Observability: N/A
- Rollback: Revert renames
- Risk of Change: Low
- Risk Reduction: {GOV}
- ROI: {Quality uplift}
- Dependencies: None
- Out-of-Scope: Does NOT create new ADRs
- Owner Role: Tech Lead

### [P1] (Effort M) (PS=9.6) Raise test coverage to 50%
- CF(s): CF2
- Dimension(s): D15
- Files/Modules: `pyproject.toml`; `tests/unit/` (new test files for services)
- Change Summary: Write unit tests for `incident_service.py`, `audit_service.py`, `reference_number.py`; raise fail_under to 50
- Definition of Done: `pytest --cov-fail-under=50` passes
- Tests/Validation: CI unit-tests job at 50% threshold
- Observability: Coverage trend via quality_trend
- Rollback: Lower threshold temporarily
- Risk of Change: Medium
- Risk Reduction: {REL}
- ROI: {Quality uplift, Risk avoided}
- Dependencies: None
- Out-of-Scope: Does NOT target 80%+
- Owner Role: Backend Engineer

### [P1] (Effort M) (PS=8.2) Swap OpenCensus → OpenTelemetry dependencies
- CF(s): CF4
- Dimension(s): D13, D20, D28
- Files/Modules: `requirements.txt`; `requirements.lock`; `src/infrastructure/monitoring/azure_monitor.py`
- Change Summary: Remove opencensus; add opentelemetry packages; regenerate lockfile
- Definition of Done: `_HAS_OTEL = True` in startup logs; traces in Azure Monitor
- Tests/Validation: Integration test: opentelemetry imports succeed; verify trace_id in logs
- Observability: Distributed traces visible in Azure Monitor
- Rollback: Revert to opencensus deps
- Risk of Change: Medium
- Risk Reduction: {REL}
- ROI: {Quality uplift}
- Dependencies: Azure Monitor connection string
- Out-of-Scope: Does NOT add custom spans
- Owner Role: Platform Engineer

### [P1] (Effort M) (PS=7.0) Reduce mypy overrides from 30 to 20
- CF(s): CF2, CF3
- Dimension(s): D21, D09
- Files/Modules: `pyproject.toml`; 10 highest-priority override modules
- Change Summary: Fix type errors in `workflow_engine.py`, `risk_scoring.py`, `audit_service.py` first; remove their overrides
- Definition of Done: mypy overrides count ≤ 20
- Tests/Validation: mypy passes with fewer overrides; CI mypy job enforces count ceiling
- Observability: Track override count in quality trend
- Rollback: Re-add overrides for specific module
- Risk of Change: Low-Medium
- Risk Reduction: {REL, GOV}
- ROI: {Quality uplift}
- Dependencies: None
- Out-of-Scope: Does NOT target zero overrides
- Owner Role: Backend Engineer

### [P1] (Effort M) (PS=6.4) Enhance 5 operational runbooks
- CF(s): CF5
- Dimension(s): D23
- Files/Modules: `docs/runbooks/incident-response.md`, `deployment.md`, `rollback.md`, `database-recovery.md`, `security-monitoring.md`
- Change Summary: Add decision trees, command snippets, verification steps to each
- Definition of Done: Each runbook has trigger criteria, step-by-step commands, verification checks
- Tests/Validation: Tabletop exercise walkthrough
- Observability: N/A
- Rollback: N/A (documentation)
- Risk of Change: Low
- Risk Reduction: {REL}
- ROI: {Risk avoided, Time saved}
- Dependencies: None
- Out-of-Scope: Does NOT create new runbooks
- Owner Role: Platform Engineer

### [P1] (Effort M) (PS=6.4) Create environment parity documentation
- CF(s): CF5
- Dimension(s): D31
- Files/Modules: Create `docs/infrastructure/environment-parity.md`
- Change Summary: Table comparing staging vs production: compute, DB, Redis, feature flags, env vars
- Definition of Done: Document covers all infrastructure components; CI drift check added
- Tests/Validation: CI script compares env var lists
- Observability: N/A
- Rollback: N/A
- Risk of Change: Low
- Risk Reduction: {REL}
- ROI: {Risk avoided}
- Dependencies: Staging and production env access
- Out-of-Scope: Does NOT change infrastructure
- Owner Role: Platform Engineer

### [P1] (Effort M) (PS=5.0) Write 5 accessibility test files
- CF(s): CF2
- Dimension(s): D03
- Files/Modules: `frontend/src/pages/__tests__/Dashboard.a11y.test.tsx`, `Login.a11y.test.tsx`, `Incidents.a11y.test.tsx`, `Complaints.a11y.test.tsx`, `AuditExecution.a11y.test.tsx`
- Change Summary: Use jest-axe to validate no critical WCAG violations on 5 key pages
- Definition of Done: `npm run test:a11y` passes with 5 test files
- Tests/Validation: CI frontend-tests includes a11y check; zero critical violations
- Observability: A11y violation count in CI output
- Rollback: N/A (additive)
- Risk of Change: Low
- Risk Reduction: {UX}
- ROI: {Risk avoided, Quality uplift}
- Dependencies: jest-axe (already installed)
- Out-of-Scope: Does NOT fix a11y violations; only detects
- Owner Role: Frontend Engineer

### [P1] (Effort M) (PS=4.6) Add optimistic locking to AuditRun
- CF(s): CF2, CF3
- Dimension(s): D24, D11
- Files/Modules: `src/domain/models/audit.py`; Alembic migration; `src/api/routes/audits.py`
- Change Summary: Add `version` column; check version on PUT/PATCH; return 409 on stale
- Definition of Done: Concurrent PUT with stale version returns 409
- Tests/Validation: Integration test: concurrent update → 409 Conflict
- Observability: Metric for 409 Conflict responses
- Rollback: Revert migration + model change
- Risk of Change: Low-Medium
- Risk Reduction: {DATA}
- ROI: {Risk avoided}
- Dependencies: None
- Out-of-Scope: Does NOT add locking to all models
- Owner Role: Backend Engineer

### [P1] (Effort M) (PS=4.5) Create 3 Playwright E2E specs
- CF(s): CF2
- Dimension(s): D15, D02
- Files/Modules: `frontend/tests/e2e/login.spec.ts`, `incident-crud.spec.ts`, `dashboard.spec.ts`
- Change Summary: E2E specs for login → dashboard → create incident → verify in list
- Definition of Done: `npx playwright test` passes; CI job configured
- Tests/Validation: Screenshots on failure stored as artifacts
- Observability: E2E pass rate in CI dashboard
- Rollback: N/A (additive)
- Risk of Change: Low
- Risk Reduction: {UX, REL}
- ROI: {Quality uplift}
- Dependencies: Playwright CI job setup
- Out-of-Scope: Does NOT cover all 71 pages
- Owner Role: Frontend Engineer

### [P1] (Effort L) (PS=8.2) Performance baseline (k6 load tests)
- CF(s): CF2
- Dimension(s): D04, D25
- Files/Modules: Create `tests/load/`; k6 scripts for top 5 endpoints
- Change Summary: k6 scripts for incident CRUD, audit list, risk matrix, dashboard, auth; run against staging
- Definition of Done: Load test results documented; P95 < 500ms; zero errors under 100 concurrent
- Tests/Validation: Results in `docs/evidence/load-test-results/`
- Observability: Performance regression alerts
- Rollback: N/A (additive)
- Risk of Change: Low
- Risk Reduction: {PERF}
- ROI: {Quality uplift, Risk avoided}
- Dependencies: k6 installed; staging environment
- Out-of-Scope: Does NOT optimize; only measures
- Owner Role: Platform Engineer

### [P1] (Effort L) (PS=7.0) Reduce flake8 max-complexity to 15
- CF(s): CF2
- Dimension(s): D21
- Files/Modules: `.flake8`; all functions with complexity > 15
- Change Summary: Lower max-complexity from 20 to 15; refactor complex functions
- Definition of Done: flake8 passes with max-complexity=15
- Tests/Validation: CI code-quality job passes
- Observability: Track complexity violations
- Rollback: Raise back to 20
- Risk of Change: Medium (requires refactoring)
- Risk Reduction: {GOV}
- ROI: {Quality uplift}
- Dependencies: F401/F841 fix (QW-05) first
- Out-of-Scope: Does NOT target complexity=10
- Owner Role: Backend Engineer

### [P2] (Effort S) (PS=4.6) Add CSP report-uri
- CF(s): CF1
- Dimension(s): D06
- Files/Modules: `src/main.py` SecurityHeadersMiddleware
- Change Summary: Add `report-uri` directive pointing to `/api/v1/telemetry/csp-reports` endpoint
- Definition of Done: CSP violations reported to backend endpoint
- Tests/Validation: Test: inject script → CSP report received
- Observability: CSP violation count metric
- Rollback: Remove report-uri directive
- Risk of Change: Low
- Risk Reduction: {SEC}
- ROI: {Risk avoided}
- Dependencies: None
- Out-of-Scope: Does NOT remove unsafe-inline yet
- Owner Role: Backend Engineer

### [P2] (Effort S) (PS=4.6) Automate release_signoff.json SHA update
- CF(s): CF5
- Dimension(s): D18
- Files/Modules: `.github/workflows/deploy-production.yml`; `release_signoff.json`
- Change Summary: Add workflow step to auto-update SHA in signoff before governance check
- Definition of Done: Production deploy succeeds without manual SHA override
- Tests/Validation: Deploy workflow passes governance gate automatically
- Observability: Deploy success rate metric
- Rollback: Revert workflow change
- Risk of Change: Low
- Risk Reduction: {REL}
- ROI: {Time saved}
- Dependencies: None
- Out-of-Scope: Does NOT change governance process
- Owner Role: DevOps Engineer

### [P2] (Effort S) (PS=4.1) Add frontend vitest coverage floor to 20%
- CF(s): CF2
- Dimension(s): D15
- Files/Modules: `frontend/vitest.config.ts`; `frontend/src/**/__tests__/`
- Change Summary: Raise vitest coverage threshold from 3% to 20%; write tests for critical components
- Definition of Done: `npm run test:coverage` passes at 20%
- Tests/Validation: CI frontend-tests job enforces
- Observability: Frontend coverage trend
- Rollback: Lower threshold
- Risk of Change: Medium
- Risk Reduction: {REL}
- ROI: {Quality uplift}
- Dependencies: None
- Out-of-Scope: Does NOT target 80%+
- Owner Role: Frontend Engineer

### [P2] (Effort S) (PS=3.0) Document API versioning strategy in ADR
- CF(s): CF4
- Dimension(s): D10, D29
- Files/Modules: Create `docs/adr/ADR-0010-api-versioning-strategy.md`
- Change Summary: Document URL-prefix versioning decision, deprecation policy, breaking change process
- Definition of Done: ADR approved and indexed
- Tests/Validation: ADR index updated
- Observability: N/A
- Rollback: N/A
- Risk of Change: Low
- Risk Reduction: {GOV}
- ROI: {Quality uplift}
- Dependencies: ADR renumbering (QW-03)
- Out-of-Scope: Does NOT implement v2 API
- Owner Role: Tech Lead

### [P2] (Effort M) (PS=6.5) Create FinOps baseline report
- CF(s): CF5
- Dimension(s): D26
- Files/Modules: Create `docs/infrastructure/finops-report.md`; enhance `cost_alerts.py`
- Change Summary: Document Azure spend by service; set budget alerts; identify right-sizing opportunities
- Definition of Done: Monthly cost report template; budget alerts configured in Azure
- Tests/Validation: Budget alert fires on test threshold
- Observability: Cost trend dashboard
- Rollback: N/A
- Risk of Change: Low
- Risk Reduction: {COST}
- ROI: {Cost reduction}
- Dependencies: Azure Cost Management access
- Out-of-Scope: Does NOT implement cost optimization
- Owner Role: Platform Engineer

### [P2] (Effort M) (PS=6.4) Add optimistic locking to Risk and Incident
- CF(s): CF2, CF3
- Dimension(s): D24, D11
- Files/Modules: `src/domain/models/risk.py`, `src/domain/models/incident.py`; Alembic migrations
- Change Summary: Add `version` column to Risk and Incident; check on PUT/PATCH
- Definition of Done: Concurrent updates return 409 Conflict
- Tests/Validation: Integration test: concurrent update → 409
- Observability: 409 Conflict metric
- Rollback: Revert migrations
- Risk of Change: Medium
- Risk Reduction: {DATA}
- ROI: {Risk avoided}
- Dependencies: QW-09 (AuditRun first, to validate pattern)
- Out-of-Scope: Does NOT add to all models
- Owner Role: Backend Engineer

### [P2] (Effort M) (PS=5.0) Add backend i18n infrastructure
- CF(s): CF2
- Dimension(s): D27
- Files/Modules: `src/core/i18n.py`; error message templates; email templates
- Change Summary: Add gettext or i18n library; externalize error messages
- Definition of Done: Error messages loaded from locale files; English locale complete
- Tests/Validation: Unit test: switch locale → different error message
- Observability: N/A
- Rollback: Revert to hardcoded messages
- Risk of Change: Medium
- Risk Reduction: {UX}
- ROI: {Quality uplift}
- Dependencies: None
- Out-of-Scope: Does NOT add non-English locales
- Owner Role: Backend Engineer

### [P2] (Effort M) (PS=4.6) Add privacy impact assessment automation
- CF(s): CF3
- Dimension(s): D07
- Files/Modules: `src/domain/models/` (data classification annotations); `scripts/pia-checker.py`
- Change Summary: Add data classification tags to model fields; script validates PII handling
- Definition of Done: All model fields with PII classified; CI check validates
- Tests/Validation: CI PIA checker passes
- Observability: PII field count metric
- Rollback: Remove annotations (no runtime impact)
- Risk of Change: Low
- Risk Reduction: {SEC, GOV}
- ROI: {Risk avoided}
- Dependencies: None
- Out-of-Scope: Does NOT implement encryption on additional fields
- Owner Role: Backend Engineer

### [P2] (Effort M) (PS=4.6) Create SLO alerting and error budget tracking
- CF(s): CF4
- Dimension(s): D13, D32
- Files/Modules: `src/api/routes/slo.py`; Azure Monitor alert rules
- Change Summary: Add error budget consumption calculation; alert when 50% budget consumed
- Definition of Done: Error budget alerts configured; SLO dashboard shows burn rate
- Tests/Validation: Simulate latency spike → alert fires
- Observability: Error budget burn rate metric
- Rollback: Remove alert rules
- Risk of Change: Low
- Risk Reduction: {REL}
- ROI: {Risk avoided}
- Dependencies: SLO router mounted (QW-02)
- Out-of-Scope: Does NOT define new SLOs
- Owner Role: Platform Engineer

### [P2] (Effort M) (PS=4.6) Expand user journey documentation
- CF(s): CF2
- Dimension(s): D01, D22
- Files/Modules: `docs/user-journeys/personas-and-journeys.md`
- Change Summary: Add journey maps for audit execution, risk assessment, and portal reporting (3 more)
- Definition of Done: 8 total journey maps; each with touchpoints, pain points, metrics
- Tests/Validation: Journey maps reviewed with stakeholders
- Observability: N/A
- Rollback: N/A
- Risk of Change: Low
- Risk Reduction: {UX}
- ROI: {Quality uplift}
- Dependencies: None
- Out-of-Scope: Does NOT redesign flows
- Owner Role: Product Owner

### [P2] (Effort M) (PS=4.1) Add capacity planning documentation
- CF(s): CF5
- Dimension(s): D25
- Files/Modules: Create `docs/infrastructure/capacity-plan.md`
- Change Summary: Document current resource usage, growth projections, scaling triggers
- Definition of Done: Capacity plan with scaling triggers for DB, Redis, compute
- Tests/Validation: Load test results inform capacity plan
- Observability: Resource utilization metrics
- Rollback: N/A
- Risk of Change: Low
- Risk Reduction: {PERF, COST}
- ROI: {Risk avoided}
- Dependencies: Performance baseline (load tests)
- Out-of-Scope: Does NOT implement autoscaling
- Owner Role: Platform Engineer

### [P2] (Effort M) (PS=4.1) Create analytics/telemetry dashboard
- CF(s): CF4
- Dimension(s): D28
- Files/Modules: `docs/observability/dashboards/`; Azure Monitor dashboard JSON
- Change Summary: Create dashboard showing web-vitals, SLO metrics, business metrics
- Definition of Done: Dashboard deployed in Azure Monitor; accessible to team
- Tests/Validation: Dashboard loads; shows last 24h of data
- Observability: Dashboard itself is the observability signal
- Rollback: Delete dashboard
- Risk of Change: Low
- Risk Reduction: {REL}
- ROI: {Quality uplift}
- Dependencies: OpenTelemetry active; SLO router mounted
- Out-of-Scope: Does NOT implement custom metrics
- Owner Role: Platform Engineer

### [P2] (Effort L) (PS=7.0) Full frontend component test coverage
- CF(s): CF2
- Dimension(s): D15, D02
- Files/Modules: `frontend/src/**/__tests__/`
- Change Summary: Write vitest tests for all major pages and components (Dashboard, Incidents, Audits, Risks, etc.)
- Definition of Done: Frontend coverage ≥40%; 30+ test files
- Tests/Validation: CI vitest job passes at 40%
- Observability: Frontend coverage trend
- Rollback: N/A
- Risk of Change: Low
- Risk Reduction: {REL}
- ROI: {Quality uplift}
- Dependencies: None
- Out-of-Scope: Does NOT include E2E tests
- Owner Role: Frontend Engineer

### [P2] (Effort L) (PS=4.6) Implement compliance evidence automation
- CF(s): CF2
- Dimension(s): D08
- Files/Modules: `src/api/routes/compliance.py`; `src/domain/services/iso_compliance_service.py`
- Change Summary: Auto-generate compliance evidence packs from audit trails + document links
- Definition of Done: `/api/v1/compliance/evidence-pack` returns ISO-ready evidence bundle
- Tests/Validation: Integration test: generate pack → validate structure matches ISO requirements
- Observability: Pack generation latency metric
- Rollback: Revert endpoint
- Risk of Change: Medium
- Risk Reduction: {GOV}
- ROI: {Time saved}
- Dependencies: Document management module
- Out-of-Scope: Does NOT replace external audit
- Owner Role: Backend Engineer

### [P2] (Effort L) (PS=4.5) Implement canary deployments
- CF(s): CF5
- Dimension(s): D18, D05
- Files/Modules: `.github/workflows/deploy-production.yml`; Azure ACA config
- Change Summary: Add revision splitting: 10% → 50% → 100% with health gate between stages
- Definition of Done: Production deploys go through 3-stage canary
- Tests/Validation: Staging canary dry-run passes
- Observability: Canary error rate vs baseline metric
- Rollback: Shift 100% traffic to previous revision
- Risk of Change: Medium
- Risk Reduction: {REL}
- ROI: {Risk avoided}
- Dependencies: Azure ACA supports revision splitting
- Out-of-Scope: Does NOT implement feature flags for canary
- Owner Role: DevOps Engineer

### [P2] (Effort L) (PS=4.1) Add OWASP ZAP DAST to CI
- CF(s): CF1
- Dimension(s): D06
- Files/Modules: `.github/workflows/ci.yml`; `tests/security/zap-config.yaml`
- Change Summary: Add ZAP baseline scan job to CI; scan staging after deploy
- Definition of Done: ZAP scan completes; zero high-severity findings
- Tests/Validation: ZAP report stored as CI artifact
- Observability: DAST finding count trend
- Rollback: Remove CI job
- Risk of Change: Low
- Risk Reduction: {SEC}
- ROI: {Risk avoided}
- Dependencies: Staging deploy completes first
- Out-of-Scope: Does NOT replace manual pentest
- Owner Role: Security Engineer

### [P2] (Effort L) (PS=4.1) Implement autoscaling rules
- CF(s): CF5
- Dimension(s): D25, D26
- Files/Modules: Azure ACA scaling config; `docs/infrastructure/capacity-plan.md`
- Change Summary: Configure CPU/memory-based autoscaling for ACA; add scaling alerts
- Definition of Done: Autoscaling triggers at 70% CPU; scales 1→4 replicas
- Tests/Validation: Load test triggers scaling; verify new instances serve traffic
- Observability: Instance count metric; scaling event alerts
- Rollback: Set fixed replica count
- Risk of Change: Medium
- Risk Reduction: {PERF, COST}
- ROI: {Cost reduction, Risk avoided}
- Dependencies: Capacity plan; load test results
- Out-of-Scope: Does NOT implement database autoscaling
- Owner Role: Platform Engineer

### [P2] (Effort L) (PS=3.0) Implement design system component library
- CF(s): CF2
- Dimension(s): D02, D03
- Files/Modules: `frontend/src/components/ui/`; `design-tokens.css`
- Change Summary: Fill 11 identified component gaps (DataTable, FormField, Breadcrumb, Tabs, etc.)
- Definition of Done: All 23 design system components documented; Storybook or equivalent
- Tests/Validation: Component tests for all new components; a11y tests
- Observability: N/A
- Rollback: Revert component additions
- Risk of Change: Low
- Risk Reduction: {UX}
- ROI: {Quality uplift, Time saved}
- Dependencies: None
- Out-of-Scope: Does NOT redesign existing components
- Owner Role: Frontend Engineer

### [P2] (Effort L) (PS=2.3) Add second i18n locale
- CF(s): CF2
- Dimension(s): D27
- Files/Modules: `frontend/src/i18n/locales/fr.json` (or similar); `scripts/i18n-check.mjs`
- Change Summary: Translate en.json to second locale; update CI i18n check for multiple locales
- Definition of Done: Language switcher works; all 2,118 keys translated
- Tests/Validation: `i18n-check.mjs` validates both locales
- Observability: Missing translation count
- Rollback: Remove locale file
- Risk of Change: Low
- Risk Reduction: {UX}
- ROI: {Revenue protection}
- Dependencies: Backend i18n (for error messages)
- Out-of-Scope: Does NOT add RTL support
- Owner Role: Frontend Engineer

---

## 10. Acceptance-Test Matrix (World-Class Proof)

| CF | E2E Tests | Integration Tests | Unit Tests | Chaos/Failure Tests | Observability Checks | Release Checks |
|----|-----------|-------------------|------------|---------------------|---------------------|----------------|
| **CF1: Auth** | Login flow; token refresh; password reset; Azure AD exchange | Auth endpoint returns 401 without token; 403 without permission; JWT expiry handling | `test_auth_enforcement.py` (46+ pairs); token creation/validation; password hashing | Redis unavailable → fallback auth; Azure AD outage → local JWT | Auth success rate SLO (99.5%); failed login alerts; rate limit hit count | Auth endpoints respond correctly post-deploy |
| **CF2: Business Workflows** | Incident CRUD lifecycle; Audit execution; Risk assessment flow | CRUD for incidents, complaints, RTAs, audits, risks, policies; status transitions; pagination | Service layer unit tests; domain model validation; reference number generation | DB connection loss → graceful degradation; circuit breaker trips | P95 latency < 500ms; error rate < 1%; business metric dashboards | Smoke tests pass; key endpoints return 200 |
| **CF3: Data Writes** | Portal report submission; bulk operations | Idempotency (duplicate POST → same result); optimistic locking (409 on stale); tenant-scoped writes | Reference number collision test; FK constraint validation; audit trail hash verification | Concurrent writes → no duplicates; Redis unavailable → idempotency degradation | DLQ depth < 10; duplicate record alerts; data write durability SLO | DB migration succeeds; no orphaned records |
| **CF4: External Integrations** | Azure AD login; file upload to blob | Azure Monitor metrics received; telemetry batch processing; SLO endpoint response | Azure auth JWKS validation; blob URL generation | Azure AD outage → local auth fallback; Blob storage timeout → retry | Distributed trace coverage; integration error rate; SLO dashboard | External service health checks pass |
| **CF5: Release/Deploy** | N/A (infrastructure) | Config validation; migration idempotency | Governance signoff validation; lockfile freshness; SBOM generation | Rollback procedure; failed migration → automatic rollback | Deploy success rate; rollback count; time-to-recovery | SHA determinism (3x match); health checks pass; security header validation |

---

## 11. World-Class Checklist (9.5+ Criteria per Dimension)

### D01: Product Clarity & User Journeys (Current 7.2 → Target 9.5)
- All user journeys documented with measurable success criteria and tracked in analytics
- Feature usage metrics tied to OKRs; quarterly user research cadence documented

### D02: UX Quality & IA (Current 7.2 → Target 9.5)
- Complete design system (23+ components) with Storybook; zero component gaps
- Lighthouse UX score ≥90; user satisfaction (CSAT/NPS) tracked quarterly

### D03: Accessibility (Current 4.5 → Target 9.5)
- WCAG 2.1 AA compliance verified by automated tests (axe-core) on all pages
- Quarterly manual accessibility audit; zero critical/serious axe violations in CI

### D04: Performance (Current 5.4 → Target 9.5)
- Load test results documented: P95 < 300ms, 99th < 1s under 200+ concurrent users
- Performance budgets enforced in CI; APM dashboard with alerting; Core Web Vitals all "Good"

### D05: Reliability & Resilience (Current 8.0 → Target 9.5)
- Quarterly chaos testing; circuit breakers validated under failure; MTTR < 30min documented
- 99.9% availability SLO met for 3 consecutive months with evidence

### D06: Security Engineering (Current 9.0 → Target 9.5)
- Zero unauthenticated business endpoints; DAST in CI; annual pentest on file
- Rate limiter working correctly for all user types; CSP without unsafe-inline

### D07: Privacy & Data Protection (Current 6.3 → Target 9.5)
- All PII fields classified and encrypted at rest; DPIA for every module with PII
- Data retention policies enforced automatically; GDPR deletion workflow tested

### D08: Compliance Readiness (Current 7.2 → Target 9.5)
- Automated evidence pack generation for ISO audits; external audit findings at zero open
- Compliance status dashboard with real-time gap tracking

### D09: Architecture Modularity (Current 8.0 → Target 9.5)
- Zero mypy overrides; clean dependency graph (no circular); architecture fitness functions in CI
- Module boundaries validated by import linter; ADR for every significant decision

### D10: API Design Quality (Current 8.0 → Target 9.5)
- API versioning strategy documented in ADR; backward compatibility tests in CI
- OpenAPI spec reviewed quarterly; all endpoints have request/response examples

### D11: Data Model Quality (Current 8.0 → Target 9.5)
- Optimistic locking on all write-heavy entities; all FKs indexed
- ERD auto-generated from models and reviewed quarterly; naming conventions documented

### D12: Schema Versioning & Migrations (Current 8.0 → Target 9.5)
- Down-migration tested for every up-migration; migration CI checks for data safety
- Schema change process documented in ADR; zero migration conflicts per quarter

### D13: Observability (Current 7.2 → Target 9.5)
- Distributed tracing active (OpenTelemetry); SLO dashboard live; error budget tracking
- Custom spans on critical paths; log aggregation with PII redaction verified

### D14: Error Handling & User-Safe Failures (Current 8.0 → Target 9.5)
- All error paths return structured envelope; user-facing messages i18n-ready
- Error rate by type tracked; no unhandled exceptions in production for 30 days

### D15: Testing Strategy (Current 6.3 → Target 9.5)
- Backend coverage ≥75%; frontend coverage ≥40%; E2E covering top 10 journeys
- Mutation testing baseline; test pyramid balanced; zero skip decorators on critical paths

### D16: Test Data & Fixtures (Current 6.3 → Target 9.5)
- Factory coverage for all 27 domain models; test data builder pattern documented
- Isolated test databases per test suite; no shared mutable state between tests

### D17: CI Quality Gates (Current 10.0 — MAINTAINED)
- All existing gates remain; add DAST, mutation testing, and architecture fitness functions

### D18: CD/Release Pipeline (Current 10.0 — MAINTAINED)
- Add canary deployments; automated release_signoff SHA; rollback E2E

### D19: Configuration Management (Current 8.0 → Target 9.5)
- Config drift detection CI check; feature flag audit log; secret rotation documented
- All environments validated by Pydantic at deploy time; zero config-related incidents

### D20: Dependency Management (Current 8.0 → Target 9.5)
- OpenCensus/OpenTelemetry resolved; zero known vulnerabilities in production
- License compliance check in CI; dependency freshness score tracked

### D21: Code Quality & Maintainability (Current 6.0 → Target 9.5)
- Zero mypy overrides; flake8 max-complexity ≤ 12; zero F401/F841; Semgrep custom rules
- Code review checklist enforced; technical debt tracked with ceiling

### D22: Documentation Quality (Current 7.2 → Target 9.5)
- All ADRs indexed and sequential; API examples in OpenAPI spec; architecture diagrams current
- Documentation freshness check; no stale docs older than 90 days

### D23: Operational Runbooks (Current 6.3 → Target 9.5)
- All 25 runbooks have decision trees, commands, verification; tested via tabletop exercise
- Runbook effectiveness metrics; quarterly review cycle

### D24: Data Integrity & Consistency (Current 9.0 → Target 9.5)
- Optimistic locking on all write-heavy entities; portal records have tenant_id
- Concurrency test suite; zero data integrity incidents in production for 90 days

### D25: Scalability & Capacity (Current 5.4 → Target 9.5)
- Load test results at 200+ concurrent users; autoscaling configured and tested
- Capacity plan with 12-month projections; scaling triggers documented

### D26: Cost Efficiency (Current 3.0 → Target 9.5)
- Monthly FinOps report; Azure budget alerts active; right-sizing implemented
- Cost per transaction tracked; quarterly optimization review

### D27: I18n/L10n (Current 4.5 → Target 9.5)
- Backend i18n infrastructure; 2+ locales complete; i18n coverage in CI for all locales
- RTL support if needed; date/number formatting locale-aware

### D28: Analytics/Telemetry (Current 5.4 → Target 9.5)
- SLO dashboard live; web-vitals tracked with alerting; business metrics dashboard
- Feature adoption metrics; experiment framework validated

### D29: Governance & Decision Records (Current 7.2 → Target 9.5)
- Sequential ADRs with index; zero duplicate numbers; ADR freshness review
- Governance dashboard; change advisory board (CAB) minutes linked

### D30: Build Determinism (Current 10.0 — MAINTAINED)
- All existing determinism gates remain

### D31: Environment Parity (Current 6.3 → Target 9.5)
- Parity document maintained and validated in CI; drift detection automated
- Feature flag parity check; identical infra-as-code for staging/prod

### D32: Supportability & Operability (Current 7.2 → Target 9.5)
- Ops dashboard live; on-call rotation automated (PagerDuty/Opsgenie); runbook-to-alert links
- MTTR < 30min for SEV-1; quarterly ops review with improvement tracking

---

## Additional Enhancements

### A) Contradictions Resolver

See Round 1, Section "Contradictions Resolver" for C-001 through C-003.

### B) Risk & ROI Tags

All backlog items include Risk Reduction and ROI tags. Summary:

| Tag | Count |
|-----|-------|
| {SEC} | 8 |
| {REL} | 14 |
| {DATA} | 5 |
| {GOV} | 7 |
| {UX} | 6 |
| {PERF} | 4 |
| {COST} | 3 |

### C) No-Scope-Creep Guardrail

Every backlog item has an explicit "Out-of-Scope" line. Key boundaries:
- Coverage uplift: 50% → 65% → 75% (not 100%)
- E2E: 3 specs → 5 → 10 (not all 71 pages)
- Mypy: 30 → 20 → 10 → 0 (phased, not all-at-once)
- i18n: infrastructure first, then 1 additional locale (not all locales)
- Performance: measure first, optimize second
- Canary: revision splitting only (not full blue-green)
