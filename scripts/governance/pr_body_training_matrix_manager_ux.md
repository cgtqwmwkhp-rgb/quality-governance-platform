# Change Ledger (CL-TRAINING-MATRIX-MANAGER-UX)

## 1) Summary
- **Feature / Change name:** Training Matrix manager UX — horizon-first board, interactive Admin frequency matrix, email notify
- **User goal (1–2 lines):** Give managers a due-date-horizon view of training gaps (Overdue / 30 / 60 / 180 days) with group/course/individual/module breakdowns, a role compliance bar, rotating grounded insights, CSV export, and one-click Atlas-gap emails. Give admins an interactive dept×course frequency grid instead of a one-off "Load April 2024" seed action.
- **In scope:** Manager gap board rewrite (horizon-first); Admin requirements grid (BOARD_ROLES × course); `POST /requirements/matrix` bulk upsert/deactivate; `POST /notify` email; `last_training_notified_at` tracking; removal of the Expiry-without-Passed QA banner from the manager board; My training progress polish; unit/vitest coverage
- **Out of scope:** Changing due-date math (still Passed + frequency_years); Atlas API sync; removing the seed API (kept for ops, just hidden from Admin UI); role_key-based custom requirement rules (grid is department × BOARD_ROLES only — pre-existing role_key rules are untouched but not editable in the new grid)
- **Feature flag / kill switch:** N/A — additive UI + additive endpoints; old `/requirements` CRUD endpoints remain for any external/ops use

## 2) Impact Map (what changed)
- **Frontend:**
  - `trainingMatrix/trainingMatrixBoardHelpers.ts` (new) — horizon classification, role resolution, role stats, rotating briefings, group/course/person/module aggregation, CSV rows, my-training summary
  - `trainingMatrix/TrainingMatrixPanels.tsx` — full rewrite of `TrainingMatrixGapBoard` (horizon pills, role % bar, rotating briefing, By group/course/individual/module views, top courses, export CSV, email selected/filtered) and `TrainingMatrixAdminPanel` (interactive frequency grid replacing "Load April 2024" + manual add-rule form; upload/name-map sections unchanged); `TrainingMatrixMyTraining` polished with progress counts + next-due
  - `api/trainingMatrixClient.ts` — `upsertRequirementsMatrix`, `notify`, `last_training_notified_at` field on compliance rows
  - `api/client.ts` — re-exports new client types
  - `pages/workforce/__tests__/Training.shell.test.tsx`, `WfGate.test.tsx` — mocks updated for the new/removed API surface
- **Backend:**
  - `src/domain/services/training_matrix_board.py` (new) — `BOARD_ROLES`, `resolve_board_role`, `horizon_for_row`, `build_status_briefings` (pure, unit-tested)
  - `src/api/routes/training_matrix.py` — `POST /requirements/matrix` (bulk dept×course upsert/deactivate, admin-only), `POST /notify` (email non-OK modules to mapped Users, manager/admin), `last_training_notified_at` on compliance rows
  - `src/api/schemas/training_matrix.py` — matrix/notify request/response schemas; `last_training_notified_at` on `TrainingMatrixComplianceRow`
  - `src/domain/models/training_matrix.py` — `TrainingMatrixPerson.last_training_notified_at`
  - `src/domain/services/email_service.py` — `send_training_gap_notification` (new branded HTML template method, follows existing `send_*` conventions)
- **APIs:** `POST /api/v1/training-matrix/requirements/matrix`, `POST /api/v1/training-matrix/notify`
- **Schemas/contracts:** New request/response models above; additive field on existing compliance row response
- **Database:** New migration `20260801_train_notify` adds nullable `training_matrix_people.last_training_notified_at` (DateTime, timezone=True)
- **Workflows/jobs/queues:** None (notify is synchronous, per-request; relies on existing `email_service`/SMTP config)
- **Config/env/flags:** None new (reuses existing SMTP_* env vars via `EmailService`)
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoints + additive response field; existing `/requirements` CRUD, `/requirements/seed`, `/imports*`, `/compliance`, `/me` endpoints untouched. Old `createRequirement`/`updateRequirement`/`deleteRequirement`/`seedRequirements` client methods remain in `trainingMatrixClient.ts` for ops/API use, just no longer called from the Admin UI.
- **Tolerant reader / strict writer applied?** Matrix upsert only touches rows keyed by `(match_department ∈ BOARD_ROLES, course_key)` with `match_role_key IS NULL` — pre-existing custom `match_role_key` rules or non-standard department strings are never touched by the grid.
- **Breaking changes:** None. Removing the QA banner and "Load April 2024 matrix" button changes UI only; the seed API endpoint (`POST /requirements/seed`) is unchanged and still callable.
- **Migration plan:** Deploy → run Alembic migration (adds nullable column, no backfill needed) → new UI is live immediately
- **Rollback strategy (DB):** `alembic downgrade` drops `last_training_notified_at` (nullable, no data loss risk); UI rollback is a plain revert

## 4) Acceptance Criteria (AC)
- [x] AC-01: Manager gap board loads all compliance rows once and classifies each row into Overdue / Next 30 / 60 / 180 / All open via `horizon_for_row`/`horizonForRow` (BE + FE parity, unit-tested both sides)
- [x] AC-02: Role % bar shows Overall + Engineer/Workshop/Office/Management, computed as % of people with every required course `compliant`
- [x] AC-03: Rotating status banner shows up to 5 grounded insights (highest-risk module, new-starter heuristic, weakest/strongest role, due-in-30 pulse), auto-rotates every 8s, and has a manual Next button
- [x] AC-04: By group / By course / By individual / By module (role-scoped) views all read from the same filtered row set
- [x] AC-05: CSV export downloads the currently filtered rows with plain status labels (Overdue / Due in Nd / OK until date)
- [x] AC-06: Email selected / Email everyone in filter call `POST /notify`, which emails each person's non-OK modules + Atlas link and stamps `last_training_notified_at`
- [x] AC-07: Admin interactive frequency grid (courses × BOARD_ROLES) reads existing requirements, edits are local until Save, Save confirms the change count and calls `POST /requirements/matrix`
- [x] AC-08: No "Load April 2024 matrix" (or manual add-rule) control remains in the Admin UI; `POST /requirements/seed` is untouched for ops use
- [x] AC-09: Expiry-without-Passed QA banner is removed from the manager board entirely
- [x] AC-10: My training shows progress counts (`X/Y modules OK`) and the next-due module
- [x] AC-11: Due-date math unchanged — still `add_years(passed_on, frequency_years)`, verified by existing `training_matrix_compliance` tests (untouched)

## 5) Testing Evidence (link to runs)
- [x] Lint — `black` + `isort` on all changed Python (clean); `eslint --max-warnings 0` on all changed/added TS (clean)
- [x] Typecheck — `tsc --noEmit` clean
- [ ] Build — CI after open
- [x] Unit tests — `pytest tests/unit/test_training_matrix_board.py` (12 passed); `pytest tests/unit/test_training_matrix_parser.py tests/unit/test_training_matrix_requirement_seed.py` (unaffected, 9 passed)
- [x] Frontend unit tests — `vitest run src/pages/workforce/trainingMatrix/trainingMatrixBoardHelpers.test.ts` (20 passed); `vitest run src/pages/workforce` (88 passed, includes updated `Training.shell.test.tsx` + `WfGate.test.tsx` mocks)
- [ ] Integration tests — N/A (route logic covered by existing compliance-row tests + new pure-helper unit tests; DB-backed route test left for CI/staging)
- [ ] Contract tests — N/A
- [ ] E2E Smoke — Manager board + Admin grid + notify on staging after merge

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Manager → Training → gap board loads, filters by horizon pill, switches views, exports CSV of the filtered set
- [x] CUJ-02: Manager selects a horizon + view, selects people in "By individual", clicks "Email selected" → sees sent/skipped/failed toast
- [x] CUJ-03: Admin → Training → Admin → edits several matrix cells → Save → confirm dialog shows change count → grid reloads from saved state
- [x] CUJ-04: Employee → Training → My training shows progress counts + next due module, unchanged Atlas CTA behavior
- [x] CUJ-05: No QA banner, no "Load April 2024 matrix" button anywhere in the manager or admin UI

## 7) Observability & Ops
- **Logs:** Notify failures log through existing `EmailService`/`aiosmtplib` retry+logging path; no new log channels
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** `POST /requirements/seed` remains available for ops (e.g. via API client/curl) to bootstrap a tenant's matrix before admins start using the interactive grid; no UI entry point anymore

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Run Alembic migration; upload an Atlas CSV; edit a few matrix cells and Save; confirm gap board horizon counts move; select a mapped person and send a notify email (or confirm skip when SMTP disabled); confirm My training progress renders
- **Canary plan:** N/A (internal admin/manager tool, no public traffic split)
- **Prod post-deploy checks:** Same staging checks; spot-check that `last_training_notified_at` populates after a successful send

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Matrix grid Save corrupts requirement rows in a way that misclassifies compliance broadly, or notify sends incorrect/duplicate emails
- **Rollback steps:** Revert the PR (UI + routes); DB rollback is `alembic downgrade` for the new column only — no destructive schema change to reverse for the matrix upsert (it writes normal `training_matrix_requirements` rows, same table as before)
- **Owner:** Platform / Workforce Training track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A at open
- Canary evidence (if applicable): N/A

## Residuals (explicitly not in this PR)
- Detailed "who moves into/out of overdue" preview before saving the matrix (approximated with a confirm-dialog change count instead, per scope)
- Role_key-based custom requirement rules are not represented in the new grid (still editable only via the underlying API)
- Async/queued notify (currently synchronous per request; fine at current tenant/person volumes)
- Bulk "email everyone overdue across all filters" (current scope is "selected" or "everyone in the current filter")

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Design locked (horizon-first board; dept×BOARD_ROLES grid; additive notify/matrix endpoints; no due-date math changes)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + rollback ready
