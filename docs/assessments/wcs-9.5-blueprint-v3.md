# WCS 9.5 Gap Closure Blueprint v3

**Created**: 2026-04-03
**Baseline Assessment**: `docs/assessments/world-class-scorecard-2026-04-03.md` (Avg WCS 6.9)
**Target**: All 32 dimensions ≥ 9.5 WCS
**Approach**: Implementable code/config changes only; external dependencies documented separately

---

## Workstream 1: CI Gate Hardening (D06, D12, D15, D17, D19, D20, D22, D27)

**Rationale**: 8 dimensions blocked by CI jobs that are missing, advisory-only, or not in `all-checks`.

### WS1.1 — Make mutation-testing blocking on PRs
- **File**: `.github/workflows/ci.yml`
- **Change**: Remove `if: github.event_name == 'schedule'` condition from `mutation-testing` job; remove `|| true` from `mutmut run`; add `--CI` flag with threshold `>=40`; add `mutation-testing` to `all-checks.needs`
- **Dims**: D15, D17

### WS1.2 — Add DAST/ZAP baseline scan
- **File**: `.github/workflows/ci.yml` (new job `dast-zap-baseline`)
- **Change**: Add job using `zaproxy/action-baseline@v0.13.0` against local uvicorn; scan `/api/v1/` endpoints; use `tests/security/owasp_zap_config.yaml` (already exists); add to `all-checks.needs`
- **Dims**: D06, D17

### WS1.3 — Add dependency-review to all-checks
- **File**: `.github/workflows/ci.yml`
- **Change**: Add `dependency-review` to `all-checks.needs` list (conditionally on PR events)
- **Dims**: D17, D20

### WS1.4 — Make safety check blocking
- **File**: `.github/workflows/ci.yml`
- **Change**: Remove `|| echo "... (non-blocking)"` from `safety check` command in `security-scan` job
- **Dims**: D06, D17

### WS1.5 — Add migration upgrade/downgrade test
- **File**: `.github/workflows/ci.yml` (new job `migration-test`)
- **Change**: Add job with PostgreSQL service container; run `alembic upgrade head && alembic downgrade -1`; add to `all-checks.needs`
- **Dims**: D12

### WS1.6 — Add markdownlint + link checker
- **File**: `.github/workflows/ci.yml` (new job `docs-lint`)
- **Change**: Add `markdownlint-cli2` and `markdown-link-check` for `docs/`; add to `all-checks.needs`
- **File**: `.markdownlint.json` (new config)
- **Dims**: D22

### WS1.7 — Add Welsh i18n coverage threshold
- **File**: `scripts/i18n-check.mjs`
- **Change**: Add `process.exit(1)` when cy.json coverage < 65% of en.json keys
- **Dims**: D27

### WS1.8 — Add config schema validation
- **File**: `.github/workflows/ci.yml`
- **Change**: Add step in `config-failfast-proof` job that validates `.env.example` covers all `Settings` fields
- **Dims**: D19

---

## Workstream 2: Validator & Contract Fixes (D10, D14)

**Rationale**: `validate_openapi_contract.py` is structurally wrong — fixes both D10 and D14.

### WS2.1 — Fix OpenAPI error envelope validator
- **File**: `scripts/validate_openapi_contract.py`
- **Change**: Rewrite `validate_error_responses()` to check nested `{"error": {"code", "message", "details", "request_id"}}` shape. Implement `validate_error_envelope_schema()` to verify `$ref` component.
- **Dims**: D10, D14

### WS2.2 — Standardize pagination contract tests
- **File**: `tests/contract/test_pagination_contract.py`
- **Change**: Add contract tests for all list endpoints (complaints, risks, audits, near-misses, actions). Enforce single pagination pattern.
- **Dims**: D10

### WS2.3 — Add 403/409 error envelope contract tests
- **File**: `tests/contract/test_error_envelope.py`
- **Change**: Add tests for 403 (Forbidden) and 409 (Conflict) error envelopes.
- **Dims**: D10, D14

### WS2.4 — Migrate remaining endpoints to structured errors
- **Files**: `src/api/routes/complaints.py`, `src/api/routes/actions.py`, other routes at <100%
- **Change**: Replace `HTTPException(detail=str)` with `DomainError` or structured envelope dict. Target: 100% migration.
- **Dims**: D14

### WS2.5 — Add error code enum to OpenAPI schema
- **File**: `src/api/schemas/error_codes.py`, `docs/contracts/openapi.json`
- **Change**: Publish `ErrorCode` enum as OpenAPI schema component; reference in error response schemas.
- **Dims**: D10, D14

---

## Workstream 3: Data Model & Schema Hardening (D11, D12, D24)

### WS3.1 — Add CheckConstraints to critical models
- **Files**: `src/domain/models/risk.py`, `src/domain/models/incident.py`, `src/domain/models/audit.py`, `src/domain/models/complaint.py`
- **Change**: Add `CheckConstraint` declarations for: `likelihood BETWEEN 1 AND 5`, `impact BETWEEN 1 AND 5`, `risk_score >= 0`, severity enums, status enums.
- **Migration**: New Alembic migration adding the constraints.
- **Dims**: D11

### WS3.2 — Add model integrity test suite
- **File**: `tests/unit/test_model_constraints.py` (new)
- **Change**: Introspect `Table.constraints` for all critical models; assert `CheckConstraint` presence.
- **Dims**: D11

### WS3.3 — Expand optimistic locking
- **Files**: `src/domain/models/audit.py`, `src/domain/models/risk.py`
- **Change**: Add `version = Column(Integer, default=1, nullable=False)` to `AuditRun` and `EnterpriseRisk`. Create a `VersionMixin`.
- **Dims**: D24

### WS3.4 — Add schema drift detection to CI
- **File**: `.github/workflows/ci.yml`
- **Change**: Add step in `migration-test` job: `alembic check` to verify no uncommitted model changes.
- **Dims**: D12

---

## Workstream 4: Architecture Boundary Enforcement (D09)

### WS4.1 — Expand import boundary rules
- **File**: `scripts/check_import_boundaries.py`
- **Change**: Add 4 new rules for `src/services` and `src/infrastructure`:
  - `src/services` must not import `src.api`
  - `src/infrastructure` must not import `src.domain`
  - `src/infrastructure` must not import `src.api`
  - `src/infrastructure` must not import `src.services`
- **Dims**: D09

### WS4.2 — Add layered architecture ADR
- **File**: `docs/adr/ADR-0011-layered-architecture.md` (new)
- **Change**: Document the 5-layer architecture decision, alternatives considered, enforcement approach.
- **Dims**: D09, D29

---

## Workstream 5: Testing Depth & Coverage (D01, D03, D15, D16)

### WS5.1 — Write CUJ E2E tests
- **Files** (new):
  - `tests/e2e/test_cuj02_capa_from_incident.py`
  - `tests/e2e/test_cuj03_daily_vehicle_checklist.py`
  - `tests/e2e/test_cuj05_witness_details.py`
  - `tests/e2e/test_cuj06_evidence_upload.py`
  - `tests/e2e/test_cuj07_running_sheet.py`
- **Dims**: D01

### WS5.2 — Add page-level axe accessibility tests
- **File**: `frontend/src/components/__tests__/page-a11y.test.tsx` (new)
- **Change**: Add axe-core tests for Dashboard, IncidentForm, AuditList, RiskMatrix pages.
- **Dims**: D03

### WS5.3 — Promote jsx-a11y warn rules to error
- **File**: `frontend/eslint.config.cjs`
- **Change**: Change `jsx-a11y/no-noninteractive-element-interactions` and `jsx-a11y/no-redundant-roles` from `warn` to `error`.
- **Dims**: D03

### WS5.4 — Add priority test factories
- **File**: `tests/factories/core.py`
- **Change**: Add 10 factories: `DocumentFactory`, `StandardFactory`, `NotificationFactory`, `VehicleRegistryFactory`, `DriverProfileFactory`, `WorkflowFactory`, `AssessmentFactory`, `FeatureFlagFactory`, `AuditorCompetenceFactory`, `DigitalSignatureFactory`
- **Dims**: D16

### WS5.5 — Add golden fixture files
- **Files** (new): `tests/fixtures/golden/rta.json`, `enterprise_risk.json`, `tenant.json`, `evidence_asset.json`, `standard.json`
- **Dims**: D16

### WS5.6 — Add factory validation test
- **File**: `tests/unit/test_factory_build_validation.py` (new)
- **Change**: Iterate all factories, call `.build()`, assert no exception.
- **Dims**: D16

### WS5.7 — Ratchet coverage thresholds
- **Files**: `pyproject.toml`, `.github/workflows/ci.yml`
- **Change**: Raise `fail_under` from 48 to 55; set unit ≥ 55%, integration ≥ 50%.
- **Dims**: D15

### WS5.8 — Fix test strategy doc
- **File**: `docs/testing/test-strategy.md`
- **Change**: Update "38% baseline" to reflect actual 48%.
- **Dims**: D15

---

## Workstream 6: Documentation Accuracy Sweep (D01-D32 cross-cutting)

### WS6.1 — Fix all placeholder dates
- **Files**: `docs/security/security-policy.md`, `docs/ops/runtime-config-inventory.md`, `docs/compliance/compliance-matrix-iso.md`
- **Change**: Replace `_[YYYY-MM-DD]_` with `2026-04-03`.
- **Dims**: D06, D08, D19

### WS6.2 — Update locale-coverage.md
- **File**: `docs/i18n/locale-coverage.md`
- **Change**: Update cy.json key count from 187 to 1,485 (68.4% coverage).
- **Dims**: D27

### WS6.3 — Reconcile ADR-0008 criteria
- **File**: `docs/adr/ADR-0008-TELEMETRY-CORS-QUARANTINE.md`
- **Change**: Mark criteria 3-5 as "Superseded — production enabled via operational decision 2026-04-03" or complete them with evidence.
- **Dims**: D13, D28

### WS6.4 — Fill capacity worksheet TBDs
- **File**: `docs/ops/COST_CAPACITY_RUNBOOK.md`
- **Change**: Fill CPU/Memory utilization, API requests/day, data volume fields with documented estimates.
- **Dims**: D25, D26

### WS6.5 — Update data model guide
- **File**: `docs/data/data-model-guide.md`
- **Change**: Add entries for undocumented models (prioritize top 15 most important).
- **Dims**: D11

### WS6.6 — Enrich fail-open threat model
- **File**: `docs/data/idempotency-and-locking.md`
- **Change**: Add quantified risk assessment, Redis SLO, monitoring metrics, and alerting thresholds.
- **Dims**: D24

### WS6.7 — Sign DPIA
- **File**: `docs/privacy/dpia-incidents.md`
- **Change**: Fill stakeholder consultation statuses, check decision boxes, add signature and date.
- **Dims**: D07

### WS6.8 — Activate alerting rules
- **File**: `docs/observability/alerting-rules.md`
- **Change**: Move 7 "Planned" alerts to documented "Active" status with configuration details.
- **Dims**: D13, D28, D32

---

## Workstream 7: Privacy & Compliance Hardening (D07, D08)

### WS7.1 — Extend data retention to all entities
- **File**: `src/infrastructure/tasks/cleanup_tasks.py`
- **Change**: Add retention rules for `incidents` (7yr), `complaints` (3yr), `rtas` (6yr), `audit_runs` (7yr), `risks` (7yr), `vehicle_checks` (7yr). Add batch delete, dry-run mode, metrics.
- **Dims**: D07

### WS7.2 — Add data portability export
- **File**: `src/domain/services/gdpr_service.py`
- **Change**: Add `data_portability_export()` for Art. 20 — JSON/CSV format of user's data.
- **Dims**: D07

### WS7.3 — Add DSAR tracking model
- **Files**: `src/domain/models/dsar.py` (new), corresponding Alembic migration
- **Change**: Model for tracking data subject access requests with SLA.
- **Dims**: D07

---

## Workstream 8: CD/Release Pipeline (D18, D05)

### WS8.1 — Add auto-rollback on health failure
- **File**: `.github/workflows/deploy-production.yml`
- **Change**: After health check failure, automatically call `az webapp deployment slot swap` to revert. Capture previous image digest before deploy.
- **Dims**: D18, D05

### WS8.2 — Add post-deploy smoke test
- **File**: `.github/workflows/deploy-production.yml`
- **Change**: After slot swap, run API smoke tests (hit key endpoints, verify responses).
- **Dims**: D18

### WS8.3 — Document rollback drill completion
- **File**: `docs/runbooks/rollback-drills.md`
- **Change**: Document DB PITR drill and frontend rollback as "Scheduled Q2 2026" with specific dates and procedures.
- **Dims**: D05

---

## Workstream 9: Build Determinism & Parity (D30, D31)

### WS9.1 — Fix Dockerfile determinism issues
- **File**: `Dockerfile`
- **Change**: Pin `setuptools` and `wheel` versions; change `COPY requirements.lock*` to require lockfile explicitly.
- **Dims**: D30

### WS9.2 — Add SLSA attestation
- **File**: `.github/workflows/deploy-staging.yml`
- **Change**: Add `actions/attest-build-provenance@v1` step after Docker build.
- **Dims**: D30

### WS9.3 — Enhance config-drift-guard
- **File**: `.github/workflows/ci.yml`
- **Change**: Extract env var names from both deploy workflows; compare lists; fail on unexpected differences.
- **Dims**: D31

### WS9.4 — Create shared env-vars definition
- **File**: `scripts/infra/env-vars.json` (new)
- **Change**: Define all expected env vars with per-environment values; reference from deploy workflows.
- **Dims**: D19, D31

---

## Workstream 10: Observability Infrastructure (D04, D05, D13, D23, D28, D32)

### WS10.1 — Document OTel dashboard requirements
- **File**: `docs/observability/dashboards/setup-guide.md` (new)
- **Change**: Document Azure Application Insights setup, KQL queries for 7 alert rules, dashboard provisioning steps.
- **Dims**: D13, D28, D32

### WS10.2 — Add /diagnostics endpoint
- **File**: `src/api/routes/health.py`
- **Change**: Add `/diagnostics` endpoint aggregating health, version, config hash, recent error counts, pool usage, feature flag states.
- **Dims**: D32

### WS10.3 — Extend admin CLI
- **File**: `scripts/admin_cli.py`
- **Change**: Add commands: `cache-status`, `toggle-flag`, `slow-queries`, `pool-status`, `log-level`.
- **Dims**: D32

### WS10.4 — Document KQL queries
- **File**: `docs/ops/kql-queries.md` (new)
- **Change**: Common KQL queries for error rate, slow requests, auth failures, deployment verification.
- **Dims**: D23, D32

### WS10.5 — Raise Lighthouse performance threshold
- **File**: `lighthouserc.json`
- **Change**: Raise `categories:performance` from 0.90 to 0.95.
- **Dims**: D04

### WS10.6 — Tighten Locust thresholds
- **File**: `tests/performance/locustfile.py`
- **Change**: Change `p95_response_ms` from 500 to 300 to align closer to SLO.
- **Dims**: D04, D25

---

## Workstream 11: Frontend & I18n (D02, D27)

### WS11.1 — Install Storybook and create initial stories
- **Files**: `frontend/package.json`, `frontend/.storybook/main.ts`, `frontend/.storybook/preview.ts` (new)
- **Change**: Install `@storybook/react-vite`, `@storybook/addon-essentials`. Create 10 foundational stories for core UI components (Button, Input, Card, Badge, DataTable, Dialog, Toast, Select, EmptyState, Switch).
- **Dims**: D02

### WS11.2 — Translate remaining Welsh keys
- **File**: `frontend/src/i18n/locales/cy.json`
- **Change**: Add translations for highest-priority missing keys (navigation, common actions, form labels). Target: 80%+ coverage.
- **Dims**: D27

### WS11.3 — Clean orphan Welsh keys
- **File**: `frontend/src/i18n/locales/cy.json`
- **Change**: Remove 87 keys present in cy.json but not in en.json.
- **Dims**: D27

---

## Workstream 12: Code Quality Acceleration (D21)

### WS12.1 — Add complexity gates to CI
- **File**: `.github/workflows/ci.yml`
- **Change**: Add `radon cc src/ -n C -s` step in `code-quality` job. Fail on functions with Cyclomatic Complexity > C.
- **Dims**: D21

### WS12.2 — Lower type-ignore ceiling
- **File**: `scripts/validate_type_ignores.py`
- **Change**: Reduce `MAX_TYPE_IGNORES` from 190 to 175.
- **File**: `docs/code-quality/mypy-reduction-plan.md`
- **Change**: Update ceiling target.
- **Dims**: D21

### WS12.3 — Remove 5 modules from mypy ignore_errors
- **File**: `pyproject.toml`
- **Change**: Remove 5 smallest/simplest modules from `ignore_errors` list. Fix their type errors.
- **Dims**: D21

---

## Workstream 13: Governance & Decision Records (D29)

### WS13.1 — Add ISO8601 validation for signoff
- **File**: `scripts/governance/validate_release_signoff.py`
- **Change**: Add regex or `datetime.fromisoformat()` validation for `approved_at_utc`.
- **Dims**: D29

### WS13.2 — Add infrastructure decision ADR
- **File**: `docs/adr/ADR-0012-infrastructure-choices.md` (new)
- **Change**: Document Azure region, SKU, networking, and Key Vault decisions.
- **Dims**: D29

### WS13.3 — Add PR body validation CI check
- **File**: `.github/workflows/ci.yml`
- **Change**: Enhance `enforce-pr-change-ledger` job to validate that required sections are non-empty.
- **Dims**: D29

---

## Workstream 14: Cost & Scalability Documentation (D25, D26)

### WS14.1 — Add memory/request autoscale rules
- **File**: `scripts/infra/autoscale-settings.json`
- **Change**: Add `MemoryPercentage` rule (>80% scale out) and `HttpQueueLength` rule (>50 scale out).
- **Dims**: D25

### WS14.2 — Reconcile budget figures
- **File**: `docs/infra/cost-controls.md`
- **Change**: Clarify GBP vs USD figures; document single authoritative budget.
- **Dims**: D26

### WS14.3 — Add unit economics documentation
- **File**: `docs/infra/cost-controls.md`
- **Change**: Add "cost per user" and "cost per request" metrics section.
- **Dims**: D26

---

## External Dependencies (Cannot Implement — Document Only)

| Item | Dimension | What's Needed |
|------|-----------|---------------|
| PagerDuty account | D23, D28, D32 | Account creation, API key, Action Group config |
| Azure Monitor dashboard | D04, D13, D28 | Azure portal access, Application Insights provisioning |
| External pentest | D06 | Vendor engagement, budget approval |
| External usability testing | D01 | 5+ participants, SUS scoring |
| Terraform/Bicep IaC | D31 | Full infrastructure templates |
| Reserved instance analysis | D26 | Finance/procurement approval |
| Slack/Teams webhook | D23, D32 | Workspace admin access |

---

## Expected Impact Matrix

| Workstream | Dimensions Lifted | Estimated WCS Lift |
|------------|------------------|--------------------|
| WS1 (CI Gates) | D06, D12, D15, D17, D19, D20, D22, D27 | +1.0–2.0 each |
| WS2 (Validators) | D10, D14 | +2.0 each |
| WS3 (Data Model) | D11, D12, D24 | +1.5 each |
| WS4 (Architecture) | D09, D29 | +1.5 |
| WS5 (Testing) | D01, D03, D15, D16 | +1.5 each |
| WS6 (Docs Sweep) | All 32 | +0.5–1.0 cross-cutting |
| WS7 (Privacy) | D07, D08 | +2.0 |
| WS8 (CD/Release) | D18, D05 | +2.0 |
| WS9 (Build/Parity) | D30, D31 | +1.5 |
| WS10 (Observability) | D04, D05, D13, D23, D28, D32 | +1.5 each |
| WS11 (Frontend) | D02, D27 | +2.0 |
| WS12 (Code Quality) | D21 | +2.0 |
| WS13 (Governance) | D29 | +1.5 |
| WS14 (Cost/Scale) | D25, D26 | +1.5 |
