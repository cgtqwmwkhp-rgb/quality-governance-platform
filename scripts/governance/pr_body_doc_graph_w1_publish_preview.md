# Change Ledger (CL-DOC-GRAPH-W1-PR-D-PUBLISH-PREVIEW)

## 1) Summary
- **Feature / Change name:** Doc Graph Wave 1 PR-D — Publish impact preview checklist
- **User goal (1–2 lines):** When `document_graph` is enabled, publishing a library document version first shows a read-only checklist of likely side effects (downstream dependents, CEL rematch candidates, campaigns, open watch impacts, GKB lifecycle hooks) before the operator confirms.
- **In scope:** Flag-gated publish preview dialog on Document Detail; pure preview helpers; FE unit tests
- **Out of scope:** Durable Doc Graph impact jobs (Wave 2 / `document_graph_impact_propagation`); changing publish backend hooks; Golden Thread; create-wizard (PR-C); heuristic propose
- **Feature flag / kill switch:** `DOCUMENT_GRAPH_ENABLED` / client `document_graph` — **default OFF**. Flag-off publish stays one-click (unchanged).

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `DocumentDetail` publish path opens `DocumentPublishImpactPreview` when flag on; `documentPublishImpactHelpers` compose checklist from edges/thread/evidence/campaigns/impacts
- **Backend (handlers/services):** None — reuses existing thread / compliance / evidence / impacts APIs and existing publish route
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** No default changes — flag remains off
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Flagged / Additive UI only
- **Tolerant reader / strict writer applied?** Yes — preview fails soft (shows partial checklist + error) and still allows confirm; flag-off unchanged
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — disable flag and/or revert deploy

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Publish side-effect honesty | Publish ran rematch / quiz / re-ack hooks without a preflight UI | Flag-on publish shows read-only impact checklist before confirm |
| Flag-off publish UX | One-click publish | Unchanged |
| Doc Graph vs Golden Thread | Risk of conflating names | Preview copy never calls Doc Graph “golden thread” |
| Durable impact propagation | Not in Wave 1 | Still Wave 2 — checklist is preview only |

## 4) Acceptance Criteria (AC)
- [x] AC-01: With `document_graph` on, Publish opens the impact preview dialog (does not POST publish until Confirm)
- [x] AC-02: Preview lists dependents (thread + inbound implements), confirmed CEL rematch candidates, affected campaigns, open impacts, and lifecycle hooks
- [x] AC-03: Cancel closes without publishing; Confirm calls existing `/documents/{id}/publish`
- [x] AC-04: Flag off → Publish posts immediately (no dialog)
- [x] AC-05: Partial fetch failure surfaces an error but still allows confirm with best-effort checklist
- [x] AC-06: FE unit tests cover preview helpers

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (FE) — publish impact helper vitest
- [ ] Integration — N/A (FE-only)
- [ ] Contract — N/A
- [ ] E2E Smoke — staging bake when flag enabled
- [ ] Performance Budget (PR-04) — lazy DocumentDetail route chunk

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag on → open draft → Publish → see checklist → Confirm → version publishes
- [x] CUJ-02: Flag off → Publish → immediate publish (no preview dialog)

## 7) Observability & Ops
- **Logs:** Existing publish / GKB lifecycle paths
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** Flag remains default off

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; flag remains off unless bake enables `document_graph`
- **Canary plan:** N/A — flag default off
- **Prod post-deploy checks:** Prod `build_sha` == tip; `/healthz` + `/readyz` 200

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Publish blocked behind broken preview; false checklist; Performance Budget regression
- **Rollback steps:** Set `DOCUMENT_GRAPH_ENABLED=false`; redeploy prior image / revert squash if needed
- **Owner:** Platform Engineering (Doc Graph Wave 1) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (flag-gated preview; existing publish API)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flag off until bake)
