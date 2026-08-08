# Change Ledger (CL-JL-UX-W1-STABILIZE)

## 1) Summary
- **Feature / Change name:** JL-UX-W1 — Stabilize Job Lifecycle composer (429 storm · job cycle picker · nav collapse · resizable panels · permission health)
- **User goal (1–2 lines):** Operators can use Job Lifecycle without 429 storms, pick/create a Job cycle clearly, collapse desktop nav, resize composer panels, and see when `job:read`/`job:author` grants are missing even when flags are ON.
- **In scope:** FE-only fix for Step links refetch storm; Job cycle picker/create copy; Layout desktop collapse via existing preferences store; resizable three-panel composer; lazy library tray paging; permission-health banner (#10); Vitest coverage
- **Out of scope:** Nesting (`job_cycle` kind), PDCA, freshness/obsolete, map/trail, clone, baselines, portal, flag flips, alembic
- **Feature flag / kill switch:** Reuses existing `job_lifecycle` / `job_cell_links` (already ON in STG/PROD via Azure). No new flags. No default-on code changes.

## Conveyor / merge gate
- Serial programme wave **W1** of JL-UX W1–W5. Tip base: current `origin/main` (X-3 LIVE).
- Admin merge allowed when Change Ledger + CI green (user directed self-automate to PROD LIVE).
- Do **not** enable additional flags as part of this PR.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `JobCellLinks.tsx` (seed from cells, no fetch storm); `JobLifecycle.tsx` (cycle picker, panels, lazy library, permission health); `Layout.tsx` (desktop nav collapse); helpers + tests
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UI only; link list still seeded from existing `listCells` embedded `links[]`
- **Tolerant reader / strict writer applied?** N/A (no schema change)
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — revert FE commit / prior image

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Step links fetch | Unstable `onLinksChange` → refetch storm → 429 | Seeded from cell list; mutations only; no mount refetch loop |
| Job cycle IA | “Job types” list buried | Job cycle picker + create + operator language |
| Desktop nav | Always full width | Collapsible icon rail via preferences store |
| Composer density | Fixed 3-col grid | Resizable left/right panels (localStorage) |
| Permission honesty | Flags ON could still 403 silently | Permission-health banner when 403 on job APIs |
| Library tray rate load | Paginated all docs on mount | First page + Load more |
| Authz tokens / admin grant | 84 | Unchanged |
| Flag defaults | Programme ON in Azure | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Selecting a cell / adding a link does not trigger a listCellLinks refetch storm
- [x] AC-02: Job cycle picker switches packs; create job cycle still works
- [x] AC-03: Desktop nav collapse toggle persists via preferences store
- [x] AC-04: Composer left/right panels resize and persist widths
- [x] AC-05: 403 on listJobTypes shows permission-health banner with job:read/job:author guidance
- [x] AC-06: Library tray loads page 1 lazily; Load more advances pages
- [x] AC-07: Vitest for JobLifecycle + helpers + Layout pass; no alembic / flag changes

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (FE) — JobLifecycle + helpers + Layout — **37 passed** locally
- [ ] Integration — N/A (FE-only)
- [ ] E2E Smoke — staging bake after tip LIVE

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag on → open Job Lifecycle → cycle picker present → axes load without 429 storm path
- [x] CUJ-02: 403 on job types → permission-health banner visible
- [x] CUJ-03: Desktop collapse toggle sets `data-collapsed` / icon rail

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** If operators still see 403 with flags ON, grant `job:read` / `job:author` (or use is_superuser)

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; programme flags remain ON; healthz/readyz 200; CUJ-01 on STG
- **Canary plan:** N/A — FE-only additive
- **Prod post-deploy checks:** PROD tip SHA = MAIN; health 200; Job Lifecycle loads without 429

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Composer regressions; nav collapse breaks desktop IA; unexpected 429 remains
- **Rollback steps:** Revert squash / redeploy prior image; preferences keys are local-only
- **Data repair needed?** No

## 10) Evidence Pack
- Local Vitest 37 passed
- CI URL: (fill after PR)
- STG/PROD tip verify: (post-merge conveyor)

## Gate Checklist
- [x] Gate 0 — Change Ledger complete
- [x] Gate 1 — Scope held (FE-only W1)
- [x] Gate 2 — Compatibility / no migration
- [x] Gate 3 — AC + CUJ covered
- [ ] Gate 4 — CI green on PR
- [ ] Gate 5 — STG then PROD tip LIVE + health
