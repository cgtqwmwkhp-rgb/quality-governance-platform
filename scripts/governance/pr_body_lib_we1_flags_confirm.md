# Change Ledger (CL-LIB-WE1-FLAGS-CONFIRM-QUEUE)

## 1) Summary

- **Feature / Change name:** Library Northern Star W7 / WE-1 — Doc Graph edges
  reach the Knowledge Exceptions queue, and every graph flag joins the governed
  deploy path
- **User goal (1–2 lines):** A reviewer who opens **AI Exceptions** sees the
  document↔document relationships a machine proposed and can confirm or reject
  them there, instead of having to know which document's Related tab to open.
  Nothing about the graph is enabled by a hand-set Azure app setting any more.
- **In scope:**
  - `GET /api/v1/document-graph/edges/pending` — tenant-wide proposed /
    needs_review edge queue (`DocumentGraphService.list_pending_edges`), gated by
    the existing master `document_graph` dependency.
  - `frontend/src/pages/KnowledgeExceptions.tsx` — a "Document relationship
    proposals" section on the **existing** page, acting through the existing
    `confirmEdge` / `rejectEdge` routes.
  - Four Doc Graph subflags (`THREAD_AMBIENT`, `MAP_VIEW`, `DND_PROPOSE`,
    `STRUCTURE_MAP`) added to both deploy workflows, `scripts/infra/env-vars.json`
    and `.env.example`, with matching repo variables set to `true`.
- **Out of scope (deferred, see §3):** bulk confirm on the Exceptions page (the
  per-document Related queue already has it), a reject-rationale prompt for
  graph edges, ISO/clause edges (`Implements → standard` stays CEL), any
  Documents-360 or twin Confirm Queue route, and regenerating the ungated
  `docs/contracts/openapi.json` snapshot.
- **Feature flag / kill switch:** Master `DOCUMENT_GRAPH_ENABLED` /
  client `document_graph`. The new route 404s when it is closed; the new UI
  section renders nothing and issues no request. Both are **already `true`** in
  STG and PROD (evidence in §10), so this ships visible.

## 2) Impact Map (what changed)

- **Frontend:** `KnowledgeExceptions.tsx` gains a flag-gated
  `GraphProposalsQueue` section; new pure helpers in
  `pages/knowledgeExceptionsGraphQueue.ts`; `api/documentGraphClient.ts` gains
  `listPendingEdges` plus its response types. No route added, no page added, no
  nav entry added.
- **Backend:** `DocumentGraphService.list_pending_edges` (+ `PENDING_EDGE_STATUSES`,
  `PENDING_QUEUE_LIMIT`, ACL-aware endpoint enrichment). No new service, no new
  model, no new table.
- **APIs:** `GET /api/v1/document-graph/edges/pending` (additive). Query:
  `edge_type?`, `status?` (`proposed|needs_review` only), `limit?` (≤200).
  Requires `document:read`. Confirm/reject remain
  `POST /edges/{id}/confirm|reject` with `document:confirm_edge`.
- **Database:** None. `document_edges` is already the source of truth and nothing
  is copied into `compliance_evidence_links`.
- **Config/env/flags:** `DOCUMENT_GRAPH_THREAD_AMBIENT_ENABLED`,
  `DOCUMENT_GRAPH_MAP_VIEW_ENABLED`, `DOCUMENT_GRAPH_DND_PROPOSE_ENABLED`,
  `DOCUMENT_GRAPH_STRUCTURE_MAP_ENABLED` added to `deploy-staging.yml` and
  `deploy-production.yml` (API and Celery blocks), `scripts/infra/env-vars.json`
  and `.env.example`. Repo variables set to `true` **before** merge so the first
  deploy that reads them cannot close a flag that is currently open.
- **Dependencies:** None.
- **Tests:** `tests/unit/test_document_graph_we1_confirm_queue.py` (12),
  `tests/unit/test_document_graph_flag_deploy_persistence.py` (36),
  `frontend/src/pages/__tests__/KnowledgeExceptionsGraphQueue.test.tsx` (15).
  The existing `KnowledgeExceptions.test.tsx` client mock was extended with
  `documentGraphApi` — no assertion changed or removed.
- **Docs:** Rationale lives in the service, route, helper and test docstrings.
- **Contract baseline:** One added path and three added schemas; nothing existing
  changed or removed (`check_openapi_compatibility.py` run below).

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Purely additive. The Doc Graph queue is a second
  *reader* of `document_edges`, not a second writer and not a second source of
  truth. CEL evidence links keep their own list, their own ids and their own
  confirm/reject routes; the two queues sit on one page and never share a row.
- **Breaking changes:** None.
- **Migration plan:** No migration.
- **Rollback strategy (DB):** Not applicable.

### The config gap this closes

`az webapp config appsettings set` **merges**. A flag typed into the portal by
hand therefore survives deploy after deploy and looks durable. It is not: it
exists in no repository file, no repo variable and no workflow, so a reprovision
or a settings replacement drops it and the surface changes with nothing to point
at. That was exactly the state of the four subflags — live and `true` in STG and
PROD while the repo believed the platform default (`false`).
`test_document_graph_flag_deploy_persistence.py` is what keeps every Doc Graph
flag on the governed path from here, and what stops one being welded open with a
literal `'true'` instead of staying a kill switch.

### Honest deferrals

| Concern | State after this PR |
| --- | --- |
| Restricted document titles | **Enforced.** A tenant-wide queue would otherwise show titles that `GET /documents/{id}` refuses to the same operator. Each endpoint is checked against `user_can_read_library_document` (taxonomy ids batch-loaded, not per row); when it denies, title and reference are withheld and `readable: false` is returned. The id and deep-link stay so the operator can ask for access. |
| A proposal between two documents the reviewer cannot read | **Shown but not actionable.** Hiding it would understate the queue; offering Confirm would invite a blind decision. The row explains why there is no button. |
| Page counts | **Honest.** The service fetches one row beyond the page purely to distinguish a full page from a cut one, and returns `truncated`. The UI says "page of up to 200 — not a global total", or names the cut. |
| Zero vs unavailable | **Distinguished.** A 404 (master flag closed on the API) and a failed read each get their own copy; neither is allowed to render as "nothing pending". |
| Bulk confirm on this page | **Deferred.** `documentGraphApi.confirmEdges` already exists and the per-document Related queue uses it. Adding a second bulk surface in the same PR as the first list would double the review surface for no new capability. |
| Reject rationale on graph edges | **Deferred, deliberately.** CEL *bulk* reject demands one; CEL single reject and the Related queue's reject do not. This page now mirrors the Related queue exactly rather than inventing a third policy for the same API call. `AuditLog` records the rejection and actor either way. |
| Confirming an already-confirmed edge | **Pre-existing, not fixed here.** `DocumentGraphService.confirm` re-stamps `confirmed_by_id` / `confirmed_at` rather than refusing, so acting on a stale page can re-attribute a confirmation. The Related queue has always shared this; fixing it on one caller would leave the two inconsistent. |
| `docs/contracts/openapi.json` | **Not regenerated.** No CI job reads it, and refreshing it here would bury a small diff under an unrelated snapshot. |
| Live API/worker parity assertion | **Deferred.** `deploy-production.yml` asserts post-deploy parity for `COMPLIANCE_SCHEDULE_ENABLED` only. Doc Graph flags are now *written* to both apps and pinned by test; extending the post-deploy *read* assertion to more flags is its own change. |

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Reviewing machine-proposed relationships | Only reachable per document, via Related on a document you already knew to open | Also listed tenant-wide on the existing Exceptions inbox |
| Source of truth for edges | `document_edges` | `document_edges` — unchanged; the queue reads, never mirrors |
| `Implements → standard` | CEL evidence links | CEL evidence links (untouched; no `document_edges` row expresses a clause) |
| AI auto-confirm of impact-driving edges | Refused in `create_edge` | Still refused; the queue additionally *labels* which proposals will drive publish impact once a person confirms them |
| Restricted library titles in aggregate lists | Per-document ACL enforced on the by-id route | Also enforced on the tenant-wide queue, with withheld fields stated rather than blank |
| Graph subflag provenance | Four flags lived only as hand-set Azure app settings | All six resolve from repo variables through both deploy workflows, default closed, registered in `env-vars.json` and `.env.example`, pinned by test |
| Confirm posture | List/queue on Related | Unchanged — list/queue on Related **and** on Exceptions. Structure Map stays read-only behind its own flag and is never the confirm surface |

## 4) Acceptance Criteria (AC)

- [x] AC-01: `GET /document-graph/edges/pending` returns only live
  `proposed` / `needs_review` edges for the caller's tenant, and refuses a
  settled status with `DOCUMENT_GRAPH_NOT_PENDING_STATUS` rather than silently
  substituting the pending set.
- [x] AC-02: The queue reports `truncated` when a page is cut and never presents
  a page as a global total.
- [x] AC-03: A document the caller may not read contributes no title and no
  reference, and the proposal offers no confirm/reject when *neither* end is
  readable.
- [x] AC-04: The route 404s while `DOCUMENT_GRAPH_ENABLED` is closed, and the UI
  section renders nothing and issues no request while the client flag is closed.
- [x] AC-05: Confirm and reject on the Exceptions page call the existing
  `POST /edges/{id}/confirm` and `POST /edges/{id}/reject` — no new mutation
  route, and no CEL row is written.
- [x] AC-06: Impact-driving proposals (`implements`, `requires_record`,
  `conflicts_with`) are labelled as such before a person confirms them.
- [x] AC-07: A closed flag and a failed read are each distinguished from an empty
  queue in the UI.
- [x] AC-08: All six `DOCUMENT_GRAPH_*` flags are written by both deploy
  workflows from their repo variable, default `false`, and are registered in
  `env-vars.json` and `.env.example` — asserted by test.
- [x] AC-09: Related on Document Detail renders the relationships panel whenever
  the master flag is on, with no subflag able to hide it. **Verified, not
  changed** — the Related tab trigger is unconditional and the panel is gated on
  `useFeatureFlag('document_graph')` alone; the pre-existing
  `DocumentDetailLayers.test.tsx` already pins both the on and off branches, so
  there was no gate left to fix.
- [x] AC-10: Map stays demoted — `resolveRelationshipsPanelView` returns `list`
  unless the operator asks for the map, the map renders confirmed edges only,
  and Structure Map remains a separate read-only flagged page.
- [x] AC-11: One decision is in flight at a time across the graph queue — the
  same posture as the CEL rows above it — so a second click cannot be aimed at a
  list the reload is about to replace.

## 5) Testing Evidence (link to runs)

- [x] `tests/unit/test_document_graph_we1_confirm_queue.py` — 12 passed
- [x] `tests/unit/test_document_graph_flag_deploy_persistence.py` — 36 passed
- [x] `tests/unit/test_deploy_workflow_flag_parity.py` — 9 passed (unchanged)
- [x] `pytest tests/unit -k "document_graph or governed_knowledge or feature or catalogue or page_registry"` — 266 passed
- [x] `pages/__tests__/KnowledgeExceptionsGraphQueue.test.tsx` (15) +
  `pages/__tests__/KnowledgeExceptions.test.tsx` +
  `pages/__tests__/DocumentDetailLayers.test.tsx` +
  `pages/__tests__/DocumentRelationshipsPanel.test.tsx` (22) — 57 passed;
  `components/graph/__tests__/relationshipsMapHelpers.test.ts` — 4 passed
- [x] `tsc --noEmit` clean; `eslint` clean on changed frontend files
- [x] `black --check` / `isort --check-only` / `flake8` clean; `mypy` clean on the
  changed backend modules
- [x] `scripts/check_openapi_compatibility.py openapi-baseline.json <generated>` —
  PASSED, additive only. This PR adds
  `/api/v1/document-graph/edges/pending`, `PendingEdgeEndpoint`,
  `PendingDocumentEdgeItem`, `PendingDocumentEdgeListResponse`. The run also
  reports `/api/v1/documents/{document_id}/issue` + `LibraryIssueRequest` as
  additive — those predate this branch and are baseline lag, not a change here.
- [x] `yaml.safe_load` on both deploy workflows; actionlint clean apart from
  pre-existing `SC2129` style notes that CI already ignores
- [ ] Full CI — on PR
- [ ] Staging / Prod — tip chase after merge per conveyor

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: A reviewer opens AI Exceptions, sees a proposed `implements` link
  between two named documents, is told confirming it will drive publish impact,
  confirms it, and the queue reloads without it.
- [x] CUJ-02: The same reviewer rejects a proposal; the existing reject route is
  called and the edge leaves the queue.
- [x] CUJ-03: A reviewer without access to either document sees the proposal
  exists, sees both ends named as unavailable to them, and is given no
  confirm/reject.
- [x] CUJ-04: With Doc Graph closed, AI Exceptions behaves exactly as it did —
  CEL evidence links only, no extra section, no extra request.
- [x] CUJ-05: A reader opens a document's Related tab and still gets the
  relationships panel and its own confirm queue; the Exceptions queue did not
  replace it.

## 7) Observability & Ops

- Confirm and reject continue to write `document_graph.edge_confirm` /
  `edge_reject` `AuditLog` events with actor, previous status and both endpoint
  ids, so a confirmation made from Exceptions is indistinguishable in the record
  from one made on Related — which is correct: it is the same decision.
- The queue is a read; it emits no new event and no new metric. `truncated` is
  the operational signal worth watching, and it is on the response and on screen.
- Refusals keep the standard envelope: `404` while the flag is closed
  (`Doc Graph is not enabled in this environment.`), `422`
  `DOCUMENT_GRAPH_NOT_PENDING_STATUS` for a settled status filter, `403` from the
  permission dependency.
- No new alert. A brand-new read on an existing surface has no baseline to alert
  against on day one.

## 8) Release Plan

1. Repo variables `DOCUMENT_GRAPH_THREAD_AMBIENT_ENABLED`,
   `DOCUMENT_GRAPH_MAP_VIEW_ENABLED`, `DOCUMENT_GRAPH_DND_PROPOSE_ENABLED`,
   `DOCUMENT_GRAPH_STRUCTURE_MAP_ENABLED` set to `true` **before** merge, so the
   first deploy that reads them writes the values already live (§10).
2. Merge to `main`; `CI - Default` green on the tip SHA.
3. `Build, Push and Deploy to Azure` green for that SHA. No migration.
4. Verify the ACA/App Service image tag contains the tip SHA and the prod FQDN is
   healthy, then confirm the six `DOCUMENT_GRAPH_*` app settings are still `true`
   after the deploy has rewritten them.
5. Nothing to enable: both master and subflags are already open, so the queue is
   visible on the first request after deploy.

## 9) Rollback Plan (Mandatory)

- **Trigger:** the Exceptions page misreports the graph queue, confirm/reject
  from Exceptions behaves differently from Related, restricted titles appear to
  an operator who should not see them, or a deploy closes a graph flag that
  should be open.
- **Rollback steps:**
  1. Fastest partial: `gh variable set DOCUMENT_GRAPH_ENABLED --body false` and
     redeploy — the route 404s, the UI section disappears, and the whole Doc
     Graph surface closes with it. Use a subflag variable instead to close only
     ambient/map/DnD/structure-map.
  2. Full: revert the merge commit and let the governed CI/deploy path put the
     previous image live. No schema to unwind.
  3. If a subflag was wrongly closed by the new workflow lines, set its repo
     variable to `true` and redeploy; breakglass `az webapp config appsettings
     set` is recovery only and must be followed by fixing the variable.
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack

**Graph flags verified live before this PR (verify-only, nothing flipped):**

```
$ az webapp config appsettings list --name qgp-staging-plantexpand \
    --resource-group rg-qgp-staging --query "[?starts_with(name,'DOCUMENT_GRAPH')]"
DOCUMENT_GRAPH_ENABLED                  true
DOCUMENT_GRAPH_HEURISTIC_PROPOSE_ENABLED true
DOCUMENT_GRAPH_THREAD_AMBIENT_ENABLED   true
DOCUMENT_GRAPH_MAP_VIEW_ENABLED         true
DOCUMENT_GRAPH_DND_PROPOSE_ENABLED      true
DOCUMENT_GRAPH_STRUCTURE_MAP_ENABLED    true

$ az webapp config appsettings list --name app-qgp-prod \
    --resource-group rg-qgp-staging --query "[?starts_with(name,'DOCUMENT_GRAPH')]"
DOCUMENT_GRAPH_ENABLED                  true
DOCUMENT_GRAPH_HEURISTIC_PROPOSE_ENABLED true
DOCUMENT_GRAPH_THREAD_AMBIENT_ENABLED   true
DOCUMENT_GRAPH_MAP_VIEW_ENABLED         true
DOCUMENT_GRAPH_DND_PROPOSE_ENABLED      true
DOCUMENT_GRAPH_STRUCTURE_MAP_ENABLED    true
```

Repo variables before: only `DOCUMENT_GRAPH_ENABLED` and
`DOCUMENT_GRAPH_HEURISTIC_PROPOSE_ENABLED` existed — the other four live flags
had no governed owner. All six are now repo variables set `true`.

- Authority: `docs/adr/ADR-0021-document-relationship-graph.md` (propose →
  confirm; no AI auto-confirm of impact-driving edges),
  `docs/adr/ADR-0023-governance-library-reference-scheme.md` (no twin Confirm
  Queue / Documents-360 surface)
- Precedent for flag persistence through deploy vars:
  `scripts/governance/pr_body_doc_graph_flag_persist.md`
- Existing confirm queue this one mirrors:
  `frontend/src/pages/DocumentRelationshipsPanel.tsx`
  (`relationships-confirm-queue`)
- Master plan canvas: `library-v6-northern-star-master-plan`, wave W7
  (`config/deploy · exceptions`)

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger; deferrals named in §3 rather
  than implied
- [x] **Gate 1:** No twin SoT and no twin surface — `document_edges` stays the
  only home for graph edges, `Implements → standard` stays CEL, and the queue
  lives on the existing `/knowledge-exceptions` page with no new route, page or
  nav entry (ADR-0023)
- [ ] **Gate 2:** CI green on the PR
- [x] **Gate 3:** Behaviour verified locally — backend unit suites, frontend
  suites, typecheck, lint, contract compatibility; live flag state verified
  against both Azure environments
- [x] **Gate 4:** No migration, no data change, no backfill
- [ ] **Gate 5:** DONE = tip LIVE after merge — not claimed here
