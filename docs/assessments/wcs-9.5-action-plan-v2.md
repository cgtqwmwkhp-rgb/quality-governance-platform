# WCS 9.5 Action Plan v2 — Sequenced Execution

**Date**: 2026-04-03
**Baseline**: Avg WCS 6.2 (0/32 at 9.5)
**Target**: All 32 dimensions ≥ 9.5

---

## Phase 1: CI Hardening (highest leverage — touches 15 dimensions)

### 1.1 Make Locust load test blocking [D04, D17, D25]
- `.github/workflows/ci.yml`: Remove `|| true` from line 1375
- Change job name from "Locust Load Test (advisory)" to "Locust Load Test"
- Change `if:` from `refs/heads/main` to include PRs: `if: github.ref == 'refs/heads/main' || github.event_name == 'pull_request'`
- Validate `locustfile.py` `check_thresholds` works without `|| true`

### 1.2 Add DAST/ZAP baseline scan [D06]
- `.github/workflows/ci.yml`: New job `dast-zap-baseline`
- Uses `zaproxy/action-baseline@v0.13.0` against local uvicorn (same pattern as smoke-tests)
- Fail on WARN/FAIL medium+ findings
- Add to `all-checks` needs

### 1.3 Add import boundary check [D09]
- New `scripts/check_import_boundaries.py`: Validates `src/domain/` does not import from `src/api/`, `src/infrastructure/` does not import from `src/api/`, `src/api/` does not import from `src/infrastructure/` (except through dependency injection)
- `.github/workflows/ci.yml`: New job `import-boundary-check`
- Add to `all-checks` needs

### 1.4 Add DB constraint tests [D11]
- New `tests/integration/test_db_constraints.py`
- Test FK violations, NOT NULL violations, type constraint violations against real Postgres
- Add `CheckConstraint` to 5 key models: `Incident` (status values), `Risk` (severity values), `AuditRun` (status values), `CAPAAction` (status values), `Complaint` (status values)
- Alembic migration for constraints

### 1.5 Align coverage thresholds [D15]
- `.github/workflows/ci.yml`: Change `--cov-fail-under=43` to `--cov-fail-under=48` in both unit-tests and integration-tests jobs
- Verify current coverage can pass 48% (from pyproject.toml target)
- If not, add targeted tests to close the gap

### 1.6 Make mutation testing run on PRs [D17]
- `.github/workflows/ci.yml` mutation-testing job: Change `if:` to include `pull_request`
- Remove `|| true` from mutmut run command (or set kill-rate threshold)

### 1.7 Expand config-drift-guard [D31]
- `.github/workflows/ci.yml` config-drift-guard job: Add checks for:
  - Python version alignment (Dockerfile vs CI matrix)
  - Node version alignment (frontend CI vs Dockerfile)
  - PostgreSQL version alignment (CI services vs deploy)
  - Required env vars list consistency
- Document B1 (staging) vs B2 (prod) as intentional right-sizing in `docs/evidence/env-parity-verification.md`

### 1.8 Add Dependabot auto-merge workflow [D20]
- New `.github/workflows/dependabot-auto-merge.yml`
- Auto-approve + auto-merge for `dependabot` actor when CI passes and update is patch/minor

### 1.9 Add SBOM to releases + provenance attestation [D20, D30]
- `.github/workflows/ci.yml` sbom job: On release event, attach sbom.json as release asset
- Add `actions/attest-build-provenance@v2` step for container image attestation (SLSA Level 2)
- Fix lockfile-check reliability: pin `pip-tools` version explicitly

---

## Phase 2: Production Telemetry Enablement [D13, D28]

### 2.1 Enable production telemetry
- `frontend/src/services/telemetry.ts`: Change `TELEMETRY_ENABLED` default from `!IS_PRODUCTION` to `true`
- CORS is already configured: `purple-water-03205fa03.6.azurestaticapps.net` in `cors_origins`, CSP `connect-src` includes `*.azurewebsites.net`

### 2.2 Update telemetry documentation
- `docs/observability/telemetry-enablement-plan.md`: Mark CORS steps as Complete, update status
- `docs/adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md`: Update enablement criteria, correct regex
- `docs/observability/alerting-rules.md`: Move "Planned" OTel alerts to "Active" after enablement

---

## Phase 3: Documentation Accuracy + Missing Docs [D03, D04, D06, D08, D10, D14, D15, D22, D25, D29]

### 3.1 Fix all doc claims to match CI reality
- `docs/evidence/load-test-baseline.md`: Update enforcement status post-Phase 1.1
- `docs/ci/pr-approval-policy.md`: Remove schemathesis claim, align Locust as blocking
- `docs/ci/gate-inventory.md`: Align all gates with actual ci.yml
- `docs/security/pentest-plan.md`: Update ZAP status to reflect real CI job; document pentest vendor engagement timeline (Q3 2026)

### 3.2 Create security-policy.md [D06]
- New `docs/security/security-policy.md`: Vulnerability disclosure, responsible disclosure process, patch SLA, security contact, scope

### 3.3 Fix capacity-plan SKU contradiction [D25]
- `docs/infra/capacity-plan.md`: Correct PostgreSQL SKU to match actual deployment

### 3.4 Fix error migration tracker [D10, D14]
- `docs/api/error-migration-tracker.md`: Update to reflect runtime coverage via error_handler.py; document remaining OpenAPI spec gaps per route
- `scripts/validate_openapi_contract.py`: Fix expected shape from flat `error_code` to nested `error.code`

### 3.5 Fix CAB workflow signoff example [D22, D29]
- `docs/compliance/cab-workflow.md`: Update example JSON to match `validate_release_signoff.py` REQUIRED_FIELDS

### 3.6 Fix test-coverage-baseline.md [D15]
- `docs/evidence/test-coverage-baseline.md`: Align thresholds with post-Phase 1.5 values

### 3.7 Create runtime config audit doc [D19]
- New `docs/ops/runtime-config-inventory.md`: List all env vars, source (Key Vault / App Service / .env.example), required per environment
- Verify `.env` is not git-tracked (git ls-files confirms it's not)

### 3.8 Fix ISO §8.3 gap [D08]
- `docs/compliance/compliance-matrix-iso.md`: Link to QGP document control module as partial coverage; provide explicit out-of-scope rationale with evidence

### 3.9 Broken cross-doc link repair [D22]
- Run `markdown-link-check` across docs/; fix all 404 internal references
- Fix known broken links: pentest-plan → security-policy.md, gdpr-compliance → auth.py path

### 3.10 Decision log index [D29]
- `docs/governance/decision-log-template.md`: Add decision index listing all 10 ADRs with dates, status, links

---

## Phase 4: Template/Placeholder → Real Data [D01, D03, D05, D23, D26]

### 4.1 VPAT: Replace placeholder contact [D03]
- `docs/accessibility/vpat.md`: Replace placeholder with real org contact

### 4.2 WCAG checklist: Complete items [D03]
- `docs/accessibility/wcag-checklist.md`: Assess items 1.3.4, 1.4.3, 1.4.4, 1.4.11, 1.4.13, 2.2.1, 2.5.3, 3.1.2, 3.3.3, 3.3.4; check or N/A with rationale

### 4.3 Cost capacity runbook: Fill tables [D26]
- `docs/ops/COST_CAPACITY_RUNBOOK.md` §5.1-5.4: Fill with data from cost-controls.md

### 4.4 CUJ traceability update [D01]
- `docs/user-journeys/cuj-test-traceability.md`: Update Partial/Gap CUJs with test file references where tests exist
- `docs/evidence/usability-testing-results.md`: Label as "Interim Internal Baseline"; document external protocol

### 4.5 Chaos testing + PITR drill plan [D05]
- `docs/evidence/chaos-testing-plan.md`: Update verification evidence for already-tested scenarios
- Add DB PITR drill as scheduled item with owner, target Q2 2026

### 4.6 Runbook template → procedure conversion [D23]
- Review docs/runbooks/ and docs/ops/ for template-only files; fill with real procedures where possible

---

## Phase 5: Code Quality & Backend Hardening [D07, D14, D21, D24]

### 5.1 Implement data retention task [D07]
- `src/infrastructure/tasks/cleanup_tasks.py`: Replace stub with real purge queries
- Add audit logging, batching, dry-run mode per data-retention-policy.md

### 5.2 Remove mypy modules from ignore_errors [D21]
- Remove 15 modules from `pyproject.toml` ignore_errors (prioritize routes + simple services)
- Fix resulting type errors
- Reduce `# type: ignore` count by targeting files with highest concentrations
- Update `scripts/validate_type_ignores.py` ceiling downward

### 5.3 Document fail-open idempotency risk model [D24]
- `docs/data/idempotency-and-locking.md`: Add threat model section (safe vs unsafe routes)
- Add monitoring guidance for duplicate detection metrics

---

## Phase 6: Frontend & UX [D02, D27, D32]

### 6.1 Install Storybook + visual regression baseline [D02]
- Install `@storybook/react-vite` in frontend
- Create `.storybook/main.ts` and `preview.ts`
- Create stories for top 10 UI components (Button, Card, Dialog, Toast, Input, Select, Badge, Table, Breadcrumb, Alert)
- Add Playwright screenshot comparison for visual regression baseline

### 6.2 Expand Welsh translations [D27]
- `frontend/src/i18n/locales/cy.json`: Expand to ≥50% key coverage (~1085 keys)
- Cover: admin, forms, audits, actions, risks, incidents, complaints, common UI
- `scripts/i18n-check.mjs`: Add blocking threshold for cy coverage ≥40%

### 6.3 Add admin CLI tool [D32]
- New `scripts/admin_cli.py` using typer
- Commands: health-check, db-status, feature-flags list/toggle, queue-depth, migration-status, user-list
- Update `docs/ops/diagnostics-endpoint-guide.md` to reference CLI alongside HTTP

---

## Phase 7: Resilience & Pipeline [D05, D08, D12, D18]

### 7.1 Migration squash runbook + plan [D12]
- New `docs/runbooks/migration-squash.md`: Step-by-step for 79→1 baseline
- Create `alembic/SQUASH_CHECKPOINT.md` with target date and owner

### 7.2 Deploy rollback automation [D18]
- `.github/workflows/deploy-production.yml`: After health check failure, auto-run `rollback-production.yml` with previous image tag
- Document canary/traffic-splitting as roadmap item with Azure App Service slot-based design in `docs/infra/canary-rollout-plan.md`

### 7.3 Cyclic SHA fix documentation [D08, D18, D29]
- Note: Already fixed in PR #401 (`staging_verified=true` bypass)
- `docs/compliance/cab-workflow.md`: Document the cyclic SHA issue and mitigation
- `docs/evidence/env-parity-verification.md`: Reference deploy signoff validation bypass

---

## Phase 8: Golden Fixtures & Contract Tests [D10, D16]

### 8.1 Add golden fixtures [D16]
- New: `tests/fixtures/golden/policy.json`, `investigation.json`, `document.json`, `user.json`, `near_miss.json`
- Wire into snapshot tests

### 8.2 Expand contract test suite [D10]
- New `tests/contract/test_error_envelope.py`: Validate error envelope shape across 5+ route modules
- New `tests/contract/test_pagination_contract.py`: Validate pagination shape
- Update `docs/ci/pr-approval-policy.md` to describe actual contract test tooling

---

## Execution Sequence

| Order | Phase | Dimensions | Est. Effort |
|-------|-------|------------|-------------|
| 1 | CI Hardening | D04,D06,D09,D11,D15,D17,D20,D25,D30,D31 | Medium |
| 2 | Telemetry | D13, D28 | Small |
| 3 | Doc Accuracy | D03,D06,D08,D10,D14,D15,D19,D22,D25,D29 | Medium |
| 4 | Template→Real | D01,D03,D05,D23,D26 | Small |
| 5 | Code Quality | D07,D21,D24 | Large |
| 6 | Frontend/UX | D02,D27,D32 | Large |
| 7 | Resilience | D05,D08,D12,D18 | Medium |
| 8 | Fixtures/Tests | D10,D16 | Small |

---

## Review Findings Addressed

Items from independent review that were MISSING or WEAK:

| Finding | Resolution |
|---------|------------|
| D19 missing entirely | Added Phase 3.7 — runtime config audit doc |
| D05 DB PITR missing | Added to Phase 4.5 |
| D06 pentest report path | Added vendor timeline in Phase 3.1 |
| D02 visual regression missing | Added Playwright screenshots in Phase 6.1 |
| D11 CheckConstraint in models | Added to Phase 1.4 |
| D12 execution not just runbook | Added SQUASH_CHECKPOINT.md in Phase 7.1 |
| D14 OpenAPI coverage | Added to Phase 3.4 |
| D18 traffic splitting | Documented as roadmap in Phase 7.2 |
| D21 type:ignore reduction | Added to Phase 5.2 |
| D22 broken link repair | Added Phase 3.9 |
| D23 wrong mapping (WS4.3) | Fixed — Phase 4.6 |
| D08/D18/D29 cyclic SHA | Added Phase 7.3 (already fixed in PR #401) |
| D30 SLSA attestation | Added Phase 1.9 |
| D30 lockfile reliability | Added Phase 1.9 |
| D31 B1/B2 narrative | Added to Phase 1.7 |
| D32 HTTP diagnostics | Added to Phase 6.3 |
