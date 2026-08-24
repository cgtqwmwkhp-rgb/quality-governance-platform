# Change Ledger (CL-DOC-GRAPH-DG2-DND-PROPOSE)

## 1) Summary
- **Feature / Change name:** Doc Graph DG-2 — Library → edge DnD propose on Relationships Map
- **User goal (1–2 lines):** When `document_graph_dnd_propose` is on, an operator can drag a library document onto the Relationships Map hub to propose a typed edge — always proposed, never auto-confirmed — then confirm from the existing list queue.
- **In scope:** Propose-on-drop helpers + MIME drag payload; Documents library list drag sources; Relationships panel Library tray + drop-type picker + map drop zone; `documentGraphClient.proposeTypedEdge` (forces `proposed`); FE vitest; Change Ledger
- **Out of scope:** Entity360 / href registry (X-1); GraphCoach; Structure map; enabling flags in prod; auto-confirm; DocumentDetail rewrites; inventing parallel deep-link URL builders
- **Feature flag / kill switch:** Reuses master `document_graph`. UI gated by X-0 programme flag `document_graph_dnd_propose` — **default OFF**. Map drop UX also requires Map view (`document_graph_map_view`).

## Conveyor / merge gate
- **Do NOT enable auto-merge until X-1 is PROD LIVE** (Entity360 + ImpactBundle + href registry) per conveyor serial belt `… → DG-1 → X-1 → DG-2 → …`.
- This PR is FE-only and can land after X-1 PROD; leave auto-merge disabled until that gate clears. Rebase onto new `main` if X-1 merges first and conflicts.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `documentGraphDndHelpers`; Documents.tsx grid/table drag sources when DnD flag on; DocumentRelationshipsPanel Library tray + drop-type select in map view; RelationshipsMapView hub drop zone; graph index exports
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None — uses existing `POST /api/v1/document-graph/edges` via `proposeTypedEdge` (client forces `status: proposed`)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** No default changes — `document_graph_dnd_propose` remains default off (pre-registered in X-0)
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Flagged additive UI only
- **Tolerant reader / strict writer applied?** Yes — tray/drop zone invisible when DnD flag off; Documents list unchanged when flag off; propose path always writes `proposed`
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — disable `document_graph_dnd_propose` and/or revert deploy

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Library → Map relationship authoring | Hand-author form only (often confirmed) | Flag-gated DnD propose onto map hub |
| Auto-confirm on drop | N/A risk if DnD confirmed | `proposeTypedEdge` forces `proposed`; helpers never emit confirmed |
| Impact-driving edges from gesture | Could short-circuit confirm queue | Confirm remains on Relationships list queue |
| Documents list drag | Upload-file DnD only | Optional library-document MIME drag when flag on |
| Deep-link / href builders | X-1 owns registry | No parallel URL builders invented here |
| Flag-off behaviour | N/A for this flag | Tray/drop/drag sources absent; list + map unchanged |
| Golden Thread vs Doc Graph copy | Naming risk | Copy never calls Doc Graph “golden thread” |

## 4) Acceptance Criteria (AC)
- [x] AC-01: With `document_graph_dnd_propose` on (and map view), Relationships Map shows Library tray + hub drop zone; drop creates a **proposed** typed edge via `proposeTypedEdge`
- [x] AC-02: Drop never auto-confirms — client forces `status: proposed` even if a caller passes confirmed
- [x] AC-03: Self-drop and duplicate live edges are rejected client-side with an operator-visible reason
- [x] AC-04: Flag off → no tray, no drop zone, Documents list not draggable for graph propose
- [x] AC-05: Documents library cards/rows set the shared MIME payload when the DnD flag is on
- [x] AC-06: FE unit tests cover propose-on-drop helpers, client force-proposed, and map tray/drop wiring
- [x] AC-07: No Entity360 / href_registry files touched (X-1 exclusive)

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (FE) — `npx vitest run src/components/graph/__tests__/documentGraphDndHelpers.test.ts src/components/graph/__tests__/RelationshipsMapView.test.tsx src/api/documentGraphClient.test.ts src/pages/__tests__/DocumentRelationshipsPanel.test.tsx` — 42 passed locally
- [ ] Integration — CI as applicable
- [ ] Contract — N/A
- [ ] E2E Smoke — staging bake when programme flags enabled

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flags on → Relationships → Map → search Library tray → drag onto hub → proposed edge appears → confirm still required in list
- [x] CUJ-02: DnD flag off → no tray/drop zone; Documents list not graph-draggable; hand-author / map|list behaviour unchanged

## 7) Observability & Ops
- **Logs:** Existing Doc Graph client/API paths
- **Metrics:** No new metrics
- **Alerts:** None new
- **Runbook updates:** Keep `document_graph_dnd_propose` off until X-1 PROD + bake; enable only after master `document_graph` and map view are open in the target env

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; flags remain off unless bake enables them; smoke CUJ-01/02 with flags on in a non-prod tenant
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** ACA image tag contains tip SHA; `/health` / version; confirm programme flags still off unless signed enablement; **do not enable DnD until X-1 LIVE**

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Spurious proposed edges from drops; drop auto-confirm regression; Documents list drag regressions with flag on
- **Rollback steps:** Set `document_graph_dnd_propose` false (deploy vars / feature catalogue); master `DOCUMENT_GRAPH_ENABLED=false` if needed; redeploy prior image / revert squash
- **Owner:** Platform Engineering (Doc Graph DG-2) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (propose-only drop; shared MIME; no parallel href builders; flag gates)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flags off until bake)
- [ ] **Conveyor:** X-1 PROD LIVE before merge / auto-merge
