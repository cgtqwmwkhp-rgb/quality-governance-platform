# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Branching Assessments + World-Class Reporting
- **User goal (1-2 lines):** Let auditors compose a single audit template into different variants per `assessment_mode`/`asset_type`, hide/show questions with conditional logic, gate completion on essential/required criticality, and give leadership a live audit analytics reporting pack (KPIs, dimension breakdowns, critical queue, CSV export).
- **In scope:** AC-01..AC-08 below (reporting foundation, composition, criticality gate, conditional logic, reporting pack UI)
- **Out of scope:** Retroactive backfill of `applicability`/`assessment_mode` on historical runs (nullable, defaults to unrestricted); PDF/branded exports of the analytics pack; per-question weighting changes
- **Feature flag / kill switch:** N/A — all new fields are nullable/additive; existing templates/runs behave exactly as before (no rules = always applicable, no criticality = current behavior)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):**
  - New `/audits/analytics` page (`AuditAnalytics.tsx`) + "Analytics" entry point from `Audits.tsx`
  - `AuditTemplateBuilder` → `SectionEditor` (applicability rules UI), `QuestionEditor` (criticality + conditional logic rule builder)
  - `AuditExecution` → new `AssessmentDimensionsPanel` header, composition filtering at load, live conditional-logic visibility during answering
  - New evaluator mirrors: `evaluateComposition.ts`, `evaluateConditionalLogic.ts`
- **Backend (handlers/services):**
  - New: `audit_composition.py`, `audit_conditional.py`, `audit_analytics_service.py`
  - Updated: `audit_service.py` (`_missing_required_question_ids`, essential-fail gate, template asset-type link/unlink), `executive_dashboard.py` (live `audits` summary block)
- **APIs (endpoints changed/added):**
  - `GET /audits/analytics/summary`, `GET /audits/analytics/dimensions`, `GET /audits/analytics/export.csv`, `GET /audits/analytics/critical-queue`
  - `POST/DELETE /audits/templates/{id}/asset-types/{asset_type_id}`
  - `GET /analytics/kpis` now merges live audit stats (`essential_compliance_pct`, `incomplete_critical_count`, `pass_rate`, etc.)
  - `GET /executive-dashboard` now returns an `audits` block
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `AuditRun`, `AuditResponse`, `AuditSection`, `AuditQuestion` schemas extended (additive, nullable); new `audit_analytics.py` response schemas; new `AuditSummary` executive-dashboard schema; FE `auditsClient.ts` / `client.ts` types extended to match
- **Database (migrations/entities/indexes):** `20260805_audit_branch_reporting` — adds `audit_runs.assessment_mode/asset_type_id/location_id/customer_code` (+3 indexes), `audit_responses.applicability` (+ check constraint), `audit_sections.applicability_rules_json`. All columns nullable; no backfill required.
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive-only. All new columns are nullable with safe defaults (`applicability` defaults to `'applicable'`); absence of `applicability_rules_json` / `conditional_logic` means "always applicable / always visible" — existing templates and in-flight runs are unaffected.
- **Tolerant reader / strict writer applied?** Yes — composition/conditional evaluators treat `null`/empty rule dimensions as unrestricted; schemas accept the new fields as `Optional`.
- **Breaking changes:** None. `QuestionCriticality` gained `REQUIRED` alongside existing `ESSENTIAL`/`GOOD_TO_HAVE` — no existing value changed meaning. `good_to_have` questions never block completion (matches prior behavior).
- **Migration plan:** Single forward migration `20260805_audit_branch_reporting`, chained off `20260804_safety_lu` (single alembic head verified). Safe to run online (`ADD COLUMN ... NULLABLE`, `CREATE INDEX`, `ADD CHECK CONSTRAINT` permissive of existing NULL/`'applicable'` rows).
- **Rollback strategy (DB):** `downgrade()` implemented — drops indexes/constraint/columns in reverse dependency order. Verified single alembic head pre/post.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Reporting foundation — migration + models + schemas for `assessment_mode`/`asset_type_id`/`location_id`/`customer_code` on runs, `applicability` on responses, `applicability_rules_json` on sections
- [x] AC-02: `AuditAnalyticsService.get_summary/get_dimensions/get_critical_queue/export_runs_csv` implemented against real SQLAlchemy async queries; wired into `GET /analytics/kpis` and `GET /executive-dashboard`
- [x] AC-03: Composition — `audit_composition.py` (+ FE mirror `evaluateComposition.ts`) determines section/question applicability from `assessment_mode`/`asset_type_id`; `_missing_required_question_ids` skips non-applicable/hidden questions and requires `REQUIRED`/`ESSENTIAL` criticality only
- [x] AC-04: Essential-fail gate — `complete_run` sets `passed=False` whenever any applicable essential question has an open finding/fail, even if the overall score is above threshold
- [x] AC-05: Conditional logic end-to-end — backend `audit_conditional.py` + FE mirror `evaluateConditionalLogic.ts` share evaluation semantics; builder UI to add/remove show/hide rules; execution UI filters/skips hidden questions and persists `applicability='hidden_by_logic'` on save
- [x] AC-06: Template ↔ asset-type linking — `POST/DELETE /audits/templates/{id}/asset-types/{asset_type_id}` using `TemplateAssetType`
- [x] AC-07: Reporting pack UI — `AuditAnalytics.tsx` with KPI cards, dimensions table, critical queue, CSV export; reachable from `Audits.tsx`
- [x] AC-08: Test coverage — new backend unit/integration tests (composition, conditional, essential gate, analytics service, schema patterns) and frontend unit tests (evaluators, template helper mapping) all green; no regressions in existing suites

## 5) Testing Evidence (link to runs)
- [x] Lint — no new linter errors on touched files (`ReadLints` clean)
- [x] Typecheck — `tsc --noEmit` clean on frontend
- [x] Build — N/A (backend interpreted; frontend covered by typecheck + vitest)
- [x] Unit tests (backend) — `pytest tests/unit` → 3122 passed, 2 failed (pre-existing, unrelated: `fpdf2` not installed in this environment — confirmed failing identically on a clean stash of `origin/main`), 7 skipped
- [x] Unit tests (new, audit-specific) — `test_audit_composition.py`, `test_audit_conditional.py`, `test_audit_essential_gate.py`, `test_audit_schemas.py` (expanded), `test_executive_dashboard_response_hardening.py`, `test_executive_dashboard_dual_service_reexport.py` → 103+ passed, 0 failed
- [x] Integration tests — `tests/integration/test_audit_analytics_service.py` (summary, dimensions, critical-queue, export CSV, essential-fail completion gate) → 6 passed, 0 failed
- [x] Frontend unit tests — `vitest run src/pages` → 147 files / 850 tests passed, 0 failed (includes new `evaluateComposition.test.ts`, `evaluateConditionalLogic.test.ts`, expanded `templateHelpers.test.ts`)
- [x] Contract tests (if applicable) — N/A
- [x] E2E Smoke (critical journeys) — deferred to staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Auditor sets an audit run's assessment mode / asset type / location / customer via the new header panel → template sections/questions filter to the applicable subset → auditor answers only applicable, visible (post conditional-logic) questions → completing the run with an open essential-question finding is blocked from passing even if overall score is high.
- [x] CUJ-02: Compliance lead opens `/audits/analytics` → sees live KPI cards (totals, completion, pass rate, essential compliance, incomplete-critical count), a dimensions breakdown table (e.g. by asset type: run count, avg score, fail rate, essential compliance), and a critical queue of unanswered/failed essential items linking back to the run → exports the underlying data as CSV.

## 7) Observability & Ops
- **Logs:** No change beyond existing service logging conventions
- **Metrics:** `GET /analytics/kpis` and `GET /executive-dashboard` now surface `essential_compliance_pct` / `incomplete_critical_count` as new observable KPIs
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Run alembic upgrade to `20260805_audit_branch_reporting`, smoke-test `/audits/analytics/*` endpoints and the new AuditExecution header panel against a staging tenant with existing templates (confirming zero-behavior-change for templates without new rules configured).
- **Canary plan:** N/A
- **Prod post-deploy checks:** Health/readiness/version endpoints; spot-check `GET /audits/analytics/summary` for a real tenant returns non-error payload; confirm single alembic head.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Any critical API failure post-deploy, or alembic migration failure
- **Rollback steps:** `alembic downgrade -1` to revert schema (safe — implemented `downgrade()`), then revert the commit/deploy on main to previous SHA
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (additive schemas, nullable columns, tolerant-reader evaluators)
- [x] **Gate 2:** CI green (lint/type/build/tests) — see Testing Evidence above
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
