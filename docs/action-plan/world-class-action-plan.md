# World-Class Action Plan — Quality Governance Platform

> **Generated**: 2026-03-07
> **Audit method**: 3-round check-and-challenge (Technical Correctness → Integration/Dependency → Completeness)
> **Evidence base**: Static code analysis of full repo, 250+ API endpoints mapped, 48+ DB models verified
> **Goal**: Exceed world-class score 10/10

---

## Challenge Round Summary

| Round | Lens | Key Corrections Made |
|-------|------|---------------------|
| **R1** | Technical Correctness | F-006 downgraded P0→P1 (telemetry dormant, not crashing). F-008 recharacterized (double-commit is no-op; real bug is ComplaintService audit event ordering). F-009 clarified (cross-domain FK, ambiguous intent). |
| **R2** | Integration & Dependency | NEW: `RiskControlMapping` + `BowTieElement` FKs point to wrong table. NEW: FE AI API paths don't match BE routes. Document control FK issue expanded to 3 models. 250+ API endpoints mapped for tenant_id propagation. |
| **R3** | Completeness | **CRITICAL NEW**: All ~15 admin config FE calls missing `/api/v1/` prefix = 404 in production. Celery tasks NOT empty (662 lines, 11 files) BUT config attributes missing from Settings. ComplaintService commits audit events in wrong transaction. |

---

## Tier 1 — Critical Fixes (P0 Blockers)
> These prevent crashes, data loss, or broken critical paths. Do first.

### AP-01: Fix admin config API path prefix (NEW — P0)
**Finding**: All ~15 admin config API calls (`formTemplatesApi`, `contractsApi`, `lookupsApi`, `settingsApi`) use `/admin/config/` WITHOUT the `/api/v1/` prefix. Every other API call includes `/api/v1/`. Backend mounts all routes at `/api/v1/` (`src/main.py:290`).
**Evidence**: `frontend/src/api/client.ts:3362` — `` `/admin/config/templates${formType ? ...}` `` vs all other calls using `/api/v1/incidents/`, `/api/v1/complaints/`, etc. `src/api/__init__.py:120` — `router.include_router(form_config.router, prefix="/admin/config")`. `src/main.py:290` — `app.include_router(api_router, prefix="/api/v1")`.
**Impact**: Form builder, contracts management, lookup tables, system settings — ALL 404 from frontend.
**Fix**: Prepend `/api/v1` to all admin config paths in `frontend/src/api/client.ts:3356-3451`.
**Files**: `frontend/src/api/client.ts`
**Tests**: Vitest mock verifying correct URL construction; E2E test loading admin forms page.
**Rollback**: `git revert`

### AP-02: Fix missing `await` on 13 AI intelligence endpoints (P0)
**Finding**: All async service methods called without `await` — routes return coroutine objects, not data.
**Evidence**: `src/api/routes/ai_intelligence.py:102` — `return predictor.predict_risk_factors(lookback_days)` (no await). Services confirmed async: `src/domain/services/ai_predictive_service.py:301` — `async def predict_risk_factors`.
**Impact**: All AI intelligence endpoints return serialization errors or empty responses.
**Fix**: Add `await` to all 13 service calls. Change `from sqlalchemy.orm import Session` (line 16) to use `DbSession` alias.
**Files**: `src/api/routes/ai_intelligence.py`
**Tests**: Unit test per endpoint with mocked async service.
**Rollback**: `git revert`

### AP-03: Fix Pydantic v2 schema syntax (P0)
**Finding**: `min_items`/`max_items` are Pydantic v1 — silently ignored in v2, meaning no list length validation.
**Evidence**: `src/api/routes/ai_intelligence.py:52` — `answers: list[str] = Field(..., min_items=1, max_items=7)`. Line 71: `findings: list[str] = Field(..., min_items=1, max_items=50)`.
**Fix**: Replace `min_items` → `min_length`, `max_items` → `max_length`.
**Files**: `src/api/routes/ai_intelligence.py`
**Tests**: Schema validation test with 0, 1, and 8 items.
**Rollback**: `git revert`

### AP-04: Fix `Loader2` missing import — FE crash on form submit (P0)
**Finding**: `Loader2` component used but not imported in 2 files.
**Evidence**: `frontend/src/pages/Incidents.tsx:373` — `<Loader2 className="w-4 h-4 animate-spin" />`. Import block (lines 1-15) does not include `Loader2`. Same in `Complaints.tsx:412`.
**Fix**: Add `Loader2` to lucide-react import in both files.
**Files**: `frontend/src/pages/Incidents.tsx`, `frontend/src/pages/Complaints.tsx`
**Tests**: Vitest render test verifying submit button renders with spinner.
**Rollback**: `git revert`

### AP-05: Fix ComplaintService audit event transaction split (P0)
**Finding**: `ComplaintService.create_complaint` commits the complaint FIRST (line 63), then records the audit event AFTER (line 68). The audit event is in a separate transaction and can be lost if an error occurs. `IncidentService` does this correctly: flush → audit → commit atomically.
**Evidence**: `src/domain/services/complaint_service.py:63` — `await self.db.commit()` then line 68: `await record_audit_event(...)`. Compare `src/domain/services/incident_service.py:88` — `await self.db.flush()` then line 90: `await record_audit_event(...)` then line 102: `await self.db.commit()`.
**Fix**: Replace `commit()` with `flush()` before audit event, then `commit()` after audit event (matching IncidentService pattern). Apply same fix to `update_complaint` (line 135).
**Files**: `src/domain/services/complaint_service.py`
**Tests**: Integration test verifying audit event and complaint are atomic (rollback on audit failure should rollback complaint).
**Rollback**: `git revert`

### AP-06: Add missing config attributes for telemetry + Celery (P0)
**Finding**: `setup_telemetry()` references `settings.app_version`, `settings.otel_trace_sample_rate`, `settings.applicationinsights_connection_string` — none defined in `Settings`. `celery_app.py` references `settings.celery_broker_url`, `settings.celery_result_backend` — also missing.
**Evidence**: `src/infrastructure/monitoring/azure_monitor.py:99,106,117`. `src/infrastructure/tasks/celery_app.py:8-9`. `src/core/config.py` — grep returns empty for all 5 attributes.
**Fix**: Add all 5 attributes to `Settings` class with sensible defaults. Add corresponding entries to `.env.example`.
**Files**: `src/core/config.py`, `.env.example`
**Tests**: Config instantiation test; verify `setup_telemetry()` doesn't crash; verify `celery_app` imports cleanly.
**Rollback**: `git revert`

### AP-07: Gate staging deploy on CI success (P0)
**Finding**: `deploy-staging.yml` deploys on push to `main` without waiting for CI.
**Evidence**: `.github/workflows/deploy-staging.yml:3-7` — triggers on `push: branches: [main]` with no `needs` or `workflow_run` dependency on CI.
**Decision**: User chose branch protection rules (require CI status checks before merge to main).
**Fix**: Configure branch protection on `main` requiring `all-checks` status from `ci.yml`. Document in ADR.
**Files**: GitHub repo settings (branch protection rules), `docs/adr/` (new ADR)
**Tests**: Attempt merge without CI pass; verify blocked.
**Rollback**: Remove branch protection rule.

### AP-08: Replace 173 `datetime.utcnow` instances (P0)
**Finding**: `datetime.utcnow` is deprecated (Python 3.12+) and produces naive datetimes — timezone bugs in multi-region.
**Evidence**: `grep -c "datetime.utcnow" src/domain/models/` returns 173. Files: `ims_unification.py` (46), `ai_copilot.py` (7), `notification.py` (5), `iso27001.py` (6), `tenant.py` (1), `document_control.py` (20+), `analytics.py` (20+), `planet_mark.py`, `uvdb_achilles.py`, `auditor_competence.py`.
**Fix**: Replace all with `datetime.now(timezone.utc)` per `base.py` pattern. Two batches: core models first, then IMS/ISO/analytics.
**Files**: 12+ model files in `src/domain/models/`
**Tests**: Timestamp comparison test ensuring timezone-aware; existing model tests.
**Rollback**: `git revert`

---

## Tier 2 — High-Risk Fixes (P1 Major Defects)
> These fix broken workflows, data integrity gaps, and CI weaknesses.

### AP-09: Fix FK references across 3 domains (P1)
**Finding**: Cross-domain FK mismatches in 3 areas:
- `document_control.py:232,293,317` — `DocumentApprovalInstance`, `DocumentDistribution`, `DocumentAccessLog` reference `document_versions.id` instead of `controlled_document_versions.id`
- `risk_register.py:234,265` — `RiskControlMapping`, `BowTieElement` reference `risk_controls.id` (OperationalRiskControl) instead of `enterprise_risk_controls.id`
**Evidence**: Confirmed table names: `document_versions` in `document.py:283`, `controlled_document_versions` in `document_control.py:146`, `risk_controls` in `risk.py`, `enterprise_risk_controls` in `risk_register.py`.
**Fix**: Correct FK target tables. Create Alembic migration with `op.drop_constraint` + `op.create_foreign_key`.
**Files**: `src/domain/models/document_control.py`, `src/domain/models/risk_register.py`, new Alembic migration
**Tests**: Migration up/down test; FK constraint violation test.
**Rollback**: Downgrade migration.

### AP-10: Unify transaction boundaries — remove service-level commits (P1)
**Finding**: Services call `await self.db.commit()` while `get_db` also commits. Creates split transaction boundaries.
**Evidence**: `src/domain/services/incident_service.py:102,185,227`, `src/domain/services/audit_service.py:375,434,511,556,644,672`, `src/domain/services/complaint_service.py:63,135`.
**Fix**: Replace `commit()` with `flush()` in all services. Let `get_db` (database.py:82) be the single commit point. Exception: AP-05 fix must happen first to correct the audit event ordering in ComplaintService.
**Files**: `src/domain/services/incident_service.py`, `audit_service.py`, `complaint_service.py`
**Tests**: Integration test confirming single commit per request; test rollback on exception.
**Rollback**: `git revert`

### AP-11: Standardize error responses — ~40 raw HTTPExceptions (P1)
**Finding**: `actions.py` has ~25 raw `HTTPException` details, `assessments.py` ~15, `feature_flags.py` 5, `employee_portal.py` ~10, `incidents.py` line 149 and 236 expose internal error details.
**Evidence**: `src/api/routes/actions.py:394-398` — `detail=f"For source_type '{src_type}'..."`. `incidents.py:236` — `detail=f"Error listing incidents: {type(e).__name__}: {str(e)[:200]}"`.
**Fix**: Replace all with `api_error(ErrorCode.*, msg)`. Remove internal error detail exposure.
**Files**: `src/api/routes/actions.py`, `assessments.py`, `feature_flags.py`, `employee_portal.py`, `incidents.py`
**Tests**: Error response shape assertion tests per endpoint.
**Rollback**: `git revert`

### AP-12: Migrate incident routes to use IncidentService (P1)
**Finding**: `IncidentService` has full CRUD methods but routes only use it for `create`. All other operations bypass the service.
**Evidence**: `src/api/routes/incidents.py:101` (get — direct query), `:176` (list — direct query), `:322` (update — direct query + commit), `:374` (delete — direct query + commit). Meanwhile `src/domain/services/incident_service.py` has `get_incident`, `list_incidents`, `update_incident`, `delete_incident`.
**Fix**: Wire routes to use IncidentService methods. Map domain exceptions to HTTPExceptions in route handlers.
**Files**: `src/api/routes/incidents.py`
**Tests**: Existing integration tests + new service unit tests.
**Rollback**: `git revert`

### AP-13: Move status transition logic to domain services (P1)
**Finding**: `_INCIDENT_TRANSITIONS`, `_RISK_TRANSITIONS`, `_COMPLAINT_TRANSITIONS` maps are defined in route files — untestable, duplicated business logic.
**Evidence**: `src/api/routes/incidents.py:22-46`, `src/api/routes/risks.py:49-63`, `src/api/routes/complaints.py` (similar pattern).
**Fix**: Move transition maps and validation functions to respective domain services. Routes call service method.
**Files**: `src/api/routes/incidents.py`, `risks.py`, `complaints.py`, `src/domain/services/incident_service.py`, `risk_service.py`, `complaint_service.py`
**Tests**: Unit tests for all valid/invalid transitions per entity type.
**Rollback**: `git revert`

### AP-14: Add tenant_id to ALL models (P1 — 3 batches)
**Finding**: 40+ models lack tenant_id. User decision: add to ALL.
**Evidence**: Missing from: `Role`, `AuditSection`, `AuditQuestion`, `AuditResponse`, `IncidentAction`, `ComplaintAction`, `OperationalRiskControl`, `RiskAssessment`, `DocumentChunk`, `DocumentAnnotation`, `DocumentVersion`, `IndexJob`, `DocumentSearchLog`, `PolicyVersion`, `Standard`, `Clause`, `Control`, `Dashboard`, `DashboardWidget`, `SavedReport`, `BenchmarkData`, `CostRecord`, `ROIInvestment`, `ControlledDocument`, `FeatureFlag`, all `ims_unification.py` models, all `document_control.py` models, all `iso27001.py` models, all `uvdb_achilles.py` models, all `planet_mark.py` models, `InvestigationTemplate`, `InvestigationAction`, `InvestigationComment`, `InvestigationRevisionEvent`, `InvestigationCustomerPack`, `EnterpriseRiskControl`, `RiskAppetiteStatement`, etc.

**Batch 1** (core child models): `IncidentAction`, `ComplaintAction`, `OperationalRiskControl`, `RiskAssessment`, `PolicyVersion`, `AuditSection`, `AuditQuestion`, `AuditResponse`, `DocumentChunk`, `DocumentAnnotation`, `DocumentVersion`
**Batch 2** (enterprise modules): All `document_control.py`, `ims_unification.py`, `iso27001.py` models
**Batch 3** (remaining): All `analytics.py`, `uvdb_achilles.py`, `planet_mark.py`, `investigation.py` child models, `Standard`, `Clause`, `Control`, `FeatureFlag`, `Role`, `EnterpriseRiskControl`, `RiskAppetiteStatement`

**Fix**: Add `tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)` to each model. Create Alembic migration with `DEFAULT 1` for existing rows. Add tenant filter to all queries.
**Files**: 30+ model files, 3 Alembic migrations, query updates in routes/services.
**Tests**: Multi-tenant isolation integration tests; migration up/down.
**Rollback**: Downgrade migration(s).

### AP-15: Unify enum definitions (P1)
**Finding**: 3 `DocumentType` enums, 3 `DocumentStatus` enums, 2 `RiskStatus` enums, `AssetType` name collision.
**Evidence**: `src/domain/models/document.py` (DocumentType: 10 values), `policy.py` (DocumentType: 10 values), `document_control.py` (DocumentType: 14 values). Similar for DocumentStatus.
**Decision**: User chose single canonical enum per concept.
**Fix**: Create `src/domain/models/enums.py` with canonical `DocumentType`, `DocumentStatus`, `RiskStatus`. Write Alembic migration to map existing values. Rename `iso27001.py:AssetType` to `ISO27001AssetType`.
**Files**: New `enums.py`, 6 model files, Alembic migration.
**Tests**: Enum mapping tests; migration test.
**Rollback**: Downgrade migration.

### AP-16: Harden CI gates (P1)
**Finding**: Multiple CI weaknesses:
- `mypy src/ ... || true` — type errors pass silently (`ci.yml:99`)
- `pytest tests/security/ || true` — security tests non-blocking (`security-scan.yml`)
- Coverage threshold mismatch: `pyproject.toml` says 35%, CI enforces 40%
- `quality-trend` uses hardcoded test counts instead of real values (`ci.yml:786-794`)
**Fix**: Remove `|| true` from mypy and security tests. Align `pyproject.toml` to 40%. Parse real test counts in quality-trend.
**Files**: `.github/workflows/ci.yml`, `.github/workflows/security-scan.yml`, `pyproject.toml`
**Tests**: CI pipeline passes green.
**Rollback**: Revert individual workflow changes.

### AP-17: Create ESLint configuration (P1)
**Finding**: No `.eslintrc.*` or `eslint.config.*` file exists. ESLint 8 without config runs with no rules — `npm run lint` passes but catches nothing.
**Evidence**: `ls frontend/.eslint*` and `ls frontend/eslint*` return empty. `frontend/package.json:14` runs `eslint src/ --max-warnings 0`.
**Decision**: User chose "investigate first." Investigation result: no config found anywhere (not in package.json, not as flat config). Config is required.
**Fix**: Create `frontend/.eslintrc.cjs` with `@typescript-eslint`, `react`, `react-hooks`, `jsx-a11y` plugins. Errors for type safety and a11y, warnings for style.
**Files**: `frontend/.eslintrc.cjs` (new)
**Tests**: `npm run lint` passes.
**Rollback**: Delete config file.

---

## Tier 3 — Quality & World-Class Enhancements (P2)
> These improve UX, performance, observability, and code quality to exceed 10/10.

### AP-18: Wire telemetry in main.py (P2)
**Finding**: `setup_telemetry()` exists but is never called. Telemetry is completely non-functional.
**Evidence**: `grep -rn "setup_telemetry" src/main.py` returns empty. Function defined at `src/infrastructure/monitoring/azure_monitor.py:87`.
**Fix**: Call `setup_telemetry(app)` in the FastAPI lifespan or startup event in `src/main.py`. Depends on AP-06 (config attributes).
**Files**: `src/main.py`
**Tests**: Integration test verifying traces are emitted.
**Rollback**: `git revert`

### AP-19: Wire offline queue for form submissions (P2)
**Finding**: `idb` installed, `syncService.ts` has `queueForSync` function, but it's never called.
**Evidence**: `frontend/src/lib/syncService.ts` — `queueForSync` defined but zero references. `startAutoSync` called from `App.tsx:167` but processes empty queue.
**Decision**: User chose "wire it up properly."
**Fix**: Call `queueForSync` from incident, complaint, and portal form submissions when `navigator.onLine === false`. Add UI indicator for pending sync items. Ensure `flushPending` handles conflicts.
**Files**: `frontend/src/lib/syncService.ts`, `frontend/src/pages/Incidents.tsx`, `Complaints.tsx`, portal form pages, new `OfflineSyncIndicator` component.
**Tests**: Vitest mock testing offline queue behavior.
**Rollback**: `git revert`

### AP-20: Implement Celery background tasks (P2)
**Finding**: Celery tasks exist (11 files, 662 lines) but can't start because config attributes are missing.
**Evidence**: `src/infrastructure/tasks/celery_app.py:8-9` references `settings.celery_broker_url`, `settings.celery_result_backend`. Tasks defined: email, notifications, cleanup, competency checks, DLQ replay, monitoring, reports, SMS.
**Decision**: User chose "implement basic tasks."
**Fix**: Depends on AP-06 (config attributes). After config is added, verify all existing tasks work. Add worker startup to deployment scripts. Add Celery health check to monitoring.
**Files**: Deployment scripts, monitoring config.
**Tests**: Task unit tests with mocked broker.
**Rollback**: Remove Celery from deployment.

### AP-21: Add pagination to unpaginated endpoints (P2)
**Finding**: `users/search/` (hardcoded limit 20), `feature-flags/` (returns all), `copilot/sessions` (limit only, no offset).
**Evidence**: `src/api/routes/users.py`, `feature_flags.py`, `copilot.py`.
**Fix**: Add `skip`/`limit` query params with defaults. Backward compatible — existing calls without params get default behavior.
**Files**: `src/api/routes/users.py`, `feature_flags.py`, `copilot.py`
**Tests**: Pagination integration test.
**Rollback**: `git revert`

### AP-22: Optimize portal my-reports query (P2)
**Finding**: Portal `get_my_reports` runs 4 separate queries, merges in Python, paginates in memory.
**Evidence**: `src/api/routes/employee_portal.py:534-576`.
**Fix**: Use SQL UNION + LIMIT/OFFSET for server-side pagination.
**Files**: `src/api/routes/employee_portal.py`
**Tests**: Performance test with large dataset.
**Rollback**: `git revert`

### AP-23: FE: Separate Complaints error states (P2)
**Finding**: Single `formError` state variable used for both load failures and form validation failures.
**Evidence**: `frontend/src/pages/Complaints.tsx`.
**Fix**: Add separate `loadError` state. Display differently for each error type.
**Files**: `frontend/src/pages/Complaints.tsx`
**Tests**: Vitest: simulate load error vs form error independently.
**Rollback**: `git revert`

### AP-24: FE: Console.error gating + a11y fixes (P2)
**Finding**: 4 files have ungated `console.error`. Login password label missing `htmlFor`. Audit template select missing label. View toggle missing `aria-pressed`.
**Evidence**: `Dashboard.tsx:334`, `Audits.tsx:103,215`, `Login.tsx:104,111`, `ForgotPassword.tsx:38`. `Login.tsx:281` suppresses a11y lint.
**Fix**: Guard console statements with `import.meta.env.DEV`. Fix label associations. Add `aria-pressed`.
**Files**: `Dashboard.tsx`, `Audits.tsx`, `Login.tsx`, `ForgotPassword.tsx`
**Tests**: `jest-axe` tests on affected components.
**Rollback**: `git revert`

### AP-25: FE: NotFound page design tokens (P2)
**Finding**: Hardcoded `text-gray-300`, `text-gray-900`, `bg-blue-600` instead of design system tokens.
**Evidence**: `frontend/src/pages/NotFound.tsx`.
**Fix**: Replace with `text-muted-foreground`, `text-foreground`, `bg-primary`, etc.
**Files**: `frontend/src/pages/NotFound.tsx`
**Tests**: Visual snapshot test.
**Rollback**: `git revert`

### AP-26: FE: Replace window.prompt with Dialog (P2)
**Finding**: `window.prompt()` used for completion notes — blocks main thread, poor UX.
**Evidence**: `frontend/src/pages/IncidentDetail.tsx:291`.
**Fix**: Replace with custom Dialog component matching existing pattern.
**Files**: `frontend/src/pages/IncidentDetail.tsx`
**Tests**: Vitest interaction test.
**Rollback**: `git revert`

### AP-27: FE: Fix Badge `as any` casts (P2)
**Finding**: Multiple `variant as any` casts for Badge variants across list pages.
**Evidence**: `frontend/src/pages/Incidents.tsx:252` and similar.
**Fix**: Extend Badge component variant type union to include all status values.
**Files**: `frontend/src/components/ui/Badge.tsx`, page files.
**Tests**: TypeScript compilation (zero errors).
**Rollback**: `git revert`

### AP-28: Wire circuit breaker to external calls (P2)
**Finding**: `CircuitBreaker` and `retry_with_backoff` defined but never used.
**Evidence**: `src/infrastructure/resilience/circuit_breaker.py` — classes defined. No imports found in services.
**Fix**: Apply `@retry_with_backoff` to AI service calls, email service, Azure blob operations.
**Files**: `src/domain/services/gemini_ai_service.py`, `email_service.py`, Azure storage calls.
**Tests**: Mock failure integration tests.
**Rollback**: `git revert`

### AP-29: Add `index=True` to SoftDeleteMixin.deleted_at (P2)
**Finding**: `deleted_at` queries filter `WHERE deleted_at IS NULL` without index support.
**Evidence**: `src/domain/models/base.py` — `SoftDeleteMixin` has `deleted_at` without `index=True`.
**Fix**: Add `index=True`. Create Alembic migration.
**Files**: `src/domain/models/base.py`, Alembic migration.
**Tests**: Migration test.
**Rollback**: Downgrade migration.

### AP-30: Add Prettier and format frontend (P2)
**Finding**: No code formatter for frontend. Inconsistent formatting.
**Decision**: User chose "add and format everything in one PR."
**Fix**: Add `.prettierrc` with sensible defaults. Run `npx prettier --write src/`. Add CI check.
**Files**: `frontend/.prettierrc` (new), all `frontend/src/` files.
**Tests**: `npx prettier --check src/` passes.
**Rollback**: `git revert`

### AP-31: Consolidate import paths (P2)
**Finding**: `src/services/` re-exports from `src/domain/services/`. Mixed import paths.
**Evidence**: `src/services/reference_number.py` — re-export shim.
**Fix**: Update all imports to use `src.domain.services.*` directly. Remove `src/services/` shim.
**Files**: Various route files, `src/services/` directory.
**Tests**: Existing tests pass.
**Rollback**: `git revert`

### AP-32: Add cascade + missing indexes (P2)
**Finding**: `DocumentApprovalWorkflow` FK missing `ondelete`. `AuditResponse.question_id` missing index. `AuditTrailMixin` columns missing indexes.
**Evidence**: `src/domain/models/document_control.py` — `workflow_id` FK without `ondelete`. Various models.
**Fix**: Add `ondelete="CASCADE"` where appropriate. Add indexes. Alembic migration.
**Files**: Model files, Alembic migration.
**Tests**: Migration test.
**Rollback**: Downgrade migration.

### AP-33: Health route optional auth fix (P2)
**Finding**: `current_user: CurrentUser = None` doesn't make auth optional.
**Evidence**: `src/api/routes/health.py:84`.
**Fix**: Use `OptionalCurrentUser` alias or remove the parameter.
**Files**: `src/api/routes/health.py`
**Tests**: Unit test — unauthenticated request succeeds.
**Rollback**: `git revert`

### AP-34: Document CSRF decision (P3)
**Fix**: Create ADR documenting why CSRF is not required (JWT-in-header for SPA).
**Files**: `docs/adr/` (new ADR)

### AP-35: Fix analytics report_type parameter (P3)
**Finding**: POST body parameter handled as positional argument.
**Evidence**: `src/api/routes/analytics.py:408-414`.
**Fix**: Use Pydantic request model.
**Files**: `src/api/routes/analytics.py`

---

## Execution Order & Dependencies

```
Phase 1 (Week 1) — Zero-downtime critical fixes:
  AP-01 ─── No deps ─── Admin config paths (FE only)
  AP-02 ─── No deps ─── AI await fix (BE only)
  AP-03 ─── No deps ─── Pydantic syntax (BE only)
  AP-04 ─── No deps ─── Loader2 import (FE only)
  AP-06 ─── No deps ─── Config attributes (BE only)
  AP-07 ─── No deps ─── Branch protection (DevOps)
  AP-08 ─── No deps ─── datetime.utcnow (BE models)

Phase 2 (Week 1-2) — Transaction + service layer:
  AP-05 ─── No deps ─── ComplaintService audit fix
  AP-10 ─── After AP-05 ─── Unify all service commits
  AP-12 ─── After AP-10 ─── Incident routes → service
  AP-13 ─── After AP-12 ─── Status transitions → services

Phase 3 (Week 2-3) — Data integrity:
  AP-09 ─── No deps ─── FK corrections + migration
  AP-11 ─── No deps ─── Error response standardization
  AP-14 ─── After AP-09 ─── tenant_id (3 batch migrations)
  AP-15 ─── After AP-14 ─── Enum unification + migration

Phase 4 (Week 3-4) — CI + quality:
  AP-16 ─── No deps ─── CI gates
  AP-17 ─── No deps ─── ESLint config
  AP-18 ─── After AP-06 ─── Wire telemetry
  AP-20 ─── After AP-06 ─── Celery tasks

Phase 5 (Week 4-5) — Polish + world-class:
  AP-19, AP-21–AP-35 ─── Various deps ─── UX, perf, a11y, observability
  AP-30 ─── LAST ─── Prettier (full reformat, must be after all other FE changes)
```

---

## Release Gates

| Gate | Check | Fail Action |
|------|-------|-------------|
| A | `tsc --noEmit` zero errors + `eslint --max-warnings 0` + `black --check` + `isort --check` + `flake8` + `mypy` (blocking) | Block merge |
| B | pytest ≥ 40% coverage, vitest pass | Block merge |
| C | Playwright CUJ smoke (5 journeys) ≥ 90% baseline | Block deploy |
| D | Canary: 5%→25%→50%→100% traffic; p99 < 500ms; error rate < 0.5%; availability ≥ 99.9% | Auto-rollback |
| E | UAT sign-off: 0 S1, 0 S2 for GO | Block production |
| F | Post-deploy: health + SHA match + security headers + rate limiting | Auto-rollback |
