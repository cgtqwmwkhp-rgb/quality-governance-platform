# Change Ledger (CL-DOC-GRAPH-W1-PR-A-RELATIONSHIPS)

## 1) Summary
- **Feature / Change name:** Doc Graph Wave 1 PR-A — Relationships tab, ambient counts, create/confirm/reject
- **User goal (1–2 lines):** When `document_graph` is enabled, an operator can see confirmed inbound/outbound relationship counts on the document (header chips + Versions bar), open a Relationships tab, list edges, hand-author a relationship, and confirm/reject/delete pending edges — without ever calling Doc Graph the Golden Thread.
- **In scope:** `documentGraphClient` factory + `documentGraphApi` registration; Relationships tab + panel; header chips; ambient inbound/outbound/peers counts on `DocumentVersionControlBar`; tab deeplink helpers; create conflict → 409 honesty on the service; FE unit tests
- **Out of scope:** Create wizard polish beyond the panel form; publish impact-preview; heuristic propose; ISO reverse edges; IM seed; bulk-confirm API (client loops confirm one-by-one only); graph visualisation; Golden Thread changes
- **Feature flag / kill switch:** `DOCUMENT_GRAPH_ENABLED` / client `document_graph` — **default OFF**. Routes already 404 when closed (P0). UI loads edges and shows tab/chips/ambient counts only when the flag is open.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** Lazy `DocumentDetail` — Relationships tab + `DocumentRelationshipsPanel` / `DocumentRelationshipChips` / helpers; ambient counts on `DocumentVersionControlBar` (Versions tab); `documentEvidenceTab` relationships deeplink; API factory registered from `client.ts`
- **Backend (handlers/services):** `DocumentGraphService.create_edge` pre-check + IntegrityError → `ConflictError` (`DOCUMENT_GRAPH_EDGE_EXISTS`) so UI duplicate create is a 409, not a 500
- **APIs (endpoints changed/added):** None new — consumes existing `/api/v1/document-graph/*` from P0
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** FE types for edges/list/create/confirm/reject/thread only
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** No default changes — flag remains off
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Flagged / Additive UI only
- **Tolerant reader / strict writer applied?** Yes — UI hides when flag closed; backend duplicate create is explicit conflict
- **Breaking changes:** None
- **Migration plan:** N/A (no DB change)
- **Rollback strategy (DB):** No DB change — disable flag and/or revert deploy

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Authored document↔document relationships UI | API + table only (P0); no library-detail surface | Flag-gated Relationships tab + ambient counts (header + Versions bar) |
| Golden Thread vs Doc Graph copy | Risk of conflating names in UI | UI copy never calls Doc Graph “golden thread”; GT stays `library_document_id` |
| Duplicate edge create from UI | Partial unique index could surface as 500 | Service pre-check + race-safe IntegrityError → 409 `DOCUMENT_GRAPH_EDGE_EXISTS` |
| Confirm / reject human gate | API only | Panel confirm / reject / delete + pending queue depth on tab |
| Flag-off behaviour | Routes 404 | Unchanged; no edge fetch; no tab/chips/ambient counts |

## 4) Acceptance Criteria (AC)
- [x] AC-01: With `document_graph` on, Document Detail shows relationship chips (confirmed / pending / conflicts) and a Relationships tab
- [x] AC-02: Versions tab `DocumentVersionControlBar` shows inbound + outbound confirmed ambient counts when the flag is on; hidden when off
- [x] AC-03: Operator can list edges, hand-create a relationship, confirm/reject/delete; duplicate create surfaces a conflict (not a silent success)
- [x] AC-04: Flag off → no Relationships tab, no chips, no ambient counts, no edge API calls from Document Detail
- [x] AC-05: `documentGraphClient` is a factory; `client.ts` constructs `documentGraphApi` once — no circular import / TDZ boot break
- [x] AC-06: FE unit tests cover client, helpers, chips, panel, evidence tab, VCBar ambient counts

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (FE) — 63 targeted vitest tests green locally (client, helpers, chips, panel, evidence tab, VCBar)
- [ ] Integration — CI (existing Doc Graph P0 backend coverage; this PR adds conflict honesty on create)
- [ ] Contract — CI as applicable
- [ ] E2E Smoke — staging bake when flag enabled

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag on → open library document → see ambient relationship counts (header + Versions bar) → open Relationships tab → list confirmed/pending edges
- [x] CUJ-02: Flag on → hand-author an implements (or peer) edge → appears confirmed (manual) / confirm a proposed edge → counts update; flag off → Document Detail unchanged (no tab/chips/counts/API)

## 7) Observability & Ops
- **Logs:** Existing Doc Graph service paths; conflict code `DOCUMENT_GRAPH_EDGE_EXISTS`
- **Metrics:** No new metrics in this PR
- **Alerts:** None new
- **Runbook updates:** Enable `DOCUMENT_GRAPH_ENABLED` only after P0 bake; Wave 1 UI is inert while flag is off

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; flag remains off unless bake explicitly enables `document_graph`; smoke CUJ-01/02 with flag on in a non-prod tenant
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** ACA image tag contains tip SHA; `/health` / version endpoint; confirm flag still off unless signed enablement

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Unexpected relationship UI/API errors with flag on; boot/TDZ regression from client registration; counts disagreeing with list; 500s on duplicate create
- **Rollback steps:** Set `DOCUMENT_GRAPH_ENABLED=false` (and client catalogue remains default off); redeploy prior image / revert squash if needed
- **Owner:** Platform Engineering (Doc Graph Wave 1) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (flag-gated; factory client; ambient counts; 409 on duplicate)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flag off until bake)
