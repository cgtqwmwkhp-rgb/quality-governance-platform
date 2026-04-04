# WCS 9.5 Gap Closure Blueprint — v5

**Generated:** 2026-04-03
**Baseline commit:** current HEAD on `fix/release-signoff-tenant`
**Target:** All 32 dimensions at WCS >= 9.5

---

## Methodology

Two rounds of analysis identified **194 discrete gaps** across 32 dimensions.
This blueprint consolidates them into **12 workstreams** ordered by:
1. CI unblockers (gates that will fail if not fixed first)
2. Cross-cutting fixes (single change, multiple dimensions)
3. Depth-first dimension uplift (largest gap first)

### Scoring Math Reminder

WCS 9.5 requires: Maturity 5 (world-class automated auditable) + CM >= 0.95 (direct + comprehensive evidence).

---

## Workstream 1: CI Unblockers (MUST DO FIRST)

**Dimensions:** D08, D17, D22
**Risk:** These will FAIL the pipeline if not fixed before any other PR merges.

| # | Action | File | Detail |
|---|--------|------|--------|
| 1.1 | Replace `_[YYYY-MM-DD]_` with `2026-04-03` | `docs/compliance/compliance-matrix-iso.md` L101 | Blocks `compliance-freshness` CI gate |
| 1.2 | Replace `_[YYYY-MM-DD]_` with `2026-04-03` | `docs/security/security-policy.md` L60 | Blocks `compliance-freshness` CI gate |
| 1.3 | Replace `_[YYYY-MM-DD]_` with `2026-04-03` | `docs/ops/runtime-config-inventory.md` L135 | Blocks `compliance-freshness` CI gate |
| 1.4 | Replace `_[YYYY-MM-DD]_` with `2026-04-03` | `docs/privacy/data-retention-policy.md` L97 | Future compliance-freshness expansion |
| 1.5 | Replace `_[YYYY-MM-DD]_` with `2026-04-03` | `docs/privacy/dpia-template.md` L114 | Future compliance-freshness expansion |

**Verification:** `grep -r '_\[YYYY-MM-DD\]_' docs/` returns 0 matches.

---

## Workstream 2: CI/CD Hardening

**Dimensions:** D06, D12, D15, D17, D21, D30

| # | Action | File | Detail | Dimensions |
|---|--------|------|--------|------------|
| 2.1 | Add `dast-zap-baseline` job | `.github/workflows/ci.yml` | OWASP ZAP baseline scan; add to `all-checks` needs | D06, D17 |
| 2.2 | Add `alembic-check` job | `.github/workflows/ci.yml` | `alembic check` to detect schema drift; add to `all-checks` | D12, D17 |
| 2.3 | Add `radon-complexity` job | `.github/workflows/ci.yml` | `radon cc src/ -a -nc` with threshold CC >= B; add to `all-checks` | D21, D17 |
| 2.4 | Remove `\|\| true` from mutation-testing | `.github/workflows/ci.yml` | Lines 1469, 1473, 1474; let mutmut failures report (keep schedule-only) | D15, D17 |
| 2.5 | Promote TTI from warn to error | `lighthouserc.json` | `interactive` threshold: change to error level | D04, D17 |
| 2.6 | Expand Lighthouse URLs | `lighthouserc.json` | Add `/incidents`, `/audits`, `/risks`, `/complaints`, `/actions` | D04 |
| 2.7 | Add SLSA provenance attestation | `.github/workflows/deploy-production.yml` | Use `slsa-framework/slsa-github-generator` for signed provenance | D30 |
| 2.8 | Upload SBOM to GitHub Releases | `.github/workflows/ci.yml` | After `cyclonedx-py`, use `gh release upload` to attach to latest release | D20 |
| 2.9 | Add `npm audit --audit-level=high` blocking | `.github/workflows/ci.yml` | Already exists in frontend-tests; verify it's blocking (no `\|\| true`) | D06 |
| 2.10 | Make mutation testing enforce kill-rate | `.github/workflows/ci.yml` | Parse mutmut results for kill rate; fail if < 60% | D15, D17 |

---

## Workstream 3: Data Model Constraints

**Dimensions:** D11, D24, D08

| # | Action | File | Constraints to Add |
|---|--------|------|--------------------|
| 3.1 | Add CheckConstraints to Risk | `src/domain/models/risk.py` | `likelihood BETWEEN 1 AND 5`, `impact BETWEEN 1 AND 5`, `risk_score >= 0` |
| 3.2 | Add CheckConstraints to EnterpriseRisk (7 models) | `src/domain/models/risk_register.py` | `inherent_likelihood BETWEEN 1 AND 5`, `inherent_impact BETWEEN 1 AND 5`, `residual_*` ranges, `effectiveness_score BETWEEN 1 AND 5` |
| 3.3 | Add CheckConstraints to CAPAAction | `src/domain/models/capa.py` | `priority IN ('low','medium','high','critical')`, `capa_type IN ('corrective','preventive')` |
| 3.4 | Add CheckConstraints to RTA | `src/domain/models/rta.py` | `severity IN ('minor','damage_only','injury','fatal')` |
| 3.5 | Add CheckConstraints to Workflow | `src/domain/models/workflow.py` | `priority IN ('low','medium','high','critical')`, `version >= 1` |
| 3.6 | Add CheckConstraints to KRI | `src/domain/models/kri.py` | `threshold_value >= 0`, `frequency IN (...)` |
| 3.7 | Add CheckConstraints to DocumentControl | `src/domain/models/document_control.py` | `version >= 1`, `status IN (...)` |
| 3.8 | Add CheckConstraints to ISO27001 | `src/domain/models/iso27001.py` | `confidentiality_impact BETWEEN 1 AND 3`, `likelihood BETWEEN 1 AND 5`, `security_score BETWEEN 0 AND 100` |
| 3.9 | Add CheckConstraints to Investigation | `src/domain/models/investigation.py` | `status IN (...)` |
| 3.10 | Add CheckConstraints to DigitalSignature | `src/domain/models/digital_signature.py` | `status IN ('pending','signed','rejected','expired')` |
| 3.11 | Create Alembic migration for all constraints | `alembic/versions/` | Single migration with all CheckConstraints |
| 3.12 | Add VersionMixin to mutable models | `src/domain/models/mixins.py` | Integer `version` column, auto-increment on update for OCC | D24 |

**Target:** 14/54 model files with constraints (from current 4/54 = 7% to 26%).

---

## Workstream 4: Error Migration (Top 15 Files)

**Dimensions:** D10, D14

The full scope is 458 HTTPException instances across 55 files. This workstream targets the top 15 files by count (covering ~200 instances, 44%).

| # | File | Count | Action |
|---|------|-------|--------|
| 4.1 | `audits.py` | 24 | Replace with structured DomainError/ErrorCode |
| 4.2 | `investigations.py` | 23 | Replace with structured DomainError/ErrorCode |
| 4.3 | `actions.py` | 22 | Replace with structured DomainError/ErrorCode |
| 4.4 | `inductions.py` | 22 | Replace with structured DomainError/ErrorCode |
| 4.5 | `assessments.py` | 22 | Replace with structured DomainError/ErrorCode |
| 4.6 | `form_config.py` | 21 | Replace with structured DomainError/ErrorCode |
| 4.7 | `evidence_assets.py` | 20 | Replace with structured DomainError/ErrorCode |
| 4.8 | `risk_register.py` | 18 | Replace with structured DomainError/ErrorCode |
| 4.9 | `vehicle_checklists.py` | 16 | Replace with structured DomainError/ErrorCode |
| 4.10 | `users.py` | 15 | Replace with structured DomainError/ErrorCode |
| 4.11 | `incidents.py` | 13 | Replace with structured DomainError/ErrorCode |
| 4.12 | `complaints.py` | 12 | Replace with structured DomainError/ErrorCode |
| 4.13 | `workflow.py` | 12 | Replace with structured DomainError/ErrorCode |
| 4.14 | `standards.py` | 12 | Replace with structured DomainError/ErrorCode |
| 4.15 | `tenants.py` | 11 | Replace with structured DomainError/ErrorCode |

**Approach:** Create helper `raise_domain_error(code: ErrorCode, message: str, status: int)` in `src/api/error_helpers.py`. Migrate each file by replacing `raise HTTPException(status_code=N, detail="msg")` with `raise DomainError(code=ErrorCode.XXX, message="msg", status_code=N)`.

---

## Workstream 5: Storybook & Frontend Quality

**Dimensions:** D02, D03, D04, D28

| # | Action | File(s) | Detail |
|---|--------|---------|--------|
| 5.1 | Install Storybook packages | `frontend/package.json` | `@storybook/react-vite`, `@storybook/addon-essentials`, `@storybook/react` |
| 5.2 | Create stories for 22 components | `frontend/src/components/ui/*.stories.tsx` | Default + variant states for each |
| 5.3 | Add axe tests for 6 uncovered components | `frontend/src/components/__tests__/` | ThemeToggle, SetupRequiredPanel, LoadingSkeleton, SkeletonLoader, LiveAnnouncer, Textarea |
| 5.4 | Add route-level axe tests for 8 missing routes | `tests/ux-coverage/` | /uvdb, /settings, /near-misses, /rta, /policies, /compliance, /risk-register, /import-review |
| 5.5 | Add page_view telemetry | `frontend/src/App.tsx` or router | Track route changes with `track_metric("page_view", { route })` |
| 5.6 | Wire `aria-invalid` + `aria-describedby` on forms | `frontend/src/components/ui/Input.tsx`, `Textarea.tsx`, `Select.tsx` | VPAT remediation |

---

## Workstream 6: Observability & Telemetry

**Dimensions:** D13, D28, D32

| # | Action | File(s) | Detail |
|---|--------|---------|--------|
| 6.1 | Wire `track_metric` to 20 highest-traffic routes | `src/api/routes/*.py` | Instruments defined in event-catalog.md but not wired |
| 6.2 | Wire 9 defined-but-unwired instruments | Various service files | `incidents.created`, `incidents.resolved`, `auth.logout`, `workflows.completed`, `api.error_rate_5xx`, `cache.miss_rate`, `celery.task_failures`, `celery.queue_depth` |
| 6.3 | Add `/diagnostics` endpoint | `src/api/routes/health.py` | Returns: config summary, feature flags, connection states, OTel status, migration head |
| 6.4 | Add `logs` command to admin CLI | `scripts/admin_cli.py` | Fetch recent structured logs |
| 6.5 | Add `cache-stats` command to admin CLI | `scripts/admin_cli.py` | Redis DBSIZE, INFO, key counts |
| 6.6 | Add alert-rule validation script | `scripts/validate_alert_rules.py` | Compare metric names in alerting-rules.md vs actual track_metric calls |
| 6.7 | Activate 7 planned alerts | `docs/observability/alerting-rules.md` | Change from "Planned" to "Active" with actual thresholds |

---

## Workstream 7: Privacy & Compliance

**Dimensions:** D07, D08

| # | Action | File(s) | Detail |
|---|--------|---------|--------|
| 7.1 | Add retention rules for domain tables | `src/infrastructure/tasks/cleanup_tasks.py` | incidents (365d), complaints (365d), rtas (365d), near_misses (365d), capa_actions (365d), investigations (365d) |
| 7.2 | Add `restrict_processing()` method | `src/domain/services/gdpr_service.py` | Art. 18 implementation; set `processing_restricted=True` on records |
| 7.3 | Fix DPIA method name reference | `docs/privacy/dpia-incidents.md` | Change `data_portability_export()` to `export_user_data()` |
| 7.4 | Update DPIA consultation status | `docs/privacy/dpia-incidents.md` | Mark internal stakeholders as "Reviewed" |
| 7.5 | Expand compliance-freshness to check 5 files | `.github/workflows/ci.yml` | Add `data-retention-policy.md` and `dpia-template.md` |

---

## Workstream 8: Reliability & CD

**Dimensions:** D05, D18

| # | Action | File(s) | Detail |
|---|--------|---------|--------|
| 8.1 | Add auto-rollback on deploy failure | `.github/workflows/deploy-production.yml` | If health checks fail, execute `az webapp deployment slot swap` back |
| 8.2 | Make post-deploy E2E blocking | `.github/workflows/deploy-production.yml` | Remove `continue-on-error: true` from audit lifecycle E2E |
| 8.3 | Document chaos test results | `docs/evidence/chaos-testing-plan.md` | Record verification results for tested scenarios |
| 8.4 | Document RTO/RPO targets | `docs/evidence/rto-rpo-targets.md` | Based on slot swap (8s) and PITR drill data |

---

## Workstream 9: Configuration & Environment Parity

**Dimensions:** D19, D31

| # | Action | File(s) | Detail |
|---|--------|---------|--------|
| 9.1 | Create env-vars registry | `scripts/infra/env-vars.json` | Central registry of all environment variables with descriptions, required flag, and defaults |
| 9.2 | Make env completeness check blocking | `.github/workflows/ci.yml` | Add `scripts/check_env_completeness.py` as CI job in all-checks |
| 9.3 | Expand config-drift-guard | `.github/workflows/ci.yml` | Compare .env.example keys vs Settings class fields; fail if mismatch |
| 9.4 | Add staging CORS origin | `src/core/config.py` | Add staging URL to CORS allowlist |

---

## Workstream 10: Testing Improvements

**Dimensions:** D01, D15, D16

| # | Action | File(s) | Detail |
|---|--------|---------|--------|
| 10.1 | Create test_factory_build_validation.py | `tests/unit/test_factory_build_validation.py` | Validate all 18 factories produce valid model instances |
| 10.2 | Add golden fixtures for 5 missing entities | `tests/fixtures/golden/` | drivers, vehicles, engineers, kri, digital_signature |
| 10.3 | Tighten CUJ-02 assertions | `tests/e2e/test_cuj02_capa_from_incident.py` | Assert `source_id == incident_id` after CAPA creation |
| 10.4 | Tighten CUJ-03 assertions | `tests/e2e/test_cuj03_daily_vehicle_checklist.py` | Add full checklist completion flow test |
| 10.5 | Tighten CUJ-06 assertions | `tests/e2e/test_cuj06_evidence_upload.py` | Verify uploaded asset is linked to incident |
| 10.6 | Update CUJ traceability matrix | `docs/user-journeys/cuj-test-traceability.md` | Move CUJs from "Gap" to "Covered" after test fixes |
| 10.7 | Raise coverage threshold to 55% | `pyproject.toml` + `ci.yml` | Increase `fail_under` / `--cov-fail-under` from 48 to 55 |

---

## Workstream 11: Documentation & Governance

**Dimensions:** D22, D23, D25, D26, D29

| # | Action | File(s) | Detail |
|---|--------|---------|--------|
| 11.1 | Fill TBD values in capacity plan | `docs/infra/capacity-plan.md` | Replace all "TBD" with actual or estimated values |
| 11.2 | Add unit economics section | `docs/infra/cost-controls.md` | Per-tenant cost breakdown |
| 11.3 | Fill TBD values in cost/capacity runbook | `docs/ops/COST_CAPACITY_RUNBOOK.md` | Replace "TBD — from Azure metrics" |
| 11.4 | Fill TBD values in DR runbook | `docs/ops/DISASTER_RECOVERY_RUNBOOK.md` | Replace all `[PLACEHOLDER]` with actual contact info |
| 11.5 | Fill TBD values in deployment runbook | `docs/DEPLOYMENT_RUNBOOK.md` | Replace `[TBD]` for owner/DBA/DevOps |
| 11.6 | Create ADR-0011 and ADR-0012 | `docs/adr/` | Fill numbering gap (e.g., API versioning, testing strategy) |
| 11.7 | Add ISO8601 validation to release signoff | `scripts/governance/validate_release_signoff.py` | Validate `approved_at_utc` with `datetime.fromisoformat()` |
| 11.8 | Add DORA metrics tracking | `docs/governance/dora-metrics.md` | Lead time, deploy frequency, MTTR, change failure rate |
| 11.9 | Align Locust p95 with SLO | `tests/performance/locustfile.py` | Change p95 threshold from 500ms to 200ms (matching capacity-plan.md) |
| 11.10 | Make doc link check blocking | `.github/workflows/ci.yml` | Remove `\|\| echo "::warning::"` from docs-lint link check |

---

## Workstream 12: I18n & Welsh Coverage

**Dimensions:** D27

| # | Action | File(s) | Detail |
|---|--------|---------|--------|
| 12.1 | Add 200+ Welsh translations | `frontend/src/i18n/locales/cy.json` | Target 85% coverage (1,845/2,171 keys) |
| 12.2 | Make Welsh threshold blocking | `scripts/i18n-check.mjs` | Use `cyBelowThreshold` flag to trigger `process.exit(1)` |
| 12.3 | Remove 87 orphan keys from cy.json | `frontend/src/i18n/locales/cy.json` | Keys in cy that don't exist in en |
| 12.4 | Raise Welsh threshold to 80% | `scripts/i18n-check.mjs` | Update `CY_MIN_COVERAGE` from 70 to 80 |

---

## Dimension-to-Workstream Mapping

| Dim | Current | Target | Workstreams | Primary Actions |
|-----|---------|--------|-------------|-----------------|
| D01 | 4.5 | 9.5 | WS10 | Tighten CUJ tests, update traceability |
| D02 | 3.0 | 9.5 | WS5 | Install Storybook, 22 stories |
| D03 | 5.4 | 9.5 | WS5 | 6 axe tests, 8 route tests, VPAT fixes |
| D04 | 7.2 | 9.5 | WS2, WS5 | Expand Lighthouse URLs, RUM, TTI error |
| D05 | 4.5 | 9.5 | WS8 | Auto-rollback, chaos docs |
| D06 | 4.5 | 9.5 | WS2 | ZAP baseline, npm audit |
| D07 | 4.5 | 9.5 | WS7 | Retention rules, Art. 18, DPIA fixes |
| D08 | 4.5 | 9.5 | WS1, WS7 | Fix placeholder dates, expand freshness |
| D09 | 4.5 | 9.5 | WS2, WS11 | Alembic check, import rules |
| D10 | 4.5 | 9.5 | WS4 | Error migration top 15 files |
| D11 | 3.0 | 9.5 | WS3 | CheckConstraints on 10 models |
| D12 | 7.2 | 9.5 | WS2 | Alembic check in CI |
| D13 | 4.5 | 9.5 | WS6 | Wire track_metric, activate alerts |
| D14 | 4.5 | 9.5 | WS4 | Error migration (shared with D10) |
| D15 | 4.5 | 9.5 | WS2, WS10 | Raise coverage, mutation non-advisory |
| D16 | 5.4 | 9.5 | WS10 | Factory validation, golden fixtures |
| D17 | 7.2 | 9.5 | WS2 | ZAP, radon, alembic, mutation |
| D18 | 4.5 | 9.5 | WS8 | Auto-rollback, post-deploy smoke |
| D19 | 5.4 | 9.5 | WS9 | env-vars.json, blocking completeness |
| D20 | 7.2 | 9.5 | WS2 | SBOM to GitHub Releases |
| D21 | 4.5 | 9.5 | WS2 | Radon complexity in CI |
| D22 | 7.2 | 9.5 | WS11 | Blocking link check, TBD fixes |
| D23 | 5.4 | 9.5 | WS8, WS11 | DR/deploy runbook TBDs |
| D24 | 4.5 | 9.5 | WS3 | VersionMixin, CheckConstraints |
| D25 | 5.4 | 9.5 | WS11 | Locust threshold alignment, capacity TBDs |
| D26 | 5.4 | 9.5 | WS11 | Unit economics, cost runbook TBDs |
| D27 | 5.4 | 9.5 | WS12 | Welsh translations, blocking threshold |
| D28 | 4.5 | 9.5 | WS6, WS5 | Wire instruments, page_view |
| D29 | 7.2 | 9.5 | WS11 | ADR-0011/0012, ISO8601 validation |
| D30 | 7.2 | 9.5 | WS2 | SLSA attestation |
| D31 | 4.5 | 9.5 | WS9 | config-drift expansion |
| D32 | 4.5 | 9.5 | WS6 | /diagnostics endpoint, admin CLI |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| CheckConstraint migration breaks production data | High | Use `NOT VALID` clause; validate existing data first |
| ZAP baseline scan produces too many false positives | Medium | Start with `--fail_on=HIGH`; suppress known FPs in config |
| Error migration introduces regressions | High | Keep error_handler.py as safety net; it normalizes all HTTPExceptions |
| Coverage threshold increase fails tests | Medium | Measure current coverage before raising threshold |
| Storybook install breaks frontend build | Low | devDependency only; doesn't affect production bundle |
| Welsh translation quality is machine-translated | Medium | Mark as "machine-translated, pending review" |
| Mutation testing starts failing builds | Medium | Keep schedule-only; set low initial kill-rate threshold |

---

## Total Change Estimate

| Category | Files Modified | Files Created | Lines Changed (est.) |
|----------|----------------|---------------|---------------------|
| CI/CD workflows | 3 | 0 | ~300 |
| Domain models | 10 | 1 | ~200 |
| API routes (error migration) | 15 | 1 | ~600 |
| Frontend (stories) | 0 | 22 | ~1,100 |
| Frontend (a11y tests) | 0 | 6 | ~300 |
| Backend services (telemetry) | 20 | 1 | ~100 |
| Documentation | 15 | 5 | ~400 |
| Scripts/tools | 3 | 2 | ~150 |
| i18n | 2 | 0 | ~400 |
| Tests | 3 | 2 | ~200 |
| Config | 3 | 1 | ~50 |
| **Total** | **~74** | **~41** | **~3,800** |
