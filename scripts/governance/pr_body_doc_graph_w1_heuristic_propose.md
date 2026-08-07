# Change Ledger (CL-DOC-GRAPH-W1-PR-E-HEURISTIC-PROPOSE)

## 1) Summary
- **Feature / Change name:** Doc Graph Wave 1 PR-E — Heuristic propose + quote_hash citation staleness
- **User goal (1–2 lines):** When `document_graph_heuristic_propose` is enabled, an operator can request non-LLM relationship suggestions (category/PEL siblings, shared CEL, vector/ILIKE, regex citations) that always land as **proposed**, and see deterministic `quote_hash` citation freshness on `references` edges.
- **In scope:** Heuristic propose service + citation helpers; `POST .../propose` (sub-flag) + `GET .../citation-staleness` (master flag); Relationships panel Suggest button + staleness badges; unit tests (BE + FE)
- **Out of scope:** LLM propose (`document_graph_llm_propose`); durable impact propagation; ISO reverse freshness (PR-F); IM demo seed (PR-G); Golden Thread / evidence-pipeline changes; enabling flags in prod
- **Feature flag / kill switch:** `DOCUMENT_GRAPH_HEURISTIC_PROPOSE_ENABLED` / client `document_graph_heuristic_propose` — **default OFF**. Master `DOCUMENT_GRAPH_ENABLED` / `document_graph` still required. Propose returns 404 when either gate is closed; staleness follows the master Doc Graph gate only.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `documentGraphClient` propose + citation-staleness helpers; Relationships panel Suggest button (flag-gated) + citation staleness badges on `references` edges with `quote_hash`
- **Backend (handlers/services):** `DocumentGraphHeuristicProposeService`; `document_graph_citation` (quote_hash / regex / staleness); `DocumentGraphService.create_edge` rejects AI/heuristic auto-confirm of impact-driving types
- **APIs (endpoints changed/added):** `POST /api/v1/document-graph/documents/{id}/propose`; `GET /api/v1/document-graph/edges/{id}/citation-staleness`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `HeuristicProposeResponse`, `CitationStalenessResponse`; FE types mirrored
- **Database (migrations/entities/indexes):** None — reuses P0 edge citation columns
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** No default changes — `document_graph_heuristic_propose_enabled` remains false (catalogue + FE default already present from P0)
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Flagged / Additive — propose path invisible + 404 when off; existing manual edge APIs unchanged
- **Tolerant reader / strict writer applied?** Yes — staleness fetch soft-fails in UI; vector search failure falls back to ILIKE; proposals never auto-confirm impact-driving edges
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — disable heuristic (and/or master) flag and/or revert deploy

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Non-LLM Doc Graph proposals | Flags existed; no propose path | Flag-gated heuristic/regex/vector propose creates **proposed** edges only |
| AI/heuristic auto-confirm of impact edges | Rely on caller discipline | Service rejects `DOCUMENT_GRAPH_HEURISTIC_NO_AUTO_CONFIRM` for implements / requires_record / conflicts_with |
| Citation freshness honesty | quote_hash column unused | Deterministic staleness (`unchanged` / `moved` / `text_changed` / `not_found`) without rewriting published PDF/DOCX bytes |
| Decision audit | N/A for heuristics | `AiDecisionLog` with `auto_applied=false` |
| Golden Thread vs Doc Graph | Risk of conflating names | UI copy never calls Doc Graph “golden thread” |
| Flag-off behaviour | Master routes 404 | Unchanged; propose additionally 404s when heuristic flag off |

## 4) Acceptance Criteria (AC)
- [x] AC-01: With both flags on, `POST /documents/{id}/propose` creates proposed `related_to` / `references` edges from heuristics (never impact-driving confirmed)
- [x] AC-02: Propose logs `AiDecisionLog` with `action=document_graph_heuristic_propose` and `auto_applied=false`
- [x] AC-03: `create_edge` rejects heuristic/AI + confirmed + impact-driving with `DOCUMENT_GRAPH_HEURISTIC_NO_AUTO_CONFIRM`
- [x] AC-04: Regex citations store `quote_hash` + locator; `GET .../citation-staleness` classifies freshness against live `DocumentChunk` text
- [x] AC-05: Heuristic flag off → propose 404; master flag off → Doc Graph routes 404 (including staleness)
- [x] AC-06: Relationships panel shows Suggest when client flag on; shows citation staleness badges for references with quote_hash
- [x] AC-07: Unit tests cover citation helpers, propose guards/flag gates, FE client + panel

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (BE) — `tests/unit/test_document_graph_heuristic_propose.py` (12 passed locally)
- [x] Unit (FE) — documentGraphClient + DocumentRelationshipsPanel vitest (26 passed locally)
- [ ] Integration — CI
- [ ] Contract — CI as applicable
- [ ] E2E Smoke — staging bake when flags enabled

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flags on → Relationships → Suggest relationships → proposed edges appear → operator confirms before impact
- [x] CUJ-02: Flag off → propose 404 / Suggest hidden; references with quote_hash show staleness when master Doc Graph is on

## 7) Observability & Ops
- **Logs:** `doc_graph.heuristic_propose` exception paths; `AiDecisionLog` payload with created ids / sources
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** Keep both flags default off until bake; enable master then heuristic independently

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; flags remain off unless bake enables them
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** ACA image tag contains tip SHA; `/healthz` + `/readyz` 200; flags still off unless signed enablement

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Spurious mass proposals; auto-confirm of impact edges; staleness false positives blocking operators; Performance Budget regression
- **Rollback steps:** Set `DOCUMENT_GRAPH_HEURISTIC_PROPOSE_ENABLED=false` (and/or master `DOCUMENT_GRAPH_ENABLED=false`); redeploy prior image / revert squash if needed
- **Owner:** Platform Engineering (Doc Graph Wave 1) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (propose→confirm; quote_hash staleness; flags default off)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flags off until bake)
