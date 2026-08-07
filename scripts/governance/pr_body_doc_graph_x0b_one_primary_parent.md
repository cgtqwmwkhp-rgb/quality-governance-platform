# Change Ledger (CL-DOC-GRAPH-X0B-ONE-PRIMARY-PARENT)

## 1) Summary
- **Feature / Change name:** Doc Graph X-0b — one live primary implements parent (DB unique + demotion)
- **User goal (1–2 lines):** Enforce at most one live primary `implements` parent per child document in the database (not only in application code), remediating legacy duplicates deterministically so thread spine stays unambiguous.
- **In scope:** Alembic partial unique index `(tenant_id, src_document_id) WHERE is_primary_parent AND edge_type='implements' AND deleted_at IS NULL`; pre-flight demotion of extras (keep lowest edge id); ORM Index lockstep; service guard aligned to index predicate; IntegrityError → `DOCUMENT_GRAPH_SECOND_PRIMARY_PARENT`; reject clears `is_primary_parent`; unit tests
- **Out of scope:** Map/Thread UI (DG-1), Entity360, Job lifecycle, DnD propose, ISO-as-edges, Golden Thread rename, enabling `DOCUMENT_GRAPH_ENABLED` in prod, other programme slices
- **Feature flag / kill switch:** Master `DOCUMENT_GRAPH_ENABLED` / client `document_graph` — **default OFF** (unchanged)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `DocumentGraphService` — primary-parent lookup matches DB predicate (no status filter); create IntegrityError maps second-primary race; reject clears primary flag
- **APIs (endpoints changed/added):** None (behaviour of existing create/confirm/reject only)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** `20261018_doc_one_primary` → `ux_document_edges_one_primary_parent` on `document_edges`; ORM Index on `DocumentEdge`
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive unique index; existing single-primary rows unchanged; multi-primary legacy groups demoted (extras → `is_primary_parent=false`, lowest id kept)
- **Tolerant reader / strict writer applied?** Yes — readers already pick lowest primary id; writers refused with existing conflict code
- **Breaking changes:** Concurrent/second primary create or confirm continues to 409 (`DOCUMENT_GRAPH_SECOND_PRIMARY_PARENT`); DB now enforces even if service pre-check races
- **Migration plan:** Upgrade demotes duplicate primaries then creates partial unique index; verifies pg_index predicate
- **Rollback strategy (DB):** Downgrade drops index only (does not re-promote demoted rows)

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Second primary implements parent | Service guard only (race / legacy possible) | Partial unique index + demotion of legacy extras |
| Legacy duplicate primaries | Thread ordered by lowest id; DB allowed many | Extras demoted; lowest id remains primary |
| Create/confirm second primary | `DOCUMENT_GRAPH_SECOND_PRIMARY_PARENT` | Unchanged code; DB backstop + IntegrityError mapping |
| Rejected primary occupying slot | Flag could linger; status filter hid it from guard | Reject clears `is_primary_parent`; guard matches index |
| Flag-off document-graph | Routes 404 | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Partial unique index `ux_document_edges_one_primary_parent` on `(tenant_id, src_document_id)` with predicate `is_primary_parent AND edge_type='implements' AND deleted_at IS NULL`
- [x] AC-02: Migration demotes extra primaries (keep lowest edge id) before creating the index, or refuses with a clear report on non-PG colliding data
- [x] AC-03: ORM Index declaration matches migration `INDEX_DDL` (unit lockstep)
- [x] AC-04: Create and confirm still reject a second primary with `DOCUMENT_GRAPH_SECOND_PRIMARY_PARENT`
- [x] AC-05: IntegrityError on one-primary race maps to the same conflict code
- [x] AC-06: Reject clears `is_primary_parent` so a replacement primary can be created
- [x] AC-07: No Map/Thread FE changes in this PR

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (BE) — `tests/unit/test_document_graph_x0b_one_primary_parent.py` + X-0 / Wave 0 Doc Graph suites
- [ ] Unit (FE) — N/A (no FE)
- [ ] Integration — CI as applicable
- [ ] Contract — CI as applicable
- [ ] E2E Smoke — N/A flag-off; bake when master flag enabled

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag on → create/confirm second primary implements parent → `DOCUMENT_GRAPH_SECOND_PRIMARY_PARENT`; DB refuses duplicate live primaries
- [x] CUJ-02: Flag on → reject primary edge → `is_primary_parent` cleared → new primary create allowed (service + index)

## 7) Observability & Ops
- **Logs:** Migration logs demotion group counts / sample ids; existing AuditLog on reject
- **Metrics:** No new metrics
- **Alerts:** None new
- **Runbook updates:** Keep master `DOCUMENT_GRAPH_ENABLED` off until bake; if upgrade logs demotions, review demoted non-primary implements edges in affected tenants

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; migration applied; master flag remains off unless bake
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** ACA image tag contains tip SHA; `/health` / version; confirm flags still off unless signed enablement; alembic head includes `20261018_doc_one_primary`

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Migration failure on index create; unexpected widespread 409s on legitimate primary create after demotion surprise; deploy health regression
- **Rollback steps:** Redeploy prior image / revert squash if needed; optional `alembic downgrade` drops index only (demotions remain — safer than re-ambiguous spine). Set `DOCUMENT_GRAPH_ENABLED=false` if flag was on.
- **Owner:** Platform Engineering (Doc Graph X-0b) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (DB unique one-primary; demote lowest-id keep; no FE)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flags off until bake)
