# Change Ledger (CL-JL2-SWIMLANE-COMPOSER)

## 1) Summary
- **Feature / Change name:** JL-2 — Job Lifecycle swimlane composer UX
- **User goal (1–2 lines):** When `job_lifecycle` is on, an operator can compose Matrix / Transpose / Phase swimlanes over JL-1 axes, attach library document **refs** onto cells via DnD, and inspect Connections through Entity360 — without a second document SSOT or org chart.
- **In scope:** `JobLifecycle` page + routes; FE API client; helpers; Library tray DnD → cell `library_document_id[]` PUT; Entity360 strip on selected step; GraphCoach `job_lifecycle` mount; Documents CTA + flag-gated nav; Vitest; Change Ledger
- **Out of scope:** Alembic / migrations; enabling `job_lifecycle` in any environment; JL-3 CellLinks; department annotation; LookupOption axis binding; parallel deep-link builders
- **Feature flag / kill switch:** Reuses `job_lifecycle` / `JOB_LIFECYCLE_ENABLED` — **default OFF**. Flag-off → composer redirects to `/documents`; JL APIs remain 404. Do **not** flip env flags in this PR.

## Conveyor / merge gate
- Depends on **JL-1** (`0f3cf224`) axes + Entity360 job producer. Prefer merge after JL-1 is confirmed **PROD LIVE**; flag-off makes earlier merge deploy-safe (composer inert).
- Tip base: `origin/main` including DG-3 `76394d18`.
- Do **not** arm auto-merge until CI green on this PR.
- Do **not** enable `job_lifecycle` in staging/prod as part of this merge (even after JL-1 LIVE — enable is a separate bake decision).

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `pages/JobLifecycle.tsx`; `pages/jobLifecycleHelpers.ts`; App routes `/job-lifecycle` + `/job-lifecycle/steps/:stepId`; Documents CTA; Layout risk-improvement nav (flag-gated); coach copy ADR-aligned (lanes not departments)
- **Backend (handlers/services):** None — consumes JL-1 `/api/v1/job-lifecycle/*`
- **APIs (endpoints changed/added):** None — FE client `jobLifecycleClient.ts` only
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** FE DTOs mirroring JL-1 schemas
- **Database (migrations/entities/indexes):** None (`alembic/` untouched)
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** No default changes — `job_lifecycle` remains default off
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Flagged additive UI only; flag-off redirects composer → `/documents` and hides CTA/nav
- **Tolerant reader / strict writer applied?** Yes — cells write `library_document_ids` arrays only; DnD never copies document bodies
- **Breaking changes:** None while flag off
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — disable `job_lifecycle` and/or revert deploy

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| JL swimlane UX | API-only (JL-1) | Flag-gated Matrix · Transpose · Phase composer |
| Cell document SSOT | Junction API | UI attaches/removes `library_document_id` refs only |
| Org / department framing | Coach mentioned “departments” | Coach + empty copy say lane/step process axes (ADR-0022) |
| Connections | Entity360 job producer only | Composer mounts `<Entity360Strip entityType="job_step" />` |
| Shared coach | Registry only | Mounts `<GraphCoach surface="job_lifecycle" />` |
| Library DnD MIME | DG-2 Relationships | Reused for cell attach (same MIME; refs → PUT) |
| Flag thrash | Pre-registered `job_lifecycle` | No new flag names; defaults untouched |
| Alembic parallelism | JL-1 migration landed | Untouched this PR |

## 4) Acceptance Criteria (AC)
- [x] AC-01: With `job_lifecycle` on, `/job-lifecycle` renders swimlane composer with Matrix / Transpose / Phase views over the same cells
- [x] AC-02: Flag off → Documents CTA/nav absent; route redirects to `/documents`; no JL pack fetch
- [x] AC-03: Library DnD onto cells calls PUT with `library_document_ids` (refs only; no body copy)
- [x] AC-04: Selected step mounts Entity360 Connections strip (`job_step`); deep-link `/job-lifecycle/steps/:stepId` focuses Phase
- [x] AC-05: When `graph_coach` is also on, mounts `<GraphCoach surface="job_lifecycle" />`
- [x] AC-06: Editable axes create job type / lane / step via JL-1 APIs (code derived from name; not org identity)
- [x] AC-07: FE unit tests cover helpers + flag-off + DnD attach; no alembic / flag default changes

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (FE) — `npx vitest run` jobLifecycle client/helpers/page — **15 passed** locally; Layout nav suite updated
- [ ] Integration — CI as applicable
- [ ] Contract — N/A
- [ ] E2E Smoke — staging bake when `job_lifecycle` enabled (after JL-1 LIVE)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag on → Documents CTA → pick job type → Matrix cells → drag library doc → cell shows ref; Connections strip for step
- [x] CUJ-02: Flag off → CTA/nav gone; `/job-lifecycle` redirects; no JL fetches

## 7) Observability & Ops
- **Logs:** Existing JL-1 / Entity360 client/API paths
- **Metrics:** No new metrics
- **Alerts:** None new
- **Runbook updates:** Keep `JOB_LIFECYCLE_ENABLED` off until JL-1 PROD LIVE + bake; apply 84-token admin grant before enablement

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; `job_lifecycle` remains off unless bake; optional composer smoke with flag on in a non-prod tenant **after** JL-1 LIVE
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** ACA image tip SHA; `/health` / version; confirm `job_lifecycle` still off unless signed enablement

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Composer errors with flag on; accidental document-body copy behaviour; accidental “department/org chart” framing; unexpected JL traffic with flag off
- **Rollback steps:** Set `JOB_LIFECYCLE_ENABLED=false` (deploy vars / feature catalogue); redeploy prior image / revert squash
- **Owner:** Platform Engineering (Doc Graph × Job Lifecycle) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (JL-1 APIs; ADR-0022 axes; Entity360 Connections; Matrix·Transpose·Phase views)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked) — tip SHA; flag remains off
- [ ] **Gate 4:** Canary healthy (if used) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flags off until bake; prefer JL-1 LIVE before merge)
