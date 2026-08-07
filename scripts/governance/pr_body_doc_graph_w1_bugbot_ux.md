# Change Ledger (CL-DOC-GRAPH-W1-PR-B-BUGBOT-UX)

## 1) Summary
- **Feature / Change name:** Doc Graph Wave 1 PR-B — Bugbot UX honesty (stale edges + hide counts on error)
- **User goal (1–2 lines):** When an operator navigates between library documents (or listEdges fails) with `document_graph` on, relationship chips and Versions-bar ambient counts must never show another document's leftover edges or misleading zeros from a failed load.
- **In scope:** Clear `edges` (+ error) at the start of `loadEdges` before fetch; hide header chips and pass `relationshipCounts={null}` when `edgesError` is set; pure helpers + FE unit tests
- **Out of scope:** Create-wizard relationship step; publish impact preview; heuristic propose; ISO reverse; IM seed; flag default changes; Golden Thread
- **Feature flag / kill switch:** `DOCUMENT_GRAPH_ENABLED` / client `document_graph` — **default OFF** (unchanged). UI remains inert while closed.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `DocumentDetail.loadEdges` clears prior edges before fetch; header `DocumentRelationshipChips` and Versions `DocumentVersionControlBar` ambient counts gated via helpers when `edgesError` is set
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** No default changes — flag remains off
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Flagged / Additive honesty fix only
- **Tolerant reader / strict writer applied?** Yes — UI hides ambient surfaces on list failure; flag-off unchanged
- **Breaking changes:** None
- **Migration plan:** N/A (no DB change)
- **Rollback strategy (DB):** No DB change — revert deploy / disable flag

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Stale relationship chips on document navigation | Prior document edges could remain visible until the next listEdges resolved | `loadEdges` clears edges (+ error) before fetch when flag on + valid id |
| Ambient counts / chips after listEdges failure | Counts could still render from empty/stale summary (misleading zeros) | Chips hidden; Versions bar gets `relationshipCounts={null}` when `edgesError` set |
| Flag-off behaviour | No tab/chips/counts/API | Unchanged |
| Golden Thread naming | Doc Graph ≠ GT | Unchanged — copy still never says “golden thread” |

## 4) Acceptance Criteria (AC)
- [x] AC-01: With `document_graph` on, starting `loadEdges` for a valid documentId clears `edges` (and error) before the network call
- [x] AC-02: When `edgesError` is set, header relationship chips are not rendered
- [x] AC-03: When `edgesError` is set, `DocumentVersionControlBar` receives `relationshipCounts={null}` (no inbound/outbound/peers strip)
- [x] AC-04: Flag off → behaviour unchanged (no edge fetch; no chips/counts)
- [x] AC-05: FE unit tests cover ambient-count / chip honesty helpers

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (FE) — targeted vitest for ambient honesty helpers
- [ ] Integration — N/A (FE-only)
- [ ] Contract — N/A
- [ ] E2E Smoke — staging bake when flag enabled

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag on → open doc A with relationships → navigate to doc B → chips/counts never keep showing A's edges while B loads
- [x] CUJ-02: Flag on → listEdges fails → header chips hidden and Versions ambient counts omitted (not zeroed); flag off → Document Detail unchanged

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** None — flag remains default off

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; flag remains off unless bake explicitly enables `document_graph`
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** Prod version `build_sha` == tip; `/healthz` + `/readyz` 200; confirm flag still off unless signed enablement

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Relationship UI honesty regression with flag on; unexpected blank chips when edges loaded successfully
- **Rollback steps:** Set `DOCUMENT_GRAPH_ENABLED=false`; redeploy prior image / revert squash if needed
- **Owner:** Platform Engineering (Doc Graph Wave 1) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (clear-before-fetch; hide ambient on list error)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flag off until bake)
