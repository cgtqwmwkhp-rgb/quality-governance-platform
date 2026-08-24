# Change Ledger (CL-JL-UX-W3-ASSURE)

## 1) Summary
- **Feature / Change name:** JL-UX-W3 (Assure) — Freshness toggle on the Job Lifecycle composer · obsolete-on-attach enforcement · audit-lapse cues on `audit_outcome` links · GraphCoach freshness tip
- **User goal (1–2 lines):** An operator can flip one toggle to see the *real* Library / Document Control status of every document on the tray and in every matrix cell, is stopped from attaching a withdrawn document, and can see at a glance whether an attached audit outcome is still in date — with an honest "Unknown" wherever the data does not actually say.
- **In scope:** New classifier module `job_lifecycle_freshness.py`; bulk `GET /job-lifecycle/document-freshness`; obsolete enforcement on cell-document PUT (newly added ids only); `audit_lapse` on `JobCellLinkResponse` for `audit_outcome` links; FE freshness toggle + tray/cell chips + client-side obsolete pre-flight; audit-lapse chip in the cell and in the step links panel; one extra `job_lifecycle` GraphCoach step; BE + FE tests
- **Out of scope:** Clone / map / trail / baselines (W4–W5); portal; flag flips; new flags; **no migration**
- **Feature flag / kill switch:** Reuses existing `job_lifecycle` / `job_cell_links` (already ON in STG/PROD via Azure). **No new flags, no Azure settings touched.** The freshness endpoint hangs off the same flag-gated router, so flag-off keeps it 404. The toggle itself is a client-side preference in `localStorage`, defaulting **off** — the composer opens calm.

## Conveyor / merge gate
- Serial programme wave **W3** of JL-UX W1–W5. Base is `origin/main` **after** W2 (#1661) merged — branch tip parent is `59e609bc`.
- Admin merge allowed when Change Ledger + CI green (user directed self-automate to PROD LIVE).
- Do **not** enable additional flags as part of this PR. W4/W5 not started.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `JobLifecycle.tsx` (Freshness toggle in the header, freshness chips on tray docs and in-cell doc refs, lazy batched status fetch, audit-lapse chip on in-cell `audit_outcome` links, client-side obsolete drop refusal, explicit error line when the status lookup fails); `JobCellLinks.tsx` (audit-lapse chip in the step links panel); `jobLifecycleHelpers.ts` (toggle persistence, freshness index build/merge, id collection with cap, obsolete pre-flight, chip vocabulary for both cues); `jobLifecycleClient.ts` (`listDocumentFreshness`, `audit_lapse` types); `coachSteps/jobLifecycle.ts` (new "Check freshness" step)
- **Backend (handlers/services):** **New** `src/domain/services/job_lifecycle_freshness.py` (`classify_document_freshness`, `classify_audit_lapse` — pure functions, no DB). `job_lifecycle_service.py`: `document_freshness()` bulk lookup, `_controlled_documents_by_library_id()` (strictest doc-control record wins), `_assert_no_obsolete_attachments()`, `_audit_lapse_map()` prefetch, `_find_cell()` read-only cell lookup, `serialize_cell_link()` now takes a prefetched lapse map
- **APIs (endpoints changed/added):** **Added** `GET /api/v1/job-lifecycle/document-freshness?library_document_ids=…` (`job:read`, repeated id params, capped at 200). **Extended** `PUT /job-lifecycle/{job_type_id}/cells/{lane_id}/{step_id}/documents` — now **422** when a *newly added* id is obsolete. `JobCellLinkResponse` (returned by cell list, link list and link create) gains a read-only `audit_lapse`.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** New `JobDocumentFreshnessItem`, `JobDocumentFreshnessResponse`, `JobCellLinkAuditLapse`; new literals `JobDocumentFreshnessState` (`current|due_soon|overdue|obsolete|unknown`) and `JobAuditLapseState` (`current|due_soon|lapsed|unknown`). OpenAPI contract check vs the W2 tip schema: **PASSED — additive only** (1 new endpoint, 3 new schemas, 0 breaking).
- **Database (migrations/entities/indexes):** **None.** No new revision, no model change, no index. `alembic` head stays `20261021_job_nest_pdca` (single head). Freshness is **derived on read** from `documents` / `controlled_documents` and audit lapse from `audit_runs` / `audit_templates` — a test asserts nothing freshness-shaped is persisted on any `job_*` table.
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Purely additive. `audit_lapse` is optional and only populated for `audit_outcome` links; every existing client ignoring it is unaffected. The freshness endpoint is new. The only behaviour change to an existing route is the obsolete refusal on cell-document PUT, and that refusal is **scoped to ids the request is adding** — it cannot break a PUT that only removes or reorders.
- **Tolerant reader / strict writer applied?** Yes. Reader: an absent `audit_lapse`, an absent freshness verdict, a missing review date, an unrecognised cadence and a document the tenant cannot see all render as **Unknown** — never as good standing. Writer: `library_document_ids` beyond 200 is refused with 422 rather than silently truncated, and the obsolete refusal names the offending document id and the status that withdrew it. `audit_lapse` is server-computed and read-only, so it is registered in `SERVER_OWNED_FIELDS` for the response/request symmetry guard rather than being added to any writer.
- **Breaking changes:** None
- **Migration plan:** **None — no revision added.** A test (`test_w3_adds_no_alembic_revision_after_the_w2_head`) fails the build if a W3 revision appears after `20261021_job_nest_pdca`.
- **Rollback strategy (DB):** N/A — no schema change. Code-only revert.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Document status in the composer | Invisible — the tray dropped `status`/`review_date` on ingest | Retained on ingest and rendered from the server verdict when the toggle is on |
| Freshness SSOT | Would drift if cached on job tables | Derived per request from `documents` + `controlled_documents`; **nothing persisted on `job_*`** — asserted by test |
| Conflicting doc-control records | Undefined | Strictest wins: obsolete beats non-obsolete, then earliest review date |
| Obsolete attachment | Allowed silently | **Blocked 422** server-side, refused client-side before the call; message names the withdrawing status |
| Obsolete already attached | N/A | Stays removable — enforcement covers newly added ids only, so an operator is never trapped |
| Withdrawn vocabulary | Ad hoc | `obsolete`/`superseded`/`retired`/`archived`, case- and enum-insensitive, on both the library and doc-control sides |
| Audit standing on a link | Not shown | `audit_lapse` from run completion + template cadence; `ad_hoc` and unknown cadences read **Unknown**, never "in date" |
| Audit lapse query cost | Would be N+1 across a whole matrix | Prefetched in **one** query per list call and passed in as a map — `serialize_cell_link` never queries |
| "No data" presentation | Would default to reassuring | Explicitly `unknown` with a reason string, styled unlike `current`, and an error line when the lookup itself fails |
| Composer calm by default | N/A | Toggle defaults **off**; an unrecognised stored value is treated as no preference, not as on |
| Freshness request volume | N/A | Only fetches ids it has no verdict for; capped at 200 with cell refs prioritised over tray page |
| Alembic heads | 1 (`20261021_job_nest_pdca`) | 1 (`20261021_job_nest_pdca`) — **unchanged, no W3 revision** |
| Feature flags | `job_lifecycle` / `job_cell_links` ON in Azure | Unchanged; no new flags; no Azure settings touched |
| OpenAPI contract | W2 baseline | Additive only — contract check PASSED |
| Write-contract round-trip | Baseline | `audit_lapse` declared server-owned (read-only) rather than growing `KNOWN_UNREADABLE_REQUEST_FIELDS` |

## 4) Acceptance Criteria (AC)
- [x] AC-01: **No alembic revision added**; head remains `20261021_job_nest_pdca`, single head — asserted by test
- [x] AC-02: Freshness is never persisted on a `job_*` table; it is classified per request from the document tables — asserted by test
- [x] AC-03: Toggle defaults **off** (calm composer), round-trips through `localStorage`, survives storage that throws, and treats an unrecognised stored value as "no preference"
- [x] AC-04: Toggle **on** requests status for the tray page **and** the ids already attached to cells, and does not re-request ids it already holds
- [x] AC-05: Tray ingest retains `status` / `review_date` instead of dropping them
- [x] AC-06: A document with no verdict renders **Unknown**, styled unlike `current`; a failed lookup shows an explicit error rather than a wall of green
- [x] AC-07: Every withdrawn library status reads as obsolete; a doc-control `obsolete` beats an `approved` library row; obsolescence beats an overdue review date
- [x] AC-08: Review-date windows classify `current` / `due_soon` (30d) / `overdue`; doc-control `next_review_date` is preferred over the library date; naive dates are read as UTC, not crashed on
- [x] AC-09: Attaching an obsolete document is refused **422** with the withdrawing status named; refused client-side before the API call, with freshness on *or* off
- [x] AC-10: Enforcement covers **newly added ids only** — an already-attached obsolete doc stays removable, clearing a cell is never blocked, and the guard never creates a cell before it has passed
- [x] AC-11: `audit_lapse` is attached only from a prefetched map (one query per list call), is `None` when the run is absent, and never appears on non-`audit_outcome` links
- [x] AC-12: An `ad_hoc` audit and an unrecognised cadence report **Unknown**, not a guessed cadence; a completed audit lapses once its cadence elapses; a short cadence is not permanently "due soon"
- [x] AC-13: Freshness returns **one item per requested id in the order requested** — an id the tenant cannot see is reported `unknown`/`document_not_found`, not dropped; an oversized list is refused, not truncated; an empty request touches no database
- [x] AC-14: OpenAPI change is additive only; `audit_lapse` passes the response/request symmetry guard as a server-owned field
- [x] AC-15: No new feature flags, no Azure settings changed, W4/W5 scope untouched

## 5) Testing Evidence (link to runs)
- [x] Lint / typecheck — `flake8` clean on `src` + `tests`; `mypy` clean on all four changed BE modules; `eslint` clean on every changed FE file; `tsc --noEmit` clean
- [x] Unit (BE) — `tests/unit` **5832 passed, 10 skipped, 0 failed**; of which **48 new** in `tests/unit/test_job_lifecycle_ux_w3.py`
- [x] Unit (FE) — full suite **2641 passed, 0 failed** across **392 files**; of which **43 new** (23 `jobLifecycleW3Helpers` · 13 `JobLifecycleW3` · 5 `JobCellLinksW3` · 2 `jobLifecycleClient`)
- [x] Contract — OpenAPI compatibility vs the W2 tip schema: **PASSED**, additive only (`/job-lifecycle/document-freshness`, `JobDocumentFreshnessResponse`, `JobDocumentFreshnessItem`, `JobCellLinkAuditLapse`); `tests/contract` **435 passed, 68 skipped**
- [x] Route shadowing guard — **26 passed**; `/document-freshness` is reachable and not swallowed by a sibling path parameter
- [x] Combined `tests/unit` + `tests/contract` — **6267 passed, 78 skipped, 0 failed**
- [x] Migration — N/A, none added (asserted)
- [ ] E2E Smoke — staging bake after tip LIVE

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag on → open Job Lifecycle → composer is calm, no chips, no status request → flip **Freshness** → tray and cell chips populate from the server → reload → the choice is remembered
- [x] CUJ-02: Drag an obsolete document onto a cell → refused in the composer, **no API call made** → same refusal with the toggle off → an overdue-but-current document still attaches
- [x] CUJ-03: Attach an obsolete document the client had no status for → server refuses 422 and the composer surfaces the reason
- [x] CUJ-04: Open a step's links panel with an `audit_outcome` link → lapse cue reflects the server verdict; an ad-hoc audit reads **Unknown**, not "in date"; non-audit links carry no cue
- [x] CUJ-05: Status lookup fails → composer says so instead of rendering everything as fine
- [x] CUJ-06: GraphCoach on `job_lifecycle` now offers the freshness tip alongside the existing steps

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** A **422** on cell-document PUT mentioning obsolete documents is intended behaviour — the fix is in the Library / Document Control record, not in the composer. A chip reading **Unknown** means the underlying record has no readable review date or cadence; it is not a composer fault. If operators see 403 with flags ON, grant `job:read` / `job:author` (unchanged from W1).

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** No migration to apply — head stays `20261021_job_nest_pdca`. Tip SHA match; programme flags remain ON; healthz/readyz 200; CUJ-01 and CUJ-02 on STG
- **Canary plan:** N/A — no schema change, no backfill; the only existing-route behaviour change is a refusal that is unreachable unless an obsolete document is being added
- **Prod post-deploy checks:** PROD tip SHA = MAIN; ACA image tag contains tip SHA; health 200; migration still at `20261021_job_nest_pdca`; Job Lifecycle loads, freshness toggle round-trips, obsolete attach refused

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Obsolete enforcement blocking legitimate attachments; freshness lookup latency on large packs; misleading lapse verdicts
- **Rollback steps:** Revert the squash / redeploy the prior image. No DB downgrade exists or is needed — nothing was migrated. Operators can also simply leave the toggle off, which restores the W2 composer exactly.
- **Rollback owner:** Platform engineering (JL-UX programme)
- **Data repair needed?** No — nothing is written by this change. Freshness and lapse are computed on read.

## 10) Evidence Pack
- Local BE `tests/unit`: 5832 passed / 10 skipped / 0 failed (48 new)
- Local BE `tests/contract`: 435 passed / 68 skipped / 0 failed
- Local FE unit: 2641 passed / 0 failed across 392 files (43 new)
- OpenAPI contract check: PASSED (additive: 1 endpoint, 3 schemas)
- Route shadowing guard: 26 passed
- Alembic: no revision added; single head `20261021_job_nest_pdca`
- CI URL: (fill after PR)
- STG/PROD tip verify: (post-merge conveyor)

## Gate Checklist
- [x] Gate 0 — Change Ledger complete
- [x] Gate 1 — Scope held (W3 only, no W4/W5, no new flags, no Azure changes)
- [x] Gate 2 — Compatibility additive; no migration; single head unchanged
- [x] Gate 3 — AC + CUJ covered
- [ ] Gate 4 — CI green on PR
- [ ] Gate 5 — STG then PROD tip LIVE + health
