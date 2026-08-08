# Change Ledger (CL-ENTITY360-X1)

## 1) Summary
- **Feature / Change name:** Entity360 X-1 — composer + ImpactBundle + href registry
- **User goal (1–2 lines):** One shared bidirectional hop contract for Connections and publish impact; risk upstream folds onto the same internals without reshaping its wire; publish blocks when the ImpactBundle is degraded.
- **In scope:** `GET /api/v1/entity-360/{type}/{id}`; href registry; document-graph + case_link producers (bidirectional registration); fold `list_upstream_for_risk`; server ImpactBundle + publish 409 when incomplete; FE `entity360Client` + `Entity360Strip` + DocumentDetail mount/publish path; `document:confirm_edge`; unit/FE tests
- **Out of scope:** Job lifecycle, DnD propose, satellites, GraphCoach, W2 LLM, enabling `entity_360` in prod
- **Feature flag / kill switch:** `entity_360` / `ENTITY_360_ENABLED` — **default OFF** (pre-registered in X-0). Flag-off → Entity360 routes 404; publish falls back to pre-bundle path.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `entity360Client.ts`; `Entity360Strip` + helpers; DocumentDetail mount + ImpactBundle publish path; publish preview can block confirm
- **Backend (handlers/services):** `entity_360` composer/producers; `href_registry`; risk upstream fold; documents publish guard; document-graph confirm/reject → `document:confirm_edge`
- **APIs (endpoints changed/added):** `GET /api/v1/entity-360/{type}/{id}`; `GET /api/v1/entity-360/documents/{id}/impact`; risk upstream unchanged wire
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `Entity360Hop` / `Entity360Bundle` / `ImpactBundle`; FE types aligned
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** Wiring only for existing `entity_360` (no new flags)
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive API behind default-off flag; risk upstream narrowing view frozen; confirm_edge is additive permission (admin persona lists updated)
- **Tolerant reader / strict writer applied?** Yes — hop fields optional where absent; denied sources carry no counts
- **Breaking changes:** Confirm/reject edges now require `document:confirm_edge` (was `document:update`) when Doc Graph is enabled
- **Migration plan:** N/A (no DB). Grant `document:confirm_edge` to roles that confirm edges before enabling Doc Graph confirm UX in prod
- **Rollback strategy (DB):** No DB change — set `ENTITY_360_ENABLED=false`; revert deploy if needed

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Shared hop contract | Thread/risk shapes diverged | Frozen Entity360 hop + bundle |
| href construction | String-built at call sites | Central `href_registry` |
| Risk upstream | Standalone service logic | Folded onto case_link producer; wire frozen |
| Publish on degraded preview | Silent Promise.allSettled still publishable | Entity360 ImpactBundle `complete=false` blocks FE + HTTP 409 |
| Edge confirm RBAC | `document:update` | `document:confirm_edge` |
| Per-hop oracle leak | N/A | Denied sources carry no counts |
| Flag-off Entity360 | N/A | 404 |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Entity360 hop carries required contract fields; href from registry only
- [x] AC-02: Document graph producer registers both upstream and downstream day one
- [x] AC-03: Risk `/upstream` wire shape unchanged (contract test); internals via Entity360
- [x] AC-04: ImpactBundle `complete=false` blocks publish (FE + server)
- [x] AC-05: `entity_360` flag-off → Entity360 routes 404
- [x] AC-06: `document:confirm_edge` enforced on confirm/reject; catalogue + admin perms updated
- [x] AC-07: FE Connections strip + client behind `entity_360`

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (BE) — `tests/unit/test_entity_360_x1.py` + risk upstream + permission catalogue + Doc Graph X-0 suites green locally
- [x] Unit (FE) — Entity360Strip helpers + publish impact helpers
- [ ] Integration — CI
- [ ] Contract — CI as applicable
- [ ] E2E Smoke — staging bake when flag enabled

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag on → Entity360 for document returns upstream/downstream + sources; denied has no count
- [x] CUJ-02: Risk upstream still returns `source_type|source_id|title|reference|href` (+ optional audit_run_id)
- [x] CUJ-03: Degraded ImpactBundle → publish blocked; flag off → Entity360 404 and publish falls back

## 7) Observability & Ops
- **Logs:** Producer errors become `degraded_reasons` on the bundle
- **Metrics:** No new metrics in this PR
- **Alerts:** None new
- **Runbook updates:** Keep `ENTITY_360_ENABLED` off until bake; grant `document:confirm_edge` before Doc Graph confirm in prod

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; flags remain off unless bake; optional Entity360 smoke with flag on in non-prod tenant
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** ACA image tip SHA; `/health` / version; confirm `entity_360` still off unless signed enablement

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Publish false-positives blocked; Entity360 500s with flag on; confirm_edge lockout for legitimate editors
- **Rollback steps:** Set `ENTITY_360_ENABLED=false`; temporarily re-grant via `document:update` hotfix if confirm lockout; redeploy prior image if needed
- **Owner:** Platform Engineering (Entity360 X-1) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (hop + ImpactBundle + risk freeze)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flags off until bake)
