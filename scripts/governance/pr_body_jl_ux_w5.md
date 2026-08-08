# Change Ledger (CL-JL-UX-W5-FIELD-CHANGE)

## 1) Summary
- **Feature / Change name:** JL-UX-W5 (Field & change) — **portal nested-cycle read** (#8) · **cycle baseline snapshot + diff** (#9)
- **User goal (1–2 lines):** A field user can open a nested job cycle read-only from the portal, and a governance lead can freeze a pack's axes + nest edges as a snapshot and see a structured diff against the live tip — without ever treating the snapshot as an editable fork.
- **In scope:** Alembic `job_type_baselines` + RLS; `JobTypeBaseline` model; snapshot/diff module; service create/list/get/diff + portal nested-cycle DTO; staff baselines API; portal `/portal/job-lifecycle` GET-only routes; FE portal Job cycles page; composer baseline create/list/view banner + diff summary; BE + FE tests; this Change Ledger
- **Out of scope:** Baseline restore/apply onto live; baseline delete; new feature flags; Azure settings; forking JobTypes; dual nest FK on lanes; W6+
- **Feature flag / kill switch:** Reuses existing `job_lifecycle` / `job_cell_links` (already ON in STG/PROD via Azure). **No new flags, no Azure settings touched.** Portal nested-cycle graph follows `job_cell_links`; with that flag closed nest links/graph are omitted rather than inventing a second SSOT.

## Conveyor / merge gate
- Serial programme wave **W5** of JL-UX W1–W5. Base is `origin/main` at the W4 tip `90dc61c5` (PR #1664).
- Do **not** merge from this agent unless directed. Do **not** mark DONE/LIVE from this PR alone.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `PortalJobCycles.tsx` (read-only nest drill + matrix); `Portal.tsx` tile; `App.tsx` routes; `JobLifecycle.tsx` baseline create/list/view banner + diff summary; `jobLifecycleHelpers.ts` W5 helpers; `jobLifecycleClient.ts` baselines + portal calls; Vitest helpers
- **Backend (handlers/services):** **New** `job_lifecycle_baseline.py` (pure snapshot/diff); `JobLifecycleService` create/list/get/diff/capture + `portal_nested_cycle`; **new** `portal_job_lifecycle.py` GET-only router; baselines endpoints on `job_lifecycle.py`
- **APIs (endpoints changed/added):** **Added** `POST/GET /job-lifecycle/job-types/{id}/baselines`, `GET …/baselines/{id}`, `GET …/baselines/{id}/diff`; **Added** `GET /portal/job-lifecycle/job-types`, `GET …/job-types/{id}/nested-cycle`, `GET …/cycle-graph`
- **Schemas/contracts:** Baseline create/list/response/diff; portal nested-cycle DTO (`read_only` / `can_author=false`); OpenAPI additive
- **Database:** One revision `20261023_job_type_baselines` (`down_revision = 20261022_job_cell_req_ev`) — `job_type_baselines` with tenant RLS; registered in `RLS_TABLES` / `HARDENING_MIGRATIONS`
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive table + endpoints. Live `job_*` tables remain SoT for edit; baselines never redirect writes. Portal mounts no write methods.
- **Tolerant reader / strict writer applied?** Yes. Missing nest targets are omitted from snapshots; portal strips non-`job_cycle` link kinds; viewing a baseline returns an explicit banner DTO field.
- **Breaking changes:** None
- **Migration plan:** `alembic upgrade head` → `20261023_job_type_baselines`
- **Rollback strategy (DB):** `downgrade` drops `job_type_baselines` (loses snapshot artefacts only; live packs untouched)

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Field access to nested cycles | Admin composer only | Portal GET nested-cycle DTO under `job:read` |
| Portal write exposure | N/A | No POST/PATCH/PUT/DELETE on portal JL router — asserted by test |
| Approved-vs-live change view | Not expressible | Baseline snapshot + structured diff (added/removed/changed) |
| Baseline vs live edit confusion | Risk of forking | Banner + `edit_targets_live=true`; edit always live tip |
| Nest SSOT | `job_cycle` links | Unchanged — lane chip stays derived; baselines copy nest edges as JSON |
| Alembic heads | 1 (`20261022_job_cell_req_ev`) | 1 (`20261023_job_type_baselines`) — serial |
| Feature flags | Unchanged ON in Azure | Unchanged; no new flags |
| RLS coverage | JL tables through links | `job_type_baselines` hardened + registered |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Exactly one new revision `20261023_job_type_baselines` on `20261022_job_cell_req_ev`, and it is the only Alembic head
- [x] AC-02: `job_type_baselines` has tenant_id, job_type_id FK, created_by, optional label/note, snapshot JSON/JSONB, timestamps; RLS FORCE + NULLIF predicate
- [x] AC-03: Create baseline freezes axes + nest edges; live tables remain SoT (snapshot unchanged after live edits)
- [x] AC-04: Diff returns structured added/removed/changed keyed by JL codes
- [x] AC-05: GET baseline includes viewing banner / `edit_targets_live`
- [x] AC-06: Portal nested-cycle returns nest-aware DTO with `read_only=true` and `can_author=false`
- [x] AC-07: Portal router mounts GET only under `job:read` (write denied by absence)
- [x] AC-08: FE portal page drills nested cycles without author chrome; composer can create/list/view baselines with banner
- [x] AC-09: No new feature flags; no Azure settings; lane nest chip remains derived (no dual FK)
- [x] AC-10: Unit tests cover snapshot/diff + portal read permission contract

## 5) Testing Evidence (link to runs)
- [x] Unit (BE) — `tests/unit/test_job_lifecycle_ux_w5.py` **19 passed**; W4 head assertion updated for serial W5; RLS registration asserted
- [x] Unit (FE) — `jobLifecycleW5Helpers.test.ts` **5 passed**
- [x] Format — black + isort applied on touched Python
- [ ] Lint / full suite — CI on PR
- [ ] E2E Smoke — staging bake after tip LIVE

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Create baseline on a pack with a nest link → snapshot stores nest target code → live lane rename → diff shows changed lane and snapshot still holds the old name
- [x] CUJ-02: Portal nested-cycle for a parent pack returns nest links only (external/app stripped) and `can_author=false`
- [x] CUJ-03: Portal router inspection — methods == GET and permission == `job:read` only

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** Viewing a baseline is intentional; edits still PATCH the live tip. Portal 404 when `job_lifecycle` is closed is expected.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** `alembic upgrade head` → `20261023_job_type_baselines`; tip SHA match; flags remain ON; portal Job cycles opens; baseline create/diff on composer
- **Canary plan:** N/A — additive table + read/author endpoints
- **Prod post-deploy checks:** PROD tip SHA = MAIN; ACA image contains tip; health 200; `alembic current` = `20261023_job_type_baselines`
- **Rollback trigger:** Baseline create failing in prod; portal nested-cycle 500s on packs with nests

## 9) Rollback Plan (Mandatory)
- **Rollback steps:** Revert squash / redeploy prior image. Optionally `alembic downgrade -1` drops `job_type_baselines` only.
- **Rollback owner:** Platform engineering (JL-UX programme)
- **Data repair needed?** No — live packs untouched; only snapshot rows are lost on downgrade.

## 10) Evidence Pack
- Local BE W5 unit: 19 passed
- Local FE W5 helpers: 5 passed
- Alembic: `20261023_job_type_baselines` on `20261022_job_cell_req_ev`; single head
- CI URL: (fill after PR)
- STG/PROD tip verify: (post-merge conveyor — not claimed here)

## Gate Checklist
- [x] Gate 0 — Change Ledger complete
- [x] Gate 1 — Scope held (W5 only, no new flags, no Azure changes)
- [x] Gate 2 — Compatibility additive; one serial migration; single head
- [x] Gate 3 — AC + CUJ covered
- [ ] Gate 4 — CI green on PR
- [ ] Gate 5 — STG then PROD tip LIVE + health
