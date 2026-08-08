# Change Ledger (CL-DOC-GRAPH-DG3-STRUCTURE-MAP)

## 1) Summary
- **Feature / Change name:** Doc Graph DG-3 — whole-library Structure map
- **User goal (1–2 lines):** When `document_graph_structure_map` is on, an operator can explore confirmed implements relationships across the library on a dedicated Structure map that reuses the DG-1 map renderer and mounts the shared X-2 GraphCoach — without calling Doc Graph the Golden Thread.
- **In scope:** `DocumentStructureMap` page + route; structure-map helpers; GraphCoach surface `document_structure_map`; Documents library CTA (flag-gated); FE vitest; Change Ledger
- **Out of scope:** Alembic / migrations; JL-1 Job Lifecycle models; Entity360 backend; enabling flags in prod/stg; force-directed layout; bulk Doc Graph API; DocumentDetail rewrite
- **Feature flag / kill switch:** Reuses master `document_graph`. UI gated by X-0 programme flag `document_graph_structure_map` — **default OFF**. Coach chrome additionally requires `graph_coach` (also default OFF).

## Conveyor / merge gate
- Depends on **DG-2 · X-2 PROD LIVE** (satisfied on tip `1d09120e`).
- Parallel OK with JL-1 (different blast area; this PR touches no `alembic/`).
- Do **not** arm auto-merge until CI green on this PR.
- Do **not** enable `document_graph_structure_map` / `graph_coach` in staging/prod as part of this merge.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `pages/DocumentStructureMap.tsx`; `components/graph/documentStructureMapHelpers.ts`; `coachSteps/documentStructureMap.ts` + surface registry; App route `/documents/structure`; Documents CTA when flag on; graph index exports
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None — consumes existing documents list + per-document edges (`edge_type=implements`, `status=confirmed`)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** No default changes — `document_graph_structure_map` / `graph_coach` remain default off (pre-registered in X-0)
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Flagged additive UI only; flag-off redirects Structure map → `/documents` and hides library CTA
- **Tolerant reader / strict writer applied?** Yes — confirmed implements only; proposed edges never drawn; fetch skipped when master Doc Graph closed
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — disable `document_graph_structure_map` and/or revert deploy

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Whole-library implements explorer | Per-document Relationships Map / Thread only | Flag-gated Structure map page reusing DG-1 `RelationshipsMapView` |
| Spine / Structure naming | “Spine explorer” concept | User-facing **Structure map**; copy never says “golden thread” |
| Shared coach reuse | Relationships + JL registry only | Adds `document_structure_map` surface; still one `<GraphCoach surface>` |
| Proposed edges on structure chrome | Risk of presenting guesses as spine | Confirmed implements only |
| Flag thrash | X-0 pre-registered `document_graph_structure_map` | No new flag names; catalogue/config untouched |
| Flag-off behaviour | N/A | CTA absent; `/documents/structure` redirects to library; no edge fetch |
| JL-1 / migrations | Parallel lane | Untouched (`alembic/` clean) |

## 4) Acceptance Criteria (AC)
- [x] AC-01: With `document_graph_structure_map` on, `/documents/structure` renders Structure map; Documents library shows Structure map CTA
- [x] AC-02: Flag off → CTA absent; route redirects to `/documents`; no documents/edges fetch for Structure map
- [x] AC-03: Map reuses DG-1 `RelationshipsMapView` / `buildRelationshipMapModel` over confirmed implements edges only
- [x] AC-04: When `graph_coach` is also on, mounts `<GraphCoach surface="document_structure_map" />` (+ orientation toggle via existing primitive)
- [x] AC-05: Master `document_graph` off → page chrome may show when structure flag on, but no Doc Graph edge fetch
- [x] AC-06: FE unit tests cover helpers + flag-off behaviour; coach copy never includes “golden thread”
- [x] AC-07: No alembic / JL-1 / Entity360 backend / catalogue default changes

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (FE) — `npx vitest run` on structure map helpers/page + GraphCoach registry/mount suites — **27 passed** locally
- [ ] Integration — CI as applicable
- [ ] Contract — N/A
- [ ] E2E Smoke — staging bake when programme flags enabled

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flags on → Documents → Structure map CTA → pick focus → confirmed implements hub/spine map; coach advances when `graph_coach` on
- [x] CUJ-02: Structure map flag off → CTA gone; `/documents/structure` redirects; no Structure map fetches

## 7) Observability & Ops
- **Logs:** Existing Doc Graph client/API paths
- **Metrics:** No new metrics
- **Alerts:** None new
- **Runbook updates:** Keep `document_graph_structure_map` off until bake; enable only after master `document_graph` (and preferably map/thread) are open in the target env

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; flags remain off unless bake; optional Structure map smoke with flags on in a non-prod tenant
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** ACA image tip SHA; `/health` / version; confirm programme flags still off unless signed enablement

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Structure map errors with flags on; unexpected Doc Graph traffic with structure flag off; accidental “golden thread” copy
- **Rollback steps:** Set `document_graph_structure_map` false (deploy vars / feature catalogue); master `DOCUMENT_GRAPH_ENABLED=false` if needed; redeploy prior image / revert squash
- **Owner:** Platform Engineering (Doc Graph DG-3) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (reuse DG-1 map + X-2 coach; confirmed implements; flag gates)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flags off until bake)
- [x] **Conveyor:** DG-2 · X-2 PROD LIVE before merge; do not arm auto-merge until CI green
