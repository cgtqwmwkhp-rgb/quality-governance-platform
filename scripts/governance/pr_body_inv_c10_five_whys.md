# Change Ledger (CL-INV-C10-FIVE-WHYS)

> Adjacent, not fixed here: CAPA per Why is INV-C11 (DEC-2) — this PR keeps the
> single "Create CAPA from root cause" action. ICAM / contributing-factor rows
> are C12. The generated pack and closure still read the legacy `why_1`..`why_5`
> strings (C13 / C18 drop them later); this PR dual-writes those strings and
> does not edit `investigation_pack_pdf.py`, `investigation_pack_draw.py`
> (C15 #1857 squash `e4facada7` is chasing Azure) or
> `investigation_closure_helpers.py` (C8 LIVE). No findings CRUD, no
> competence, no PAMS, no Entra, no CB-UI-5.

## 1) Summary
- **Feature / Change name:** INV-C10 — RCA onto `five_whys_analyses`
- **User goal:** The investigation workspace RCA tab was a single `why_1`
  textarea (plus problem / root / contributing boxes) saved through the run
  JSON. PR-15/16/17 already shipped `five_whys_analyses` with a JSON `whys`
  column of `{level, why, answer, evidence}`, but the workspace never used it.
  Investigators could not record per-Why evidence, leftover `why_1`..`why_5`
  strings never became analyses, and the generic `/rca-tools/five-whys`
  surface is not tenant-scoped for this page. Absorbs the investigation-scoped
  API, the RCA tab rebuild, and the leftover-string conversion (the three
  concerns that only make sense together because the tab has to read the same
  row the conversion writes).
- **In scope:** investigation-scoped `GET`/`PUT /investigations/{id}/rca` on
  the existing table; lazy conversion of leftover `why_1`..`why_5` (and the
  other RCA strings) without inventing text; dual-write of those strings into
  both JSON shapes; RCA tab rebuilt onto five Why slots with optional
  evidence; OpenAPI pair updated surgically; unit + smoke + frontend tests.
- **Out of scope:** CAPA-per-Why columns (C11), ICAM (C12), pack PDF/draw
  (C15/C13), closure helpers (C8), findings CRUD, dropping flat-key readers
  (C18), alembic (the table already has `tenant_id`, `investigation_id`, and
  `whys` JSON with evidence), a second table, competence, PAMS, Entra, CB-UI-5.
- **Feature flag / kill switch:** None. Kill SHA = LIVE `684bac3d60f7` (INV-C8).
  Reverting the squash restores the `why_1` textarea; converted analysis rows
  remain on `five_whys_analyses` and the dual-written strings remain on the
  run. **Do not merge while C15 #1857 squash `e4facada7` is chasing LIVE** —
  Azure is one SHA.

## 2) Impact Map (what changed)
- **Database:** none. `five_whys_analyses` already exists (PR-15/16/17) with
  nullable `tenant_id`, `investigation_id` ON DELETE CASCADE, and JSON `whys`.
  No column added, renamed, or dropped. No alembic in this PR.
- **Migration:** none.
- **Backend:** `src/domain/services/investigation_rca_service.py` (new — own
  the analysis, convert leftover strings once, dual-write); 
  `src/api/schemas/investigation_rca.py` (new); `src/api/routes/investigation_rca.py`
  (new); `src/api/__init__.py` — mount under `/investigations` after findings.
  Generic `/rca-tools/five-whys` is untouched.
- **Frontend:** `InvestigationDetail.tsx` RCA tab — five Why answer + evidence
  slots, honest empty caption, save via `saveRca` not `investigationsApi.update`.
  `investigationsClient.ts` — `getRca` / `saveRca`.
- **APIs:** `GET` and `PUT /api/v1/investigations/{investigation_id}/rca`.
  Contract files updated in pair (`docs/contracts/openapi.json` and
  `openapi-baseline.json`), surgical insert, files kept byte-identical.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive. The run payload still carries
  `why_1`..`why_5`, `problem_statement`, `root_cause` and
  `contributing_factors` in both JSON shapes. Every workspace write overwrites
  those strings from the analysis (not C4's blank-fill merge): after C10 the
  analysis is the author, and a blank-fill would leave a stale nested Why
  standing over a cleared slot. Flat-key readers stay until C18. C3 still
  reads nested or flat.
- **Lazy conversion:** the first GET or PUT for a run with no tenant-scoped
  analysis copies leftover nested-non-empty-then-flat RCA strings into a row,
  under a row lock on the run. Empty / whitespace / non-string values produce
  no Why text — nothing is invented, including Why *questions*. A run nobody
  opens is never touched. A `tenant_id IS NULL` row already linked to this
  investigation is claimed rather than duplicated.
- **PUT replaces levels 1–5.** Extra levels `>5` stored by the generic
  RCA-tools editor are kept so a workspace save cannot drop them. Duplicate
  levels on the request are 422, not last-write-wins.
- **Contributing factors:** the column is JSON (a list in the RCA-tools
  model); the workspace is one box. The string is stored as a one-item list.
  Splitting on newlines would invent several factors from one textarea (C12
  is ICAM; this PR does not).
- **GET `/rca` may persist a conversion.** Same "read that writes, once" as
  C7 `GET /findings` and C8 closure. `get_db` commits a successful request;
  the route also commits explicitly when conversion wrote a row.
- **Fail closed:** every analysis query re-filters on `tenant_id` **and**
  `investigation_id`. A missing tenant, a mismatch, or another organisation's
  row is honest empty on GET and a refused write on PUT — never a 500 and
  never a Why that does not belong to this tenant.
- **Empty Whys:** five blank slots, `id` null, HTTP 200. Not a 404
  and not invented prose.
- **Transactions:** the service never commits. The route owns the transaction,
  so an analysis write and its JSON sync land together or not at all. `data`
  is reassigned rather than mutated in place.
- **Response contract (PX-168):** `GET`/`PUT` return `id` (the analysis row;
  server-owned) plus the settable fields. Dual-written `why_1`..`why_5` stay
  on `investigation_runs.data` and in the service payload used by tests; they
  are not advertised on `InvestigationRcaResponse`, because a leftover-string
  field would be a second writer of the same Why.
- **Shell budget:** RCA `getRca`/`saveRca` live on the lazy
  `investigationDetailApi` module, not the shell `investigationsApi` factory.
- **Breaking changes:** none of the public run contract. The RCA tab no
  longer PATCHes `why_1` through the run update; callers that still PATCH the
  run JSON are overwritten the next time the tab saves (the analysis is now
  the author).
- **QGP never writes PAMS.**

## Compliance Delta
- **PII touched?** Yes, but no new PII and no new audience. Why answers and
  evidence are investigator prose about an incident and may name people; they
  were already stored on `investigation_runs.data` and (for anyone who used
  RCA tools) on `five_whys_analyses`. This PR changes where the workspace
  edits that prose (the analysis row, with the strings kept in step) and who
  can edit evidence per Why. No new collection, no new field type, no new
  export.
- **Lawful basis / retention:** unchanged — legal obligation / legitimate
  interest, existing investigation retention. Analysis rows are `ON DELETE
  CASCADE` from the run (already on the table), so an investigation deletion
  still removes its 5-Whys in one step. Conversion copies existing words; it
  does not lengthen retention.
- **New processor?** No. **New egress?** No. **Entra?** Untouched, flag stays
  false.
- **QGP never writes PAMS.** Nothing here touches PAMS, competence, or Users.
- **Authorisation:** both endpoints declare `investigation:update`, including
  the GET — same reason as C7 findings. `investigation:view` is granted to
  nobody (`ADMIN_ROLE_PERMISSIONS` is a proposal, not a migration). A new
  token would 403 the RCA tab for every non-superuser. `AUTHENTICATED_ONLY_DEBT`
  is at its ceiling, so `CurrentUser` alone is not an option. Two new routes,
  two permission-gated. `_get_investigation_or_404` is imported from
  `investigations.py` rather than reimplemented (cross-tenant
  `TENANT_ACCESS_DENIED` before roles; in-tenant-but-not-yours is a 404).
- **The consequence, recorded rather than hidden:** a caller who may read an
  investigation but not update it can no longer see Whys *on this panel*.
  They still see the legacy strings on the run payload and in the generated
  pack. Splitting read from write needs a granted `investigation:view`.
- **Logging:** one info line, `investigation_rca_converted`, carrying an
  investigation id and an analysis id. No Why text and no identity reaches
  application logs.
- **What this PR does not claim:** that closure now reads the analysis (it
  still reads the strings — C8 / C13), that the pack prints per-Why evidence
  (C15/C13), that CAPA can be raised per Why (C11), or that a read-only
  viewer can see the panel.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Workspace RCA is stored on the existing `five_whys_analyses`
  table (one tenant-scoped row per run). No second table, no CAPA-per-Why
  column.
- [x] AC-02: `GET` and `PUT /api/v1/investigations/{id}/rca` exist, declare
  `investigation:update`, and go through `_get_investigation_or_404`.
- [x] AC-03: Each Why is `{level, why, answer, evidence}`. The RCA tab is
  five answer + evidence slots, not a single `why_1` textarea.
- [x] AC-04: First GET/PUT for a run with leftover `why_1`..`why_5` (nested
  non-empty, then flat) converts those strings into an analysis without
  inventing Why questions, evidence, or blank-slot prose.
- [x] AC-05: Every workspace write dual-writes `why_1`..`why_5`,
  `problem_statement`, `root_cause` and `contributing_factors` into both JSON
  shapes. Clearing a Why overwrites a stale nested string. Flat-key readers
  are not dropped.
- [x] AC-06: Empty Whys return HTTP 200 with five blank slots and
  `id` null — not 404, not 500, not invented text. Whitespace-only
  leftover strings create no row.
- [x] AC-07: Every analysis query filters on `tenant_id` and
  `investigation_id`. A missing or mismatched tenant is honest empty on GET
  and a refused write on PUT. Another tenant's row with the same
  `investigation_id` is invisible.
- [x] AC-08: A null-tenant analysis already linked to this run is claimed,
  not duplicated.
- [x] AC-09: Extra Why levels `>5` from RCA-tools survive a workspace save
  of levels 1–5. Duplicate levels on PUT are refused.
- [x] AC-10: Generic `/rca-tools/five-whys` is unchanged. Pack PDF/draw and
  closure helpers are not in this diff. "Create CAPA from root cause" remains
  one action, not per-Why.
- [x] AC-11: OpenAPI pair records the new path and schemas and stays
  byte-identical. QGP never writes PAMS.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_investigation_rca_five_whys.py` (17 tests) and
  `tests/unit/test_investigation_rca_api.py` (8 tests): dual-write of both
  nested RCA sections, clearing a stale nested Why, no invented blank
  sections, padded empty slots, empty GET, whitespace invents nothing, flat
  and nested conversion, conversion is once, Why questions are not invented,
  upsert dual-write, leftover Whys not lost on first PUT, extra levels kept,
  cross-tenant invisible, mismatched tenant fail-closed, null-tenant claim,
  GET converts and commits, PUT without tenant refused, duplicate levels 422,
  extra-forbid, both endpoints permission-gated, paths mounted where the
  client calls them.
- [x] Smoke — `tests/smoke/test_inv_c10_five_whys.py`: leftover `why_1`
  converts; empty run stays empty and creates no row.
- [x] Regression — `pytest tests/unit -k 'investigation and not pack_pdf and not pack_draw'`
  (337 passed, none skipped). Existing RCA/investigation tests were not
  skipped or loosened.
- [x] Frontend — `vitest run` on `InvestigationDetail.test.tsx` and
  `investigationsClient.test.ts` (44 passed): RCA save goes to `saveRca` not
  `update`, Why + evidence hydrate, honest empty caption, CAPA-from-root
  still present, client hits `/investigations/{id}/rca`.
- [x] Lint/type — `black`, `isort`, `flake8` clean on the new Python;
  `mypy` clean on the three new src modules; `scripts/check_import_boundaries.py`
  OK; Prettier on the changed frontend files.
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open an investigation whose RCA exists only as leftover
  `why_1` / nested section-4 text — the RCA tab shows that Why as level 1
  with empty evidence; the words are unchanged; an analysis row now exists.
- [x] CUJ-02: Type Why 1, optional evidence, and a root cause; Save RCA —
  `PUT /rca` stores the analysis; `why_1` and `root_cause` are dual-written
  flat and nested so closure and the pack still read them.
- [x] CUJ-03: Open an investigation with no RCA — five blank slots and an
  honest empty caption; Save is a no-op until something is typed; no 500.
- [x] CUJ-04: Clear a previously saved Why and save — the nested
  `section_4_root_cause.why_1` is overwritten to `""`, not left stale.
- [x] CUJ-05: An investigation with no tenant recorded lists empty Whys and
  refuses PUT rather than storing an unscoped row.
- [x] CUJ-06: Create CAPA from root cause still opens one CAPA from the
  root-cause box, not per Why.

## 7) Observability & Ops
- **Logs:** `investigation_rca_converted` (investigation id + analysis id)
  when GET persists a conversion. No Why text.
- **Metrics:** none added.
- **Query cost:** one indexed `five_whys_analyses` SELECT per GET/PUT
  (`investigation_id` + `tenant_id`), plus a row lock on the run when
  conversion might write. Conversion is once per run.

## 8) Release Plan
- **Do not merge this PR until C15 #1857 squash `e4facada7` is LIVE**
  (`build_sha` matches). Azure is one SHA.
- **Staging / prod:** no schema change and no flag. After this PR's own
  deploy, confirm `/healthz` and `/api/v1/meta/version` `build_sha` on the
  merge SHA, then open RCA on a staging investigation that has leftover
  `why_1` and confirm the Why appears as a slot with empty evidence, and
  that Save writes an analysis without dropping the legacy strings.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** a Why attributed to the wrong tenant, invented Why
  text on an empty run, a 500 on an investigation with no RCA, or the
  RCA tab saving through the run JSON again and desyncing the analysis.
- **Rollback steps:** Revert the squash on `main` and redeploy previous LIVE
  SHA `684bac3d60f7` (C8). Converted `five_whys_analyses` rows and
  dual-written strings remain; the tab reverts to the `why_1` textarea.
  No data-drop step — the table predates this PR.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- No migration
- Kill SHA: `684bac3d60f7` (INV-C8 LIVE)
- Head at open: `e4facada7` (INV-C15 squash, not yet LIVE)

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (`GET`/`PUT /investigations/{id}/rca`;
  OpenAPI pair updated; existing `five_whys_analyses` reused)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
