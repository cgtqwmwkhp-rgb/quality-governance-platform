# WCS 9.5 Gap Closure Blueprint v2

**Date**: 2026-04-03  
**Baseline**: Strict assessment avg WCS 6.2/10 (0 dimensions at 9.5)  
**Target**: All 32 dimensions ≥ 9.5 WCS

---

## Workstream 1: CI Hardening (D04, D06, D09, D11, D17, D20, D25, D30, D31)

### WS1.1 — Make Locust load test blocking (D04, D17, D25)
- **File**: `.github/workflows/ci.yml` lines 1306-1383
- **Change**: Remove `|| true` from line 1375; remove `(advisory)` from job name; change `if:` to run on PRs to main too
- **Impact**: D04, D17, D25 all cite Locust advisory as gap

### WS1.2 — Add DAST/ZAP scan to CI (D06)
- **File**: `.github/workflows/ci.yml` — new job `dast-zap-scan`
- **Change**: Add OWASP ZAP baseline scan against local app (similar to smoke-tests pattern)
- **Impact**: D06 claims ZAP exists; this makes it real

### WS1.3 — Add import boundary lint (D09)
- **File**: New script `scripts/check_import_boundaries.py`
- **File**: `.github/workflows/ci.yml` — new job `import-boundary-check`
- **Change**: Enforce domain→infrastructure, api→domain import rules; block reverse deps
- **Impact**: D09 has no automated enforcement

### WS1.4 — Add constraint validation tests (D11)
- **File**: New `tests/integration/test_db_constraints.py`
- **Change**: Test FK violations, NOT NULL, type constraints against real DB
- **Impact**: D11 has no deep constraint evidence

### WS1.5 — Add Dependabot auto-merge workflow (D20)
- **File**: New `.github/workflows/dependabot-auto-merge.yml`
- **Change**: Auto-approve+merge patch/minor Dependabot PRs after CI passes
- **Impact**: D20 gap: no auto-merge policy

### WS1.6 — Add SBOM to GitHub Releases (D20, D30)
- **File**: `.github/workflows/ci.yml` `sbom` job
- **Change**: On tag/release, attach `sbom.json` as release asset
- **Impact**: D20 SBOM not published; D30 no provenance

### WS1.7 — Expand config-drift-guard (D31)
- **File**: `.github/workflows/ci.yml` lines 142-188
- **Change**: Add env-var comparison (staging vs prod required vars list); check Docker image parity; validate Python/Node version alignment
- **Impact**: D31 drift guard checks only 1 string in 4 files

### WS1.8 — Make mutation testing run on PRs (D17)
- **File**: `.github/workflows/ci.yml` mutation-testing job
- **Change**: Remove `if: github.event_name == 'schedule'` restriction; add kill-rate threshold
- **Impact**: D17 mutation is weekly-only

### WS1.9 — Align coverage thresholds (D15)
- **File**: `.github/workflows/ci.yml` (unit-tests, integration-tests)
- **File**: `pyproject.toml` `[tool.coverage.report]`
- **Change**: Set all to 48% consistently
- **Impact**: D15 has 43 vs 48 inconsistency

---

## Workstream 2: Production Telemetry Enablement (D13, D28, partially D04)

### WS2.1 — Enable production telemetry in frontend
- **File**: `frontend/src/services/telemetry.ts`
- **Change**: Change `TELEMETRY_ENABLED` default to `true` for all environments (CORS origins are already configured correctly — `purple-water-03205fa03.6.azurestaticapps.net` is in `cors_origins`)
- **Impact**: D28 production telemetry disabled; D13 no production traces

### WS2.2 — Verify CORS alignment
- **File**: `src/main.py` line 305 (regex) + `src/core/config.py` line 190-192 (explicit origins)
- **Verify**: Production SWA origin `purple-water-03205fa03.6.azurestaticapps.net` is already in `cors_origins`. CSP `connect-src` already includes `*.azurewebsites.net`. No code change needed — just verification.
- **Impact**: Removes the stated CORS blocker

### WS2.3 — Update telemetry enablement plan documentation
- **File**: `docs/observability/telemetry-enablement-plan.md`
- **Change**: Mark CORS verification steps as Complete; update production status
- **Impact**: D28 documentation accuracy

### WS2.4 — Update ADR-0008 to match actual CORS config
- **File**: `docs/adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md`
- **Change**: Update enablement criteria to reflect current state; correct CORS regex reference
- **Impact**: D28, D22 doc accuracy

---

## Workstream 3: Documentation Accuracy Sweep (D04, D06, D10, D15, D22, D25)

### WS3.1 — Fix load-test-baseline.md claims
- **File**: `docs/evidence/load-test-baseline.md`
- **Change**: After WS1.1 (if Locust becomes blocking), update to match reality. If advisory, correct "enforced" claims.

### WS3.2 — Fix pr-approval-policy.md claims
- **File**: `docs/ci/pr-approval-policy.md`
- **Change**: Remove schemathesis claim; align Locust description with actual CI behaviour

### WS3.3 — Fix gate-inventory.md
- **File**: `docs/ci/gate-inventory.md`
- **Change**: Align all gates with actual `ci.yml` behaviour (blocking vs advisory, schedule vs PR)

### WS3.4 — Fix pentest-plan.md DAST claim
- **File**: `docs/security/pentest-plan.md`
- **Change**: After WS1.2, update ZAP status to reflect real CI job

### WS3.5 — Create security-policy.md (D06)
- **File**: New `docs/security/security-policy.md`
- **Change**: Vulnerability disclosure, responsible disclosure, patch SLA, security contact

### WS3.6 — Fix capacity-plan SKU contradiction (D25)
- **File**: `docs/infra/capacity-plan.md`
- **Change**: Align PostgreSQL SKU reference to match `scalability-plan.md` and `cost-controls.md`

### WS3.7 — Fix error-migration-tracker percentages (D10, D14)
- **File**: `docs/api/error-migration-tracker.md`
- **Change**: Since error_handler.py wraps ALL responses at runtime, update tracker to reflect ~100% runtime coverage; document remaining OpenAPI spec gaps

### WS3.8 — Fix CAB workflow signoff example (D22, D29)
- **File**: `docs/compliance/cab-workflow.md`
- **Change**: Update example JSON to match `REQUIRED_FIELDS` in `validate_release_signoff.py`

### WS3.9 — Fix test-coverage-baseline.md thresholds (D15)
- **File**: `docs/evidence/test-coverage-baseline.md`
- **Change**: Align with actual CI thresholds after WS1.9

---

## Workstream 4: Template/Placeholder Docs → Real Data (D01, D03, D23, D26, D29)

### WS4.1 — VPAT: Replace placeholder contact (D03)
- **File**: `docs/accessibility/vpat.md`
- **Change**: Replace `accessibility@governance.platform — substitute` with real org contact

### WS4.2 — WCAG checklist: Complete unchecked items (D03)
- **File**: `docs/accessibility/wcag-checklist.md`
- **Change**: Assess and check/N/A items 1.3.4, 1.4.3, 1.4.4, 1.4.11, 1.4.13, 2.2.1, 2.5.3, 3.1.2, 3.3.3, 3.3.4 with evidence refs

### WS4.3 — Cost capacity runbook: Fill empty tables (D26)
- **File**: `docs/ops/COST_CAPACITY_RUNBOOK.md` §5.1-5.4
- **Change**: Fill monthly cost trend, resource inventory, growth assumptions from cost-controls.md data

### WS4.4 — Decision log: Convert to index (D29)
- **File**: `docs/governance/decision-log-template.md`
- **Change**: Add decision index listing all 10 ADRs with dates, status, and links

### WS4.5 — CUJ traceability: Address Gap/Partial items (D01)
- **File**: `docs/user-journeys/cuj-test-traceability.md`
- **Change**: Add test file references for Gap CUJs where tests exist; update statuses

### WS4.6 — Usability testing: Document baseline properly (D01)
- **File**: `docs/evidence/usability-testing-results.md`
- **Change**: Clearly label as "Interim Internal Baseline"; add protocol for external Q2 2026

---

## Workstream 5: Code Quality & Backend Hardening (D07, D14, D21, D24)

### WS5.1 — Implement data retention task (D07)
- **File**: `src/infrastructure/tasks/cleanup_tasks.py`
- **Change**: Replace stub `run_data_retention` with actual purge queries per `data-retention-policy.md`

### WS5.2 — Fix OpenAPI error schema alignment (D14)
- **File**: `scripts/validate_openapi_contract.py`
- **Change**: Update expected shape from flat `error_code` to nested `error.code` matching actual handler

### WS5.3 — Remove mypy modules from ignore_errors (D21)
- **File**: `pyproject.toml`
- **Strategy**: Remove 10-15 least-complex modules from ignore_errors list; fix resulting type errors
- **Priority modules**: Routes with few type issues first (health, feature_flags, slo, signatures, notifications)

### WS5.4 — Document idempotency fail-open risk (D24)
- **File**: `docs/data/idempotency-and-locking.md`
- **Change**: Add explicit threat model section: which routes are safe (reads), which are unsafe (payments/mutations); add monitoring guidance for duplicate detection

---

## Workstream 6: Frontend & UX (D02, D27, D32)

### WS6.1 — Install Storybook + create initial stories (D02)
- **Files**: New `frontend/.storybook/`, new `frontend/src/components/ui/*.stories.tsx`
- **Change**: Install @storybook/react-vite; create stories for top 10 UI components (Button, Card, Dialog, Toast, etc.)

### WS6.2 — Expand Welsh translations (D27)
- **File**: `frontend/src/i18n/locales/cy.json`
- **Change**: Add translations for high-value categories (admin, forms, audits, actions, risks) — target ≥50% key coverage
- **File**: `scripts/i18n-check.mjs`
- **Change**: Make cy parity check blocking at a threshold (e.g. ≥40%)

### WS6.3 — Add admin CLI tool (D32)
- **File**: New `scripts/admin_cli.py`
- **Change**: Typer-based CLI for health check, queue depth, feature flag toggle, DB migration status, user management

---

## Workstream 7: Resilience & Operations (D05, D08, D12, D18)

### WS7.1 — Document chaos drill execution plan (D05)
- **File**: `docs/evidence/chaos-testing-plan.md`
- **Change**: Fill verification evidence for scenarios already implicitly tested; schedule Q2 2026 drills with owners

### WS7.2 — Add migration squash runbook (D12)
- **File**: New `docs/runbooks/migration-squash.md`
- **Change**: Step-by-step guide for 79→1 baseline migration squash with freeze/archive/verify steps

### WS7.3 — Fix ISO §8.3 gap documentation (D08)
- **File**: `docs/compliance/compliance-matrix-iso.md`
- **Change**: Link to QGP document control module as partial coverage; document out-of-scope rationale

### WS7.4 — Add automated rollback on health failure (D18)
- **File**: `.github/workflows/deploy-production.yml`
- **Change**: After deploy, if health check fails, automatically revert to previous container image tag

---

## Workstream 8: Golden Fixtures & Contract Tests (D10, D16)

### WS8.1 — Add golden fixtures (D16)
- **Files**: New `tests/fixtures/golden/policy.json`, `investigation.json`, `document.json`, `user.json`, `near_miss.json`
- **Change**: 5 additional golden fixtures matching factory output

### WS8.2 — Expand contract test suite (D10)
- **Files**: New `tests/contract/test_error_envelope.py`, `test_pagination_contract.py`
- **Change**: Test error envelope shape across multiple route modules; test pagination contract

---

## Dimension → Workstream Mapping

| Dim | WS Items | Current WCS | Target |
|-----|----------|-------------|--------|
| D01 | WS4.5, WS4.6 | 7.2 | 9.5 |
| D02 | WS6.1 | 6.3 | 9.5 |
| D03 | WS4.1, WS4.2 | 6.3 | 9.5 |
| D04 | WS1.1, WS3.1 | 5.4 | 9.5 |
| D05 | WS7.1 | 6.3 | 9.5 |
| D06 | WS1.2, WS3.4, WS3.5 | 4.5 | 9.5 |
| D07 | WS5.1 | 5.4 | 9.5 |
| D08 | WS7.3, WS3.8 | 7.2 | 9.5 |
| D09 | WS1.3 | 6.3 | 9.5 |
| D10 | WS3.7, WS8.2 | 6.3 | 9.5 |
| D11 | WS1.4 | 6.3 | 9.5 |
| D12 | WS7.2 | 7.2 | 9.5 |
| D13 | WS2.1, WS2.2, WS2.3 | 4.5 | 9.5 |
| D14 | WS3.7, WS5.2 | 6.3 | 9.5 |
| D15 | WS1.9, WS3.9 | 5.4 | 9.5 |
| D16 | WS8.1 | 6.3 | 9.5 |
| D17 | WS1.1, WS1.8 | 7.2 | 9.5 |
| D18 | WS7.4 | 6.3 | 9.5 |
| D19 | Verify .env untracked | 6.3 | 9.5 |
| D20 | WS1.5, WS1.6 | 8.0 | 9.5 |
| D21 | WS5.3 | 6.3 | 9.5 |
| D22 | WS3.2-WS3.9, WS2.4 | 7.2 | 9.5 |
| D23 | WS4.3, WS7.1 | 7.2 | 9.5 |
| D24 | WS5.4 | 6.3 | 9.5 |
| D25 | WS1.1, WS3.6 | 5.3 | 9.5 |
| D26 | WS4.3 | 5.4 | 9.5 |
| D27 | WS6.2 | 5.4 | 9.5 |
| D28 | WS2.1-WS2.4 | 3.8 | 9.5 |
| D29 | WS3.8, WS4.4 | 7.2 | 9.5 |
| D30 | WS1.6 | 8.0 | 9.5 |
| D31 | WS1.7 | 5.4 | 9.5 |
| D32 | WS6.3 | 6.3 | 9.5 |
