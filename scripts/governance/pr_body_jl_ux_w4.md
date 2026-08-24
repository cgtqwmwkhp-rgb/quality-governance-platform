# Change Ledger (CL-JL-UX-W4-SYSTEM-AUDIT)

## 1) Summary
- **Feature / Change name:** JL-UX-W4 (System & audit) — process interaction **Map** over `job_cycle` links · **Trail** sample path walk on the same edge model · **mandatory-evidence** cells with derived readiness · **clone JobType pack** (axes only) · **If-Match / updated_at** optimistic concurrency with a conflict banner
- **User goal (1–2 lines):** A governance lead can see what a job cycle actually interacts with, walk one sampled path from the pack to the evidence behind it, mark the intersections that *must* hold evidence and see honestly which of them do not, stand up a new pack from an existing shape without inheriting its evidence claims, and be told plainly when someone else's edit beat theirs instead of silently overwriting it.
- **In scope:** New `job_cells.requires_evidence` column + serial migration; new shared graph module `job_lifecycle_graph.py` (nodes, edges, readiness classifier, trail sampler); new `job_lifecycle_concurrency.py` (If-Match parsing/comparison); 5 new endpoints (clone · cell requirement PATCH · evidence-readiness · audit-trail · cycle-graph); `If-Match` accepted on the three existing axis PATCHes; FE Map/Trail modes in the composer shell, per-cell requirement toggle + readiness chip, clone control, conflict banner; BE + FE tests
- **Out of scope:** W5 (baselines/versioning); portal; any flag flip; new flags; document cloning; graph *authoring* (Map and Trail are read-only views)
- **Feature flag / kill switch:** Reuses existing `job_lifecycle` / `job_cell_links` (already ON in STG/PROD via Azure). **No new flags, no Azure settings touched.** `cycle-graph` hangs off the `job_cell_links` router, so with that flag closed it 404s and the FE withholds the Map mode rather than drawing an empty one. The new column defaults `false`, so the feature is inert until a cell is explicitly marked.

## Conveyor / merge gate
- Serial programme wave **W4** of JL-UX W1–W5. Base is `origin/main` at the W3 merge tip `6b4526ab` (PR #1662).
- Admin merge allowed when Change Ledger + CI green (user directed self-automate to PROD LIVE).
- Do **not** enable additional flags as part of this PR. W5 not started.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `JobLifecycle.tsx` (Map/Trail modes in the existing view toggle, per-cell "Evidence required" toggle + derived readiness chip, unsatisfied-cell summary line, clone control in the job-cycles panel, conflict banner with a reload action, `If-Match` sent on every axis PATCH); **new** `components/jobLifecycle/JobGraphPanel.tsx` (one renderer for both Map and Trail); `jobLifecycleHelpers.ts` (view-mode availability, graph column layout, node/edge vocabulary, readiness copy/colours, `ifMatchToken`, 409 detection, conflict copy); `jobLifecycleClient.ts` (5 new calls, optional `ifMatch` write option, W4 types)
- **Backend (handlers/services):** **New** `src/domain/services/job_lifecycle_graph.py` (`JobGraphNode` / `JobGraphEdge` / `JobGraphBuilder`, `classify_cell_readiness`, `summarise_readiness`, `select_trail_cells`, depth/limit clamps — pure, no DB). **New** `src/domain/services/job_lifecycle_concurrency.py` (`job_lifecycle_etag`, `parse_if_match`, `if_match_matches`). `job_lifecycle_service.py`: `clone_job_type()`, `set_cell_requirement()`, `evidence_readiness()`, `cycle_graph()`, `audit_trail()`, `_assert_if_match()` plus read helpers (`_cells_with_axis_context`, `_documents_by_cell`, `_links_by_cell`, `_nest_link_rows`, `_live_job_type_names`, `_freshness_by_document_id`)
- **APIs (endpoints changed/added):** **Added** `POST /job-lifecycle/job-types/{id}/clone` (`job:author`), `PATCH /job-lifecycle/job-types/{id}/cells/{lane_id}/{step_id}` (`job:author`), `GET …/evidence-readiness?assure=` (`job:read`), `GET …/audit-trail?limit=&assure=` (`job:read`), `GET …/cycle-graph?depth=` (`job:read`, also gated by `job_cell_links`). **Extended** `PATCH /job-types/{id}`, `PATCH /lanes/{id}`, `PATCH /steps/{id}` — optional `If-Match` header; `JobCellResponse` gains `requires_evidence`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** 11 new schemas (`JobTypeCloneRequest/Response`, `JobCellRequirementUpdate`, `JobCellReadiness`, `JobCellReadinessItem`, `JobEvidenceReadinessResponse`, `JobGraphNodeModel`, `JobGraphEdgeModel`, `JobCycleGraphResponse`, `JobAuditTrailPath`, `JobAuditTrailResponse`); new literals `JobCellReadinessState`, `JobGraphNodeKind`, `JobGraphEdgeKind`. OpenAPI check vs the W3 tip schema: **PASSED — additive only** (5 endpoints, 11 schemas, 0 breaking)
- **Database (migrations/entities/indexes):** **One** revision `20261022_job_cell_req_ev` (`alembic/versions/20261022_job_cell_requires_evidence.py`), `down_revision = 20261021_job_nest_pdca` — single head. Adds `job_cells.requires_evidence BOOLEAN NOT NULL DEFAULT false` and index `ix_job_cells_tenant_requires_evidence (tenant_id, requires_evidence)`. **Only the requirement is stored; the readiness verdict is not** — it is derived on every read
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive. The new column has a server default of `false`, so every existing cell keeps the behaviour it had and nothing becomes "non-compliant" by deploying. `If-Match` is **opt-in**: a request without the header behaves exactly as it did before W4, so no existing client is broken by the new precondition. `requires_evidence` is optional on the FE `JobCell` type, so a payload from a pre-W4 server still reads as "not required" rather than crashing.
- **Tolerant reader / strict writer applied?** Yes. Reader: an absent `requires_evidence`, an unreadable document status, a soft-deleted nest target and an unresolvable trail node are all reported explicitly (`not_required`, `unknown`, `detail: "unavailable"`, key dropped) — never as good standing. Writer: a malformed `If-Match` is **400**, not a silent pass; a stale one is **409** naming the current `updated_at`; the clone endpoint refuses a duplicate code rather than mangling it; `depth` and `limit` are clamped server-side (`1..5`, `1..50`).
- **Breaking changes:** None
- **Migration plan:** `alembic upgrade head` applies `20261022_job_cell_req_ev`. Adding a boolean with a server default is a metadata-only change on modern Postgres — no table rewrite, no backfill, no lock of consequence on a table of this size.
- **Rollback strategy (DB):** `downgrade` drops the index then the column, and is exercised by test (`upgrade → downgrade → upgrade` on SQLite in a subprocess). Nothing else references the column, so a downgrade loses only the authored requirement flags, never any evidence — the document references live in `job_cell_documents` and the library.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| "Which cells must hold evidence?" | Not expressible | `requires_evidence` authored per cell; defaults **false** so nothing is claimed by deploying |
| Readiness verdict | N/A | **Derived on every read** — never stored, so it cannot drift from the document SSOT |
| Readiness with `assure` off | N/A | Presence only, and says so in the response and the tooltip |
| Readiness with `assure` on | N/A | An obsolete attachment **fails** the cell; an unreadable one reports `unknown`, not `ready` |
| Empty mandatory cell | Invisible | `missing_evidence`, counted in a banner an operator can act on |
| Process interaction map | Not visible | Rendered from `job_cycle` cell links only — a **view**, deleting the link deletes the edge |
| Nest target soft-deleted | Would silently vanish from the pack | Edge kept, node marked `unavailable` and made non-navigable |
| Map walk cost | N/A | Depth clamped `1..5`, one query per level, `truncated` flag when nesting continues |
| Audit trail completeness | N/A | Explicitly a **sample**: `total_candidates` + `truncated` returned so it never reads as an export |
| Trail vs composer visibility | N/A | Link edges follow the same `job_cell_links` gate as cells — the trail cannot surface links the composer hides |
| Clone semantics | N/A | Axes only. `cloned_cell_count` / `cloned_document_count` are returned as **0** rather than implied |
| Cloned evidence claims | Risk of inheriting unearned evidence | Impossible — no cell, no link and no document reference is copied |
| Concurrent axis edits | Silent last-write-wins | `If-Match` on `updated_at` → **409** with the current value; **400** if the precondition cannot be evaluated |
| Limit of that guard | N/A | Stated, not implied: the check is read-then-write, so a committer landing inside that gap is still not caught. It closes the operator-scale window (an open form), not the sub-millisecond one — a conditional UPDATE with a rowcount check would, and is not in this wave |
| Concurrency for old clients | N/A | Header optional — omitting it is the pre-W4 behaviour, unchanged |
| Refused edit in the UI | Would read as a generic failure | Distinct conflict banner naming the axis, stating the edit was **not applied**, offering a reload |
| Map when `job_cell_links` is closed | Would 404 or draw an empty graph | Mode withheld from the toggle; a stored `map` preference falls back to Matrix |
| Readiness request volume | N/A | Requested only when the pack actually has a mandatory cell |
| Alembic heads | 1 (`20261021_job_nest_pdca`) | 1 (`20261022_job_cell_req_ev`) — serial, asserted by test via Alembic's own `ScriptDirectory` |
| Feature flags | `job_lifecycle` / `job_cell_links` ON in Azure | Unchanged; no new flags; no Azure settings touched |
| OpenAPI contract | W3 baseline | Additive only — contract check PASSED |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Exactly **one** new revision, chained to `20261021_job_nest_pdca`, and it is the **only head** — asserted against Alembic's own script directory, not a regex
- [x] AC-02: `requires_evidence` is `NOT NULL DEFAULT false`; the migration upgrades, downgrades and re-upgrades cleanly; existing rows read `false`
- [x] AC-03: No readiness/verdict column is added to any `job_*` table — the verdict is derived on read and a test asserts the model carries no such field
- [x] AC-04: `assure=false` is a presence check; `assure=true` fails an obsolete attachment and reports `unknown` for a document whose standing cannot be read
- [x] AC-05: Cell **links** never satisfy a mandatory cell — only an attached library document reference does
- [x] AC-06: Marking a cell mandatory **creates** the cell if it does not exist, and attaching documents never clears the requirement
- [x] AC-07: Clone copies lanes and steps only; returns `cloned_cell_count = cloned_document_count = 0`; the new pack has no cells, no links and no document references
- [x] AC-08: Clone refuses a duplicate job-type code and copies inactive axes by default (a retired lane is part of the template's shape)
- [x] AC-09: `If-Match` matching the read `updated_at` succeeds; a stale value is **409**; a malformed value is **400**; `*` matches any live row; **no header behaves exactly as before**
- [x] AC-10: The cycle graph is built from `job_cycle` links only, dedupes nodes, keeps two edges when two cells nest the same pack, and does not loop on a revisited cycle
- [x] AC-11: Depth and limit are clamped server-side (`1..5`, `1..50`) and `truncated` is only set when the walk actually stopped at a boundary
- [x] AC-12: The trail prioritises mandatory cells over merely populated ones when truncating, and reports `total_candidates` so a sample never reads as complete
- [x] AC-13: Map and Trail share one node/edge vocabulary, and a soft-deleted nest target is shown as `unavailable` rather than dropped
- [x] AC-14: FE withholds Map when `job_cell_links` is closed (and falls back from a stored `map` preference), never issuing the request
- [x] AC-15: A 409 renders as a conflict banner naming the axis, stating the edit was not applied, with a reload that re-reads the pack; a non-409 stays in the ordinary error surface
- [x] AC-16: OpenAPI change is additive only; no new feature flags; no Azure settings changed; W5 scope untouched

## 5) Testing Evidence (link to runs)
- [x] Lint / typecheck — `black --check` clean on `src` + `tests`; `flake8` clean (0 findings); `mypy src/` clean (590 files); `eslint` clean on every changed FE file; `tsc --noEmit` clean
- [x] Unit (BE) — `tests/unit` **5935 passed, 11 skipped, 0 failed**; of which **104 new** in `tests/unit/test_job_lifecycle_ux_w4.py`
- [x] Unit (FE) — full suite **2686 passed, 0 failed** across **394 files**; of which **45 new** (22 `jobLifecycleW4Helpers` · 20 `JobLifecycleW4` · 3 `jobLifecycleClient`)
- [x] Contract — OpenAPI compatibility vs the W3 tip schema (`6b4526ab`): **PASSED**, additive only (5 endpoints, 11 schemas); `tests/contract` **437 passed, 68 skipped, 59 xfailed**
- [x] Migration — `20261022_job_cell_req_ev` driven in a subprocess against SQLite: upgrade adds the column and index, existing rows default `false`, downgrade removes both, re-upgrade succeeds
- [x] Existing-suite regression — the W3 no-migration assertion was narrowed to "no *W3* revision", not deleted, so it still fails if a W3 revision appears; W2 PATCH assertions were **tightened** to require the `If-Match` token
- [ ] E2E Smoke — staging bake after tip LIVE

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flags on → open Job Lifecycle → mark a cell **Evidence required** → it shows `No evidence` and the banner counts one unsatisfied cell → attach a library document → it reads `Ready`
- [x] CUJ-02: Turn **Freshness** on with an obsolete document attached to a mandatory cell → the cell drops to `Evidence obsolete`; a document whose status cannot be read reads `Unknown`, never `Ready`
- [x] CUJ-03: Switch to **Map** → nested cycles render from `job_cycle` links → click a nested cycle → the composer drills into it → delete the link → the edge is gone
- [x] CUJ-04: Switch to **Trail** → a sampled path walks pack → cell → document with the cell's readiness → the sample line states how many paths exist and warns when truncated
- [x] CUJ-05: Clone a pack → the new cycle has every lane and step and **no** cells, links or document references, and the composer says so
- [x] CUJ-06: Two editors rename the same lane → the second is refused **409** → the banner names the lane, says the edit was not applied, and reloading shows the other editor's version
- [x] CUJ-07: With `job_cell_links` closed, Map is not offered and no cycle-graph request is made; Trail still works

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** A **409** on an axis PATCH is intended behaviour — the row moved under the editor; reload and re-apply. A **400** on an axis PATCH mentioning `If-Match` means a client sent a precondition that could not be parsed; the fix is the client, not the data. A cell reading **Unknown** means the attached document's standing could not be read, not that the composer is broken. Map absent from the toggle means `job_cell_links` is off for that environment.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** `alembic upgrade head` → head is `20261022_job_cell_req_ev`, single head; tip SHA match; programme flags remain ON; healthz/readyz 200; CUJ-01, CUJ-03 and CUJ-06 on STG
- **Canary plan:** N/A — the schema change is one nullable-free boolean with a server default and no backfill; every new endpoint is additive and read-only except two authoring routes behind `job:author`
- **Prod post-deploy checks:** PROD tip SHA = MAIN; ACA image tag contains tip SHA; health 200; `alembic current` = `20261022_job_cell_req_ev`; Job Lifecycle loads; Map and Trail render; a marked cell reports readiness
- **Rollback trigger:** Conflict banner firing on ordinary single-editor use (would indicate an `updated_at` comparison fault); map/trail read latency on a wide pack; readiness misreporting

## 9) Rollback Plan (Mandatory)
- **Rollback steps:** Revert the squash / redeploy the prior image. If the column must also go, `alembic downgrade -1` drops the index and column; this loses only the authored requirement flags. No evidence, document reference or link is touched by either direction.
- **Rollback owner:** Platform engineering (JL-UX programme)
- **Data repair needed?** No. The only new stored state is one boolean per cell; everything else this PR shows is computed at read time.

## 10) Evidence Pack
- Local BE `tests/unit`: 5935 passed / 11 skipped / 0 failed (104 new)
- Local BE `tests/contract`: 437 passed / 68 skipped / 59 xfailed / 0 failed
- Local FE unit: 2686 passed / 0 failed across 394 files (45 new)
- OpenAPI contract check vs `6b4526ab`: PASSED (additive: 5 endpoints, 11 schemas)
- Alembic: one revision `20261022_job_cell_req_ev` on `20261021_job_nest_pdca`; single head
- Lint: black / flake8 / mypy / eslint / tsc all clean
- CI URL: (fill after PR)
- STG/PROD tip verify: (post-merge conveyor)

## Gate Checklist
- [x] Gate 0 — Change Ledger complete
- [x] Gate 1 — Scope held (W4 only, no W5, no new flags, no Azure changes)
- [x] Gate 2 — Compatibility additive; one serial migration; single head; downgrade tested
- [x] Gate 3 — AC + CUJ covered
- [ ] Gate 4 — CI green on PR
- [ ] Gate 5 — STG then PROD tip LIVE + health
