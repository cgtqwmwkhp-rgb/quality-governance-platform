# Change Ledger (CL-JL3-STEP-LINKS)

## 1) Summary
- **Feature / Change name:** JL-3 — Step / cell links (audit · app · external)
- **User goal (1–2 lines):** When `job_cell_links` (and parent `job_lifecycle`) are on, operators can pin app entity hops, external https tools, and audit_outcome bi-links onto swimlane cells — hrefs resolved only via the X-1 `href_registry`.
- **In scope:** Alembic `job_cell_links` + RLS; model/schemas/service/routes; Entity360 job producer audit_outcome bi-link; `JobCellLinks.tsx` + helpers; FE client; Vitest + unit tests; Change Ledger
- **Out of scope:** Enabling `job_lifecycle` / `job_cell_links` in any environment; department annotation; parallel URL builders; X-3 satellites
- **Feature flag / kill switch:** `job_cell_links` / `JOB_CELL_LINKS_ENABLED` — **default OFF** (X-0 pre-registered). Parent `job_lifecycle` must also be on. Flag-off → link routes 404; composer hides Step links panel.

## Conveyor / merge gate
- Depends on **JL-2** tip (`531175fb`) swimlane composer + JL-1 axes. Prefer merge after JL-2 is **PROD LIVE**; flag-off makes earlier merge deploy-safe.
- Tip base: `origin/main` at/after `531175fb`.
- Do **not** arm auto-merge until CI green on this PR.
- Do **not** enable `job_cell_links` or `job_lifecycle` in staging/prod as part of this merge.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `JobCellLinks.tsx` + helpers; mounted from `JobLifecycle` when both flags on; cell chips for link labels; client list/create/delete
- **Backend (handlers/services):** `JobLifecycleService` link CRUD + `resolve_cell_link_href`; Entity360 `JobLifecycleProducer` supports `audit_finding` bi-link when flag on
- **APIs (endpoints changed/added):** `GET/POST …/cells/{lane}/{step}/links`; `DELETE …/links/{id}` (gated by both flags); cell list optionally embeds `links[]` when flag on
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `JobCellLinkCreate` / `JobCellLinkResponse`; additive `links` on `JobCellResponse`
- **Database (migrations/entities/indexes):** `20261020_job_cell_links` — table `job_cell_links` + FORCE RLS
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** Wiring only for existing `job_cell_links` (no new flags; remains default off)
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive schema + APIs behind default-off flags; JL-2 composer unchanged when `job_cell_links` off
- **Tolerant reader / strict writer applied?** Yes — app/audit store structured refs; href resolved at read via registry; external must be absolute http(s)
- **Breaking changes:** None while flags off
- **Migration plan:** Single revision `20261020_job_cell_links` revises `20261019_job_lifecycle_axes` (never parallel)
- **Rollback strategy (DB):** Flag-off 404s link routes; downgrade drops `job_cell_links`

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Cell hyperlinks | Docs refs only (JL-1/2) | App · external · audit_outcome links behind `job_cell_links` |
| Href construction | X-1 registry for Entity360 | Cell link hrefs also via `href_registry` / `audit_finding_href` only |
| Audit ↔ job bi-link | N/A | Entity360 `audit_finding` ↔ `job_step` via `job_cell_link` relation |
| Parallel URL builders | Forbidden by belt | Not introduced (FE uses API `href`) |
| RLS inventory | 33 tables | 34 — `job_cell_links` in `RLS_TABLES` + `HARDENING_MIGRATIONS` |
| Authz tokens / admin grant | 84 | Unchanged (reuse `job:read` / `job:author`) |
| Flag defaults | Pre-registered off | Untouched — still default off |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `job_cell_links` off → link endpoints 404; Step links UI absent
- [x] AC-02: App links store `entity_type` + `entity_id`; href from `href_for` only
- [x] AC-03: External links require absolute http(s) URL
- [x] AC-04: Audit outcome links store `audit_run_id` + `audit_finding_id`; href from `audit_finding_href`
- [x] AC-05: Entity360 producer emits bidirectional lists for `audit_finding` when flag on (empty OK when off)
- [x] AC-06: Single Alembic revision; `job_cell_links` in `RLS_TABLES` + `HARDENING_MIGRATIONS`; count 34
- [x] AC-07: Vitest + BE unit tests; flags not enabled in any environment by this PR

## 5) Testing Evidence (link to runs)
- [ ] Lint / typecheck / build — CI
- [x] Unit (BE) — `tests/unit/test_job_lifecycle_jl3.py` (+ JL-1 / RLS suites) — **60 passed** locally
- [x] Unit (FE) — jobLifecycle client/helpers/page + jobCellLinksHelpers — **20 passed** locally
- [ ] Integration — CI as applicable
- [ ] Contract — CI as applicable
- [ ] E2E Smoke — staging bake when flags enabled

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag on → select cell → add app / external / audit_outcome link → href from registry / URL
- [x] CUJ-02: Flag off → link routes 404; no Step links panel; composer still works under `job_lifecycle` alone
- [x] CUJ-03: Audit finding Entity360 returns job_step downstream hops when linked (flag on)

## 7) Observability & Ops
- **Logs:** Existing JL / Entity360 paths; producer errors become Entity360 source `error`
- **Metrics:** No new metrics
- **Alerts:** None new
- **Runbook updates:** Keep `JOB_CELL_LINKS_ENABLED` off until JL-2 LIVE + bake; enable only after `job_lifecycle` bake

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tip SHA match; both JL flags remain off unless bake; migration applied
- **Canary plan:** N/A — flag default off is the kill switch
- **Prod post-deploy checks:** ACA image tip SHA; `/health` / version; confirm `job_cell_links` still off unless signed enablement

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Link 500s with flag on; accidental parallel URL construction; unexpected link traffic with flag off
- **Rollback steps:** Set `JOB_CELL_LINKS_ENABLED=false`; redeploy prior image / revert squash; DB downgrade only if table must be removed
- **Owner:** Platform Engineering (Doc Graph × Job Lifecycle) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: Linked after Azure deploy on tip SHA
- Canary evidence (if applicable): N/A — flag default off

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (href_registry only; audit bi-link; additive schema)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked) — tip SHA; flags remain off
- [ ] **Gate 4:** Canary healthy (if used) — N/A flag-off kill switch
- [x] **Gate 5:** Production verification plan + monitoring ready (tip SHA + health; flags off until bake)
