# Change Ledger (CL-DOC-GRAPH-DG1-THREAD-MAP)

## 1) Summary
- **Feature / Change name:** Doc Graph DG-1 — ambient implements thread strip + Relationships Map|List
- **User goal (1–2 lines):** When programme flags are on, an operator sees the confirmed Doc Graph implements spine as an ambient strip on Document Detail, and can toggle a hub-and-peers Map over the Relationships panel — without N+1 fetches and without calling Doc Graph the Golden Thread.
- **In scope:** `DocumentThreadStrip` (confirmed-only `/thread` hops from X-0); `RelationshipsMapView` Map|List toggle over existing edges API; minimal DocumentDetail + Relationships panel mount points; FE helpers + vitest; Change Ledger
- **Out of scope:** Alembic / primary-parent uniqueness migration (X-0b); Entity360 composer; DnD propose; spine explorer; GraphCoach; enabling flags in prod; force-directed layout
- **Feature flag / kill switch:** Reuses master `document_graph`. UI gated by X-0 programme flags `document_graph_thread_ambient` and `document_graph_map_view` — **default OFF**.

## Conveyor / merge gate
- **Merge waits for X-0b PROD** (one-primary-parent partial unique index) per conveyor — do not merge DG-1 to `main` until X-0b is LIVE, even though this PR has no migration conflict.
- Auto-merge left **disabled** until X-0b is PROD LIVE; babysit thereafter.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** New `frontend/src/components/graph/*` (`DocumentThreadStrip`, `RelationshipsMapView`, helpers); DocumentDetail mounts strip only; DocumentRelationshipsPanel Map|List toggle when map flag on
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None — consumes existing `/thread` + edges list from X-0 / Wave 1
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None (X-0b exclusive)
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** No default changes — programme flags remain default off
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Flagged additive UI only
- **Tolerant reader / strict writer applied?** Yes — strip/map invisible when flags off; thread fetch confirmed-only (no `include_proposed`); map uses confirmed edges only
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — disable programme flags and/or revert deploy

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Ambient implements spine on Document Detail | Counts/chips only; no hop strip | Flag-gated `DocumentThreadStrip` from enriched confirmed hops |
| Thread N+1 on ambient render | Would require per-hop document GETs | Uses X-0 hop `title` / `reference` / `href` |
| Proposed edges on ambient strip | Risk of presenting guesses as spine | Confirmed-only default (no `include_proposed`) |
| Relationships visualisation | List only | Optional Map\|List hub-and-peers (no force-directed toy) |
| DocumentDetail bloat / merge contention | Large page owns all graph UX | Extracted components; mount points only |
| Flag-off behaviour | N/A for these flags | Strip/toggle/map absent; no thread fetch when ambient off |
| Golden Thread vs Doc Graph copy | Naming risk | Copy never calls Doc Graph “golden thread” |

## 4) Acceptance Criteria (AC)
- [x] AC-01: With `document_graph` + `document_graph_thread_ambient` on, Document Detail shows implements thread strip from confirmed hops (title/reference/href)
- [x] AC-02: Ambient strip does not call `include_proposed`; flag off → strip invisible and no `/thread` fetch
- [x] AC-03: With `document_graph_map_view` on, Relationships panel offers Map\|List; map is hub + peers over confirmed edges
- [x] AC-04: Map flag off → no toggle, list-only behaviour unchanged
- [x] AC-05: DocumentDetail only mounts the strip component; graph UI lives under `frontend/src/components/graph/*`
- [x] AC-06: FE unit tests cover strip/map helpers and flag-off invisibility

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (FE) — graph helpers + strip/map + Relationships panel suites green locally (`npx vitest run src/components/graph src/pages/__tests__/DocumentRelationshipsPanel.test.tsx` — 36 passed)
- [ ] Integration — CI as applicable
- [ ] Contract — N/A
- [ ] E2E Smoke — staging bake when programme flags enabled

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flags on → open library document → ambient implements strip shows enriched confirmed ancestors/descendants; ambient off → strip absent, no thread call
- [x] CUJ-02: Map flag on → Relationships tab → Map shows hub + confirmed peers; List restores confirmed rows; map flag off → list-only, no toggle

## 7) Observability & Ops
- **Logs:** Existing Doc Graph client/API paths
- **Metrics:** No new metrics
- **Alerts:** None new
- **Runbook updates:** Keep programme flags off until X-0b PROD + bake; enable `document_graph_thread_ambient` / `document_graph_map_view` only after master `document_graph` is open

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; flags remain off unless bake enables them; smoke CUJ-01/02 with flags on in a non-prod tenant
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** ACA image tag contains tip SHA; `/health` / version; confirm programme flags still off unless signed enablement; **do not enable strip/map until X-0b LIVE**

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Ambient strip errors with flags on; map layout regressions; unexpected `/thread` traffic with ambient off
- **Rollback steps:** Set `document_graph_thread_ambient` / `document_graph_map_view` false (deploy vars); master `DOCUMENT_GRAPH_ENABLED=false` if needed; redeploy prior image / revert squash
- **Owner:** Platform Engineering (Doc Graph DG-1) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (X-0 hop contract consumed; confirmed-only ambient; hub map; flag gates)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flags off until bake)
- [ ] **Conveyor:** X-0b PROD LIVE before merge
