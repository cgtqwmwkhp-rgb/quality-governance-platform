# Change Ledger (CL-DOC-GRAPH-W1-PR-C-CREATE-WIZARD)

## 1) Summary
- **Feature / Change name:** Doc Graph Wave 1 PR-C — Create-wizard relationship step (post-upload)
- **User goal (1–2 lines):** When `document_graph` is enabled, uploading a library Document keeps the operator in a relationship authorship step so implements / requires_record / related_to / conflicts_with can be recorded at create time — not only later on Document Detail.
- **In scope:** Flag-gated post-upload `DocumentCreateRelationshipsStep` wired from `Documents.tsx` upload success; create-wizard edge-type allowlist helper; FE unit tests
- **Out of scope:** Publish/revise impact preview; heuristic propose; ISO reverse; IM seed; `references` at create (detail tab only); flag default changes; Golden Thread / controlled-doc lineage
- **Feature flag / kill switch:** `DOCUMENT_GRAPH_ENABLED` / client `document_graph` — **default OFF**. Step is invisible and unused while closed (upload modal closes as today).

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `Documents` upload success → optional relationship step when flag on; new `DocumentCreateRelationshipsStep`; `CREATE_WIZARD_DOCUMENT_EDGE_TYPES` helper
- **Backend (handlers/services):** None — consumes existing `/api/v1/document-graph/edges` create
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** No default changes — flag remains off
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Flagged / Additive UI only
- **Tolerant reader / strict writer applied?** Yes — flag-off path unchanged; create uses existing edge API
- **Breaking changes:** None
- **Migration plan:** N/A (no DB change)
- **Rollback strategy (DB):** No DB change — disable flag and/or revert deploy

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Relationship capture at library document authorship | Only via Document Detail Relationships tab | Flag-on upload success offers create-wizard step before close |
| Authored edge types at create | N/A | implements / requires_record / related_to / conflicts_with (not references) |
| Flag-off behaviour | Upload closes after success | Unchanged — no relationship step, no Doc Graph API from upload path |
| Golden Thread vs Doc Graph copy | Risk of conflating names | Step copy never calls Doc Graph “golden thread”; GT / lineage unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: With `document_graph` on, successful library upload opens the relationship step (modal stays open)
- [x] AC-02: Operator can search a counterpart, pick implements|requires_record|related_to|conflicts_with, and create via `documentGraphApi.createEdge`
- [x] AC-03: Skip / Done closes the step without requiring a relationship
- [x] AC-04: Flag off → upload success closes modal as before; no relationship step rendered
- [x] AC-05: Create-wizard type list excludes `references`; UI never labels Doc Graph as Golden Thread
- [x] AC-06: FE unit tests cover step create/skip, Documents flag on/off upload paths, and wizard type allowlist

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (FE) — targeted vitest for create step + Documents upload flag paths + helpers
- [ ] Integration — N/A (FE-only; backend create covered by P0)
- [ ] Contract — N/A
- [ ] E2E Smoke — staging bake when flag enabled
- [ ] Performance Budget (PR-04) — lazy `Documents` route chunk; shell index budget unchanged by design

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag on → upload library doc → relationship step → record implements (or peer/conflict) → Done → list refreshed; edge exists via create API
- [x] CUJ-02: Flag off → upload → modal closes; no relationship step / no createEdge from upload path

## 7) Observability & Ops
- **Logs:** Existing Doc Graph create-edge paths
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** Enable `DOCUMENT_GRAPH_ENABLED` only after bake; Wave 1 UI remains inert while flag is off

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; flag remains off unless bake explicitly enables `document_graph`
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** Prod version `build_sha` == tip; `/healthz` + `/readyz` 200; confirm flag still off unless signed enablement

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Upload modal stuck on relationship step; createEdge errors blocking upload completion UX with flag on; Performance Budget regression attributed to this slice
- **Rollback steps:** Set `DOCUMENT_GRAPH_ENABLED=false`; redeploy prior image / revert squash if needed
- **Owner:** Platform Engineering (Doc Graph Wave 1) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (flag-gated post-upload step; existing create-edge API; no GT rename)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flag off until bake)
