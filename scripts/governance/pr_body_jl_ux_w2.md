# Change Ledger (CL-JL-UX-W2-NESTING-PDCA)

## 1) Summary
- **Feature / Change name:** JL-UX-W2 — Job cycle nesting (`job_cycle`) · PDCA phases on steps · axis reorder/rename · breadcrumb drill-in/out
- **User goal (1–2 lines):** Operators can nest any Job cycle inside any other from a matrix cell, drill in/out via a breadcrumb, colour steps by PDCA phase, and reorder/rename lanes and steps in place — with nesting shown on lanes as a chip derived from the links themselves.
- **In scope:** Alembic `20261021_job_nest_pdca` (widen `ck_job_cell_links_kind` to `job_cycle`; nullable `target_job_type_id` FK → `job_types`; `pdca_phase` on `job_steps`); models/schemas/service/routes for `job_cycle` + BFS acyclic guard; `href_registry` registers `job_type`; thin `GET /job-lifecycle/link-entity-types`; Entity360 `JobLifecycleProducer` nest hops both ways + `job_type` entity; FE nesting picker, PDCA colours, breadcrumb, derived lane chip, axis reorder/rename; BE + FE tests
- **Out of scope:** Clone, map, trail, freshness/obsolete, baselines (W3–W5); portal; flag flips; new flags
- **Feature flag / kill switch:** Reuses existing `job_lifecycle` / `job_cell_links` (already ON in STG/PROD via Azure). **No new flags.** Flag-off keeps every touched route 404.

## Conveyor / merge gate
- Serial programme wave **W2** of JL-UX W1–W5. Base is `origin/main` **after** W1 (#1660) merged — branch tip parent is `91346d795`.
- Admin merge allowed when Change Ledger + CI green (user directed self-automate to PROD LIVE).
- Do **not** enable additional flags as part of this PR.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `JobLifecycle.tsx` (breadcrumb drill-in/out, PDCA colouring, lane/step rename + reorder, derived nest chip, in-cell nest chip navigation); `JobCellLinks.tsx` (`job_cycle` kind + Job cycle picker, entity-type dropdown from registry); `jobLifecycleHelpers.ts`, `jobCellLinksHelpers.ts`, `jobLifecycleClient.ts`; `App.tsx` route `/job-lifecycle/cycles/:jobTypeId`
- **Backend (handlers/services):** `job_lifecycle_service.py` (`job_cycle` validation, `_assert_nestable_job_cycle`, `would_create_job_cycle_nest_cycle` BFS, `nested_job_type_ids`, `pdca_phase` create/update incl. explicit clear, `list_link_entity_types`); `href_registry.py`; `entity_360/producers/job_lifecycle.py`; `entity_360/permissions.py`
- **APIs (endpoints changed/added):** **Added** `GET /api/v1/job-lifecycle/link-entity-types` (`job:read`). **Extended** `POST /job-lifecycle/cells/{cell_id}/links` (accepts `target_job_type_id`), `POST`/`PATCH` job steps (accept `pdca_phase`, `pdca_phase_set`). Axis reorder/rename reuse the **existing** PATCH lane/step endpoints — no new routes for those.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `JobCellLinkKind` gains `job_cycle`; new `JobStepPdcaPhase` literal; `target_job_type_id` on link create/response; `pdca_phase` on step create/update/response; new `JobLinkEntityTypesResponse`. OpenAPI contract check: **PASSED, additive only, no breaking changes.**
- **Database (migrations/entities/indexes):** `20261021_job_nest_pdca` revises `20261020_job_cell_links` — widened `ck_job_cell_links_kind`; `job_cell_links.target_job_type_id` (nullable, FK `job_types.id` `ON DELETE CASCADE`); index `ix_job_cell_links_tenant_target_type`; `job_steps.pdca_phase` (nullable) + `ck_job_steps_pdca_phase`. No new table → `RLS_TABLES` / `HARDENING_MIGRATIONS` unchanged (`job_cell_links` already FORCE RLS from JL-3).
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Purely additive. `target_job_type_id` and `pdca_phase` are nullable; existing `job_cell_links` rows and `job_steps` rows are untouched. Widening a CHECK constraint cannot invalidate existing data. Old clients that never send the new fields keep working.
- **Tolerant reader / strict writer applied?** Yes — reader tolerates `pdca_phase = NULL` (renders "none"); writer is strict: `job_cycle` links **require** `target_job_type_id` and **reject** the other kinds' target fields, and `pdca_phase` is validated against `plan|do|check|act`.
- **Breaking changes:** None
- **Migration plan:** Single revision `20261021_job_nest_pdca` revises `20261020_job_cell_links` — extends the JL chain, never parallel. `alembic heads` = **one** head. Verified on a scratch Postgres by applying the full chain and asserting column nullability, constraint definitions, CHECK enforcement (invalid `pdca_phase` rejected, valid + NULL accepted) and `ON DELETE CASCADE` behaviour.
- **Rollback strategy (DB):** Flag-off 404s the link routes. `downgrade()` deletes `kind='job_cycle'` rows **before** narrowing the CHECK constraint (otherwise the narrow would fail against live nest rows), then drops the index, FK column and `pdca_phase` + its constraint.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Job cycle nesting | Not expressible | Any `JobType` → any other via `job_cell_links` kind `job_cycle` (not hardcoded Operational↔Engineer) |
| Nest cycle safety | N/A | BFS acyclic guard mirroring `document_graph` `would_create_implements_cycle`; self-nest and transitive loops rejected 409 |
| Lane nest SSOT | N/A | Chip **derived** from links; **no** second FK on `job_lanes` — asserted by test |
| Deep-link resolution | `job_type` unregistered | `job_type` registered in `href_registry` → `/job-lifecycle/cycles/{id}` |
| Entity-type dropdown | Would drift if hardcoded in FE | Served from registry via `GET /link-entity-types`, FE falls back to a matching static list only on fetch failure |
| Entity360 nest visibility | No nest hops | Nest hops both directions + `job_type` entity supported |
| Entity360 permissions | `job_type` absent from map | `HOP_READ_PERMISSIONS["job_type"] = "job:read"` |
| PDCA phase | Not modelled | `job_steps.pdca_phase` nullable + CHECK; colours on step axis only |
| Axis reorder/rename | Read-only labels/order | Inline rename + move up/down via **existing** PATCH APIs (no new endpoints) |
| Alembic heads | 1 (`20261020_job_cell_links`) | 1 (`20261021_job_nest_pdca`) — no parallel JL head |
| DB-level cascades invisible to ORM hooks | 83 | 84 — `("job_types", "job_cell_links")` registered in the audit-visibility ledger |
| Feature flags | `job_lifecycle` / `job_cell_links` ON in Azure | Unchanged; no new flags |
| OpenAPI contract | Baseline | Additive only — contract check PASSED |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Single alembic revision `20261021_job_nest_pdca` revises `20261020_job_cell_links`; `alembic heads` returns exactly one head
- [x] AC-02: `ck_job_cell_links_kind` accepts `job_cycle`; `target_job_type_id` nullable FK → `job_types` with `ON DELETE CASCADE`; verified on live Postgres
- [x] AC-03: `job_steps.pdca_phase` nullable, constrained to `plan|do|check|act`; invalid value rejected by the DB
- [x] AC-04: `job_cycle` link create requires `target_job_type_id` and rejects the other kinds' target fields
- [x] AC-05: BFS acyclic guard rejects self-nest, direct, transitive and diamond-reachable cycles with 409
- [x] AC-06: `job_type` registered in `href_registry`; `job_cycle` link hrefs resolve through the registry (not string-built in the service)
- [x] AC-07: `JobLifecycleProducer` supports the `job_type` entity and emits nest hops **both** ways; `job:read` enforced via `HOP_READ_PERMISSIONS`
- [x] AC-08: PDCA colours apply to the **step** axis only — lane headers stay uncoloured; cycling a phase issues a step PATCH
- [x] AC-09: Lane nest chip is derived from links only; no `job_type` FK field exists on `JobLane`
- [x] AC-10: Breadcrumb drills in from a lane chip and from a matrix cell nest chip, drills back out, and deep-links via `/job-lifecycle/cycles/:jobTypeId`
- [x] AC-11: Lane/step rename PATCHes on blur and skips the PATCH when unchanged; reorder writes dense `sort_order` and no-ops at list ends
- [x] AC-12: Entity-type dropdown is populated from `GET /link-entity-types` (fetched once per mount) with a registry-matching fallback
- [x] AC-13: `pdca_phase_set` distinguishes "omitted" from an explicit `null` clear
- [x] AC-14: No new feature flags; W3–W5 scope (clone/map/trail/freshness/baselines) untouched

## 5) Testing Evidence (link to runs)
- [x] Lint / typecheck — `eslint` clean on all changed FE files; `tsc --noEmit` clean
- [x] Unit (BE) — full suite **5782 passed, 11 skipped, 0 failed**; of which **27 new** in `tests/unit/test_job_lifecycle_ux_w2.py`
- [x] Unit (FE) — full suite **2598 passed, 0 failed** across 389 files; of which **49 new** (22 helpers · 12 `JobCellLinksW2` · 15 `JobLifecycleW2`)
- [x] Contract — OpenAPI compatibility check vs `openapi-baseline.json`: **PASSED**, additive only
- [x] Route shadowing guard — 18 passed; `/link-entity-types` reachable and not swallowed by `/links/{link_id}`
- [x] Migration — full chain applied to scratch Postgres; schema, CHECK enforcement and CASCADE verified by hand
- [ ] E2E Smoke — staging bake after tip LIVE

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag on → open Job Lifecycle → add a `job_cycle` link from a cell → nest chip appears on the lane (derived) → drill in via breadcrumb → drill back out
- [x] CUJ-02: Attempt a nest that would close a loop → 409 surfaced in the composer, no row written
- [x] CUJ-03: Set a step's PDCA phase → column header recolours; lane headers unaffected
- [x] CUJ-04: Rename and reorder a lane and a step → existing PATCH APIs, dense `sort_order`
- [x] CUJ-05: Deep-link straight to `/job-lifecycle/cycles/:jobTypeId` → correct pack loads with breadcrumb

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** A 409 on nest create means the link would create a cycle — inspect existing `job_cycle` links for that pack. If operators see 403 with flags ON, grant `job:read` / `job:author` (unchanged from W1).

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** `alembic upgrade head` reaches `20261021_job_nest_pdca`; tip SHA match; programme flags remain ON; healthz/readyz 200; CUJ-01 on STG
- **Canary plan:** N/A — additive nullable columns + widened CHECK; no backfill, no read-path change for existing rows
- **Prod post-deploy checks:** PROD tip SHA = MAIN; ACA image tag contains tip SHA; health 200; migration at `20261021_job_nest_pdca`; Job Lifecycle loads and nesting round-trips

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Nest guard false positives blocking legitimate links; composer regressions on axes; migration failure on STG
- **Rollback steps:** Revert squash / redeploy prior image. If the schema must go back, `alembic downgrade 20261020_job_cell_links` — this **deletes `job_cycle` link rows and all `pdca_phase` values** by design (they cannot exist under the narrower constraint).
- **Data repair needed?** Only on a DB downgrade, and only to re-create nest links / PDCA phases — both are operator-authored and re-enterable. No silent data loss on a code-only revert.

## 10) Evidence Pack
- Local BE unit: 5782 passed / 11 skipped / 0 failed (27 new)
- Local FE unit: 2598 passed / 0 failed (49 new)
- OpenAPI contract check: PASSED (additive)
- Alembic heads: single head `20261021_job_nest_pdca`
- CI URL: (fill after PR)
- STG/PROD tip verify: (post-merge conveyor)

## Gate Checklist
- [x] Gate 0 — Change Ledger complete
- [x] Gate 1 — Scope held (no W3–W5, no new flags, no second lane SSOT)
- [x] Gate 2 — Compatibility / migration additive + single head + downgrade path stated
- [x] Gate 3 — AC + CUJ covered
- [ ] Gate 4 — CI green on PR
- [ ] Gate 5 — STG then PROD tip LIVE + health
