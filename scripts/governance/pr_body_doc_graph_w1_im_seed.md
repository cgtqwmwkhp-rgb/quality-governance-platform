# Change Ledger (CL-DOC-GRAPH-W1-PR-G-IM-SEED)

## 1) Summary
- **Wave / phase:** Doc Graph Wave 1 — PR-G (final slice)
- **Feature / Change name:** Doc Graph Wave 1 PR-G — Incident Management demo seed + empty-state coverage honesty
- **User goal (1–2 lines):** When `document_graph` is enabled, an admin can idempotently seed a demo Incident Management Doc Graph vertical in their tenant, and operators see quantitative coverage honesty when relationships are empty/sparse — without inventing ISO coverage % or calling Doc Graph the Golden Thread.
- **In scope:** Idempotent IM seed service + admin API + ops CLI; FE coverage honesty helpers; Relationships empty/sparse strip; VersionControlBar ambient honesty; unit tests (BE + FE); FE client seed helper
- **Out of scope:** LLM propose; durable impact jobs; enabling flags in prod; inventing fake tenants; Golden Thread / evidence-pipeline changes; graph visualisation
- **Feature flag / kill switch:** Master `DOCUMENT_GRAPH_ENABLED` / client `document_graph` — **default OFF**. Seed route 404s when closed; UI honesty surfaces only when the flag is open.
- **Decision log IDs:** ADR-0021 (Document Relationship Graph)
- **Risk register IDs:** None — demo seed + honesty UX only; no new processing of personal data

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `documentRelationshipCoverage` helpers; Relationships panel quantitative empty/sparse honesty; VersionControlBar ambient coverage honesty; Document Detail wires `document_type` + honesty headline; `documentGraphClient.seedIncidentManagementVertical`
- **Backend (handlers/services):** `DocumentGraphImSeedService` (find-or-create IM spine docs + confirmed `auto` edges); admin `POST /api/v1/document-graph/demo/incident-management/seed`
- **APIs (endpoints changed/added):** `POST /api/v1/document-graph/demo/incident-management/seed` (admin:manage; master flag gate)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `ImSeedResponse` (+ document/edge items); FE seed types mirrored
- **Database (migrations/entities/indexes):** None — reuses `documents` + `document_edges`
- **Workflows/jobs/queues (if any):** Ops CLI `python -m scripts.governance.library.seed_document_graph_im`
- **Config/env/flags:** No default changes — `document_graph_enabled` remains false
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Flagged / Additive — seed + honesty invisible when flag off; seed never invents tenants
- **Tolerant reader / strict writer applied?** Yes — seed reuses existing titles; live edges skipped; honesty stays off when type has no expected spine or spine is complete
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No schema change — disable master Doc Graph flag and/or revert deploy; seed rows/edges remain ordinary library data and can be unlinked manually if needed
- **Data repair / audit follow-up:** None required — seed is idempotent and tenant-scoped; no backfill of other tenants

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| IM vertical demo edges | Manual authoring only | Flag-gated idempotent admin/ops seed of confirmed IM spine |
| Empty/sparse Relationships honesty | Soft copy only | Quantitative “N of M expected relationship roles recorded” (type spine; never ISO %) |
| Ambient Versions bar | Inbound/outbound/peers counts | Same + sparse coverage honesty headline when gap exists |
| Golden Thread vs Doc Graph | Risk of conflating names | UI copy never calls Doc Graph “golden thread” |
| Flag-off behaviour | Master routes 404 | Unchanged; seed 404; no honesty strip/counts without flag |

- **STRIDE surfaces touched:** None — additive admin seed behind existing authz (`admin:manage`) + master flag; no new auth/session surface
- **STRIDE threat-model delta:** None — seed cannot invent tenants; flag-off 404 preserved
- **DPIA delta:** None — no new LLM purpose; seed uses existing library document rows
- **LIA delta:** None
- **CRM-M365 addendum impacted:** None

## 4) Acceptance Criteria (AC)
- [x] AC-01: Flag on + admin → `POST .../demo/incident-management/seed` finds-or-creates IM docs and confirms spine edges (`implements` / `requires_record` / `related_to`) with `created_method=auto`
- [x] AC-02: Seed is idempotent (second run reuses docs/edges; no duplicate live edges)
- [x] AC-03: Flag off → seed route 404; Relationships honesty + ambient honesty hidden; no inventing ISO coverage %
- [x] AC-04: Empty/sparse typed documents show “N of M expected relationship roles recorded” on Relationships tab (and Versions bar when gap)
- [x] AC-05: Ops CLI refuses to run when `DOCUMENT_GRAPH_ENABLED` is off
- [x] AC-06: Unit tests cover seed service/route gate, coverage honesty helpers, panel/VCBar ambient honesty, FE client seed helper

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (BE) — `tests/unit/test_document_graph_im_seed.py`
- [x] Unit (FE) — coverage honesty + Relationships panel + VersionControlBar + helpers + documentGraphClient
- [ ] Integration — CI
- [ ] Contract — CI as applicable
- [ ] E2E Smoke — staging bake when flag enabled
- Required check: `Enforce PR Change Ledger + Gates`
- Required check: `Quality Gates`
- Required check: `Smoke Tests (Local Server)`

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag on → admin seeds IM vertical → Relationships on Incident Management Policy shows confirmed spine edges
- [x] CUJ-02: Flag on → empty/sparse typed document shows quantitative coverage honesty; flag off → seed 404 and honesty/counts invisible

## 7) Observability & Ops
- **Logs:** `doc_graph.im_seed` warnings when roles/docs unresolved; CLI stdout summary of created/reused docs/edges
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** Enable `DOCUMENT_GRAPH_ENABLED` only for bake; run admin seed or `python -m scripts.governance.library.seed_document_graph_im --tenant-id N`
- **Known gaps / residual risk:** None — honesty is type-spine based, not ISO %; seed stubs are draft library rows with zero-byte markdown placeholders until real files are uploaded

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Release owner:** Platform Engineering (Doc Graph Wave 1) — David Harris
- **Staging verification:** Tip SHA match; flag remains off unless bake enables `document_graph`; optional seed in non-prod tenant
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** ACA/App Service image/build SHA contains tip; `/healthz` + `/readyz` 200; flag still off unless signed enablement

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Seed creating unexpected documents/edges with flag on; honesty copy implying ISO coverage; Performance Budget regression
- **Rollback steps:** Set `DOCUMENT_GRAPH_ENABLED=false`; redeploy prior image / revert squash if needed
- **Rollback owner:** Platform Engineering (Doc Graph Wave 1) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag-off kill switch

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (flag-gated seed; quantitative honesty; never golden-thread naming)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flag off until bake)
