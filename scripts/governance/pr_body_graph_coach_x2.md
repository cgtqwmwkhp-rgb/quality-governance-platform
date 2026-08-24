# Change Ledger (CL-GRAPH-COACH-X2)

## 1) Summary
- **Feature / Change name:** Shared GraphCoach + orientation (X-2)
- **User goal (1–2 lines):** One `<GraphCoach surface=…/>` with a per-surface step registry coaches operators through Document Relationships (and registers Job Lifecycle steps for later); a shared V/H orientation swap primitive flips the Relationships Map between hub-fan and vertical spine without inventing a second coach.
- **In scope:** `GraphCoach` + `coachSteps/*` registry; `graphOrientation` primitive + `GraphOrientationToggle`; Relationships panel mount; map model vertical layout; FE vitest; Change Ledger
- **Out of scope:** Job Lifecycle UI mount; Structure map; Entity360 changes; ADR/migrations; enabling `graph_coach` in prod/stg; second coach implementation; DocumentDetail body rewrite
- **Feature flag / kill switch:** Reuses X-0 programme flag `graph_coach` / `GRAPH_COACH_ENABLED` — **default OFF**. Orientation toggle ships behind the same flag (no new flag names).

## Conveyor / merge gate
- Depends on **DG-2 PROD LIVE** (satisfied on tip `67b1fb25`).
- Do **not** arm auto-merge until CI green on this PR.
- Do **not** enable `graph_coach` in staging/prod as part of this merge.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `GraphCoach.tsx`; `GraphOrientationToggle.tsx`; `graphCoachHelpers.ts`; `graphOrientation.ts`; `coachSteps/{types,documentRelationships,jobLifecycle,index}.ts`; Relationships map helpers/view orientation; DocumentRelationshipsPanel mount; graph index exports
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** No catalogue/config changes — uses pre-registered `graph_coach` only
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Flagged additive UI only; flag-off renders nothing new
- **Tolerant reader / strict writer applied?** Yes — dismissed coach state is localStorage soft preference; orientation persistence fails open
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — disable `graph_coach` and/or revert deploy

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Shared coach across Doc Graph / Job Lifecycle | Create-wizard authorship only; risk of two coaches | One `<GraphCoach surface>` + registry (`document_relationships`, `job_lifecycle`) |
| Orientation swap | Hard-coded hub-fan map | Shared V/H primitive; map vertical spine when coach flag on |
| Auto-confirm / publish gating via coach | N/A risk | Coach never auto-confirms; never blocks publish |
| Golden Thread naming | Copy risk on coach surfaces | Coach copy never says “golden thread” (tested) |
| Flag thrash | X-0 pre-registered `graph_coach` | No new flags; catalogue/config untouched |
| Flag-off behaviour | N/A | Coach + orientation toggle absent; map/list unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `<GraphCoach surface="document_relationships" />` mounts on Relationships panel when `graph_coach` is on
- [x] AC-02: Flag off → coach and orientation toggle absent; Relationships panel behaviour unchanged
- [x] AC-03: Per-surface step registry includes Doc Graph + Job Lifecycle step packs (JL not mounted yet)
- [x] AC-04: V/H orientation toggle swaps Relationships Map layout (horizontal hub-fan ↔ vertical spine)
- [x] AC-05: Dismiss/Skip/Done persists per surface and stays hidden on remount
- [x] AC-06: Coach copy never includes “golden thread”; never auto-confirms edges
- [x] AC-07: No catalogue / config / JL / ADR / migration files touched

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (FE) — `npx vitest run` on GraphCoach helpers/mount + relationships map/panel suites — **46 passed** locally
- [ ] Integration — CI as applicable
- [ ] Contract — N/A
- [ ] E2E Smoke — staging bake when `graph_coach` enabled

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag on → Relationships tab shows coach → Next through steps → Done/Skip dismisses; remount stays dismissed
- [x] CUJ-02: Flag on + Map view → Horizontal/Vertical toggle flips `data-orientation` and spine layout
- [x] CUJ-03: Flag off → no coach, no orientation toggle; Map|List / DnD behaviour unchanged

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** No new metrics
- **Alerts:** None new
- **Runbook updates:** Keep `GRAPH_COACH_ENABLED` / `graph_coach` off until bake; enable only after Doc Graph surfaces operators will coach against are open in the target tenant

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; flags remain off unless bake; optional coach/orientation smoke with flag on in non-prod tenant
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** ACA image tip SHA; `/health` / version; confirm `graph_coach` still off unless signed enablement

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Coach chrome regressions on Relationships; orientation layout breaks map DnD; accidental “golden thread” copy
- **Rollback steps:** Set `GRAPH_COACH_ENABLED=false`; redeploy prior image / revert squash if needed
- **Owner:** Platform Engineering (GraphCoach X-2) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (shared coach + orientation primitive; no second coach)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flags off until bake)
