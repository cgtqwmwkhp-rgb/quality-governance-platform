# Change Ledger (CL-DOC-GRAPH-X0-THREAD-CONTRACT)

## 1) Summary
- **Feature / Change name:** Doc Graph X-0 — enriched thread hop contract, walk safety, AuditLog, programme flag pre-reg
- **User goal (1–2 lines):** Ambient Doc Graph thread can render without N+1, walks confirmed-only by default with cycle-safe deterministic ordering, graph mutations are attributed in AuditLog, and later programme flags are pre-registered default-off — without calling Doc Graph the Golden Thread.
- **In scope:** Enrich `DocumentThreadHop` (`title`/`reference`/`href`/`origin`/`status`); confirmed-only thread + `include_proposed`; deterministic ancestor `order_by`; visited-set descendant walk; second-primary `implements` parent guard on create/confirm; AuditLog on confirm/reject/soft-delete; pre-register 9 programme flags; FE client hop types + `include_proposed` param; unit tests
- **Out of scope:** Map UI, Entity360 composer, Job lifecycle, DnD propose behaviour, ISO-as-edges, Golden Thread rename/reuse, enabling flags in prod
- **Feature flag / kill switch:** Master `DOCUMENT_GRAPH_ENABLED` / client `document_graph` — **default OFF** (unchanged). Programme flags registered default-off only; ambient thread UI gated later by `document_graph_thread_ambient`.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `documentGraphClient` hop types + optional `include_proposed` on `getThread`; `useFeatureFlag` defaults for 9 programme flags; client unit test
- **Backend (handlers/services):** `DocumentGraphService.get_thread` enrichment + walk safety; primary-parent uniqueness guard; `record_audit_event` on confirm/reject/soft-delete; route query param + actor on delete
- **APIs (endpoints changed/added):** `GET /documents/{id}/thread?include_proposed=` (additive); delete path stamps actor for audit
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `DocumentThreadHop` enriched fields; FE `DocumentThreadHop` aligned
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** Nine programme settings default false in `config.py` + client catalogue (no deploy-var flips)
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive schema fields + query param; flag defaults unchanged (master off)
- **Tolerant reader / strict writer applied?** Yes — new hop fields optional where absent docs; confirmed-only default preserves ambient honesty
- **Breaking changes:** None for flag-off clients; flag-on thread consumers gain fields (additive)
- **Migration plan:** N/A (no DB change)
- **Rollback strategy (DB):** No DB change — revert deploy / keep master flag off

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Ambient thread render without N+1 | Hop carried ids only | Hop carries title / reference / href / origin / status |
| Proposed edges on ambient thread | PROPOSED/NEEDS_REVIEW walked | Confirmed-only unless `include_proposed=true` |
| Ancestor selection | Nondeterministic `.first()` | Deterministic `order_by` edge id |
| Descendant cycles / duplicates | Unbounded revisit risk | Visited-set; each node once |
| Second primary implements parent | Allowed (ambiguous spine) | Create/confirm refuse with `DOCUMENT_GRAPH_SECOND_PRIMARY_PARENT` |
| Graph mutation attribution | Confirm/reject/delete unaudited | AuditLog on confirm / reject / soft-delete |
| Later programme flags | Would thrash config/catalogue/FE | Nine flags pre-registered default-off |
| Golden Thread vs Doc Graph | Naming risk | Unchanged — Doc Graph never called Golden Thread; ISO not stored as edges |
| Flag-off document-graph | Routes 404 | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Thread hops include `title`, `reference`, `href`, `origin`, `status` plus existing ids/depth/direction
- [x] AC-02: Default thread excludes PROPOSED/NEEDS_REVIEW; `include_proposed=true` includes them
- [x] AC-03: Second primary implements parent rejected on create and confirm; legacy duplicates ordered deterministically
- [x] AC-04: Cyclic primary graph terminates; each descendant node once
- [x] AC-05: Confirm / reject / soft-delete each write AuditLog attributed to actor
- [x] AC-06: Flag-off still 404s `/api/v1/document-graph/*`
- [x] AC-07: Nine programme flags registered default-off in config, catalogue, and `useFeatureFlag`

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (BE) — `tests/unit/test_document_graph_x0_thread_contract.py` + related Doc Graph / catalogue suites green locally (69 targeted)
- [x] Unit (FE) — `documentGraphClient.test.ts` include_proposed coverage
- [ ] Integration — CI
- [ ] Contract — CI as applicable
- [ ] E2E Smoke — staging bake when master flag enabled

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag on → get thread for a document → ancestors/descendants carry enriched hop fields; proposed parents absent unless `include_proposed=true`
- [x] CUJ-02: Flag on → attempt second primary implements parent (create or confirm) → conflict; confirm/reject/delete appear in AuditLog; flag off → thread route 404

## 7) Observability & Ops
- **Logs:** AuditLog entries `document_graph.edge_confirm|reject|delete` on `document_edge`
- **Metrics:** No new metrics in this PR
- **Alerts:** None new
- **Runbook updates:** Keep master `DOCUMENT_GRAPH_ENABLED` off until bake; programme flags stay off until their slices

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; master flag remains off unless bake enables `document_graph`; optional thread smoke with flag on in a non-prod tenant
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** ACA image tag contains tip SHA; `/health` / version; confirm flags still off unless signed enablement

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Thread walk errors with flag on; audit write failures blocking confirm/reject/delete; unexpected 409s on legitimate primary confirm
- **Rollback steps:** Set `DOCUMENT_GRAPH_ENABLED=false`; redeploy prior image / revert squash if needed
- **Owner:** Platform Engineering (Doc Graph X-0) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (enriched hop; confirmed-only; primary guard; AuditLog; flag pre-reg)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flags off until bake)
