# Change Ledger (CL-INV-C7-FINDINGS-ROWS)

> Adjacent, not fixed here: the closure gate still reads the concatenated string, not the rows
> (INV-C8), and the flat `data["findings"]` key still has readers (INV-C18). Both are why the
> string is kept in step rather than dropped. No pack rendering change (C13), no C15 graphics,
> no RCA link from a finding.

## 1) Summary
- **Feature / Change name:** INV-C7 — findings as rows with a list editor
- **User goal:** DEC-3. Findings were one free-text blob on `investigation_runs.data` — flat, and
  mirrored into the nested `sections` shape since INV-C4. Nothing could address, order, count or
  later reference an individual finding: the investigator typed a paragraph into a textarea, and
  the closure gate could only ask "is this string non-empty". Findings become a child table with
  their own ids and order, and the detail page gets an add / edit / reorder / delete list editor
  in place of the textarea.
- **In scope:** new `investigation_findings` table + additive migration; a service that owns row
  CRUD, the derived string, and the one-shot conversion of the legacy paragraph; five endpoints
  under `/api/v1/investigations/{id}/findings`; the list editor on `InvestigationDetail.tsx`;
  the OpenAPI pair.
- **Out of scope:** moving the closure gate onto rows (INV-C8), retiring the flat key (INV-C18),
  pack rendering (C13), C15 graphics, `investigations.py` / `investigation_service.py` (run
  lifecycle and timeline — C9 owns them), `InvestigationTimeline.tsx` / `activitySpine.ts` (C9).
- **Feature flag / kill switch:** None. Kill SHA = LIVE `54dcdb6d7c42` (INV-C4). Reverting the
  squash restores the textarea; the string it reads is still authoritative on every run, so no
  data step is required — see §9.

## 2) Impact Map (what changed)
- **Database:** new table `investigation_findings` (`id`, `tenant_id` NOT NULL → `tenants.id`,
  `investigation_id` NOT NULL → `investigation_runs.id` ON DELETE CASCADE, `sort_order` NOT NULL
  DEFAULT 0, `body` TEXT NOT NULL, plus the standard timestamp and audit-trail columns). One
  composite index `ix_investigation_findings_run_order (investigation_id, sort_order, id)` — the
  only read this table serves is "the findings of run X, in order".
- **Migration:** `alembic/versions/20261120_inv_c7_findings_rows.py`,
  revision `20261120_inv_c7_findings`, down_revision `20260903_asm_plant_evid`. Single head after
  the C9 merge (C9 added no migration). Create-only up, drop-only down.
- **Backend:** `src/domain/models/investigation_finding.py` (new);
  `src/domain/services/investigation_findings_service.py` (new — split/join, JSON sync, row CRUD,
  lazy conversion); `src/api/routes/investigation_findings.py` (new — five endpoints);
  `src/api/schemas/investigation_finding.py` (new); `src/api/__init__.py` mounts the router under
  the existing `/investigations` prefix; `src/domain/models/__init__.py` registers the model.
- **Frontend:** `frontend/src/pages/investigation/InvestigationFindingsEditor.tsx` (new — the list
  editor); `InvestigationDetail.tsx` replaces the findings textarea with it and stops sending
  `findings` in the summary save payload; `investigationsClient.ts` gains the five findings
  methods (`getTimeline` untouched); `client.ts` re-exports the two new types.
- **i18n:** twelve `investigations.findings.*` keys in `en.json` **and** `cy.json`. The four C9
  `investigations.timeline.origin_*` keys are kept as merged — this branch is rebased onto
  `1de9c8e13883`, not merged over it.
- **APIs:** three new paths, five operations, five new component schemas. Additive only:
  `docs/contracts/openapi.json` and `openapi-baseline.json` are updated **together** and remain
  byte-identical (433 insertions each, zero deletions).
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** dual-write, rows authoritative. Every row mutation rewrites the
  derived string into *both* JSON shapes (flat `data["findings"]` and each nested
  `data["sections"][…]["findings"]`), because C8 and C18 have not landed and a run whose rows and
  string disagreed would close on stale text. The string is therefore never the input after
  conversion, and never stale.
- **Why the string is overwritten, not merged:** INV-C4's `merge_nested_workspace_fields` only
  fills a blank — when both shapes hold text the nested value stands. That is correct for two
  independent editors of one field and wrong here, because after C7 the rows are the sole author.
  `sync_findings_text` writes both shapes itself and does not call the C4 merge, while following
  the same shape rules: the stored `sections` shape (dict / list / absent) is preserved rather
  than converted, a section whose value is not a dict is left alone, and a nested slot holding a
  list or object is never overwritten with text (that slot belongs to a structured editor, and
  the closure gate type-checks it).
- **Legacy conversion:** lazy and one-shot, not a migration backfill. A backfill would have to
  scan every run and write into JSON the workspace is concurrently saving. Instead the first list
  or first write for a run converts that run's string — only when the run has **zero** rows, and
  with the zero-row check and the insert taken under `SELECT … FOR UPDATE` on the run. So it
  happens once, a second concurrent first-reader waits and then finds the rows, and a run nobody
  opens is never touched. Idempotency is structural (zero rows) rather than a marker column, so
  there is no flag that can be wrong.
- **Deleting every finding is not undone by the next read:** emptying the list rewrites the string
  to `""`, so conversion cannot resurrect deleted findings from stale text.
- **The split does not invent content.** Markers (`1.` `1)` `(1)` `-` `*` `•`) win; otherwise blank
  lines; otherwise single newlines. Marker matching is anchored and bounded, so
  `2026-03-01 the guard was removed` is not a list item. Continuation lines stay attached to their
  finding, and text before the first marker becomes its own finding rather than being dropped.
  Concatenating the results reproduces the original words.
- **The join round-trips.** Two or more findings are numbered, and feeding that string back through
  the splitter returns the same bodies. A single finding is rendered with **no** `1.` prefix: that
  is the overwhelmingly common legacy shape, and numbering it would rewrite the exact words the
  pack prints and the gate reads on the first read of a run nobody has edited.
- **Ordering:** `sort_order` is 0-based and dense after any write; deletion compacts, so a later
  append cannot collide with a freed slot. It is deliberately **not** unique — a swap would have
  to violate the constraint mid-transaction, and a duplicated position degrades to
  `ORDER BY (sort_order, id)` rather than to an error the user cannot act on.
- **Reorder is all-or-nothing:** `finding_ids` must name exactly this run's findings, each once. A
  partial or padded list is refused with 400 (`INVESTIGATION_FINDINGS_REORDER_MISMATCH`), because
  the plausible cause is a stale editor and a silently-dropped id would look like a successful
  save while losing a finding's position.
- **Transactions:** the service never commits. The route owns the transaction, so a row write and
  its JSON sync land together or not at all. `data` is reassigned rather than mutated in place —
  it is a plain JSON column with no mutation tracking, and an in-place edit would not persist.
- **Breaking changes:** none server-side. The run payload still carries `findings` as a string in
  both shapes. The one user-visible removal is on the page: the summary save no longer sends
  `findings`, because the rows own it.
- **Migration plan:** additive `CREATE TABLE` + one index; no existing column is altered, renamed
  or dropped, and no data is moved. **Rollback:** `downgrade()` drops the index and the table.
  Tested as a script (see §5) and safe to run because the string on `investigation_runs.data` is
  kept current on every mutation — dropping the table loses the row structure and the ordering,
  not the findings text.
- **Read-path safety:** every row query filters on `tenant_id` **and** `investigation_id`, even
  though the caller has already been tenant-checked. `_get_investigation_or_404` is imported from
  `investigations.py` rather than reimplemented, so the investigation tenancy contract
  (#1382/#1389 — cross-tenant refused under `TENANT_ACCESS_DENIED` before roles are consulted,
  in-tenant-but-not-yours is a 404) has exactly one implementation. A second copy of that logic
  would be a second thing to keep in step, and the failure mode of it drifting is a cross-tenant
  read.

## Compliance Delta
- **PII touched?** Yes, but no new PII and no new audience. A finding is investigator prose about
  an incident and may name people; it was already stored on `investigation_runs.data` and printed
  in the customer pack. This PR changes where the same text lives (rows beside the JSON, not
  instead of it) and who can edit it granularly. No new collection, no new field, no new export.
- **Lawful basis / retention:** unchanged — legal obligation / legitimate interest, existing
  investigation retention. The child rows are `ON DELETE CASCADE` from the run, so an
  investigation deletion still removes its findings in one step and no retention path is
  lengthened or orphaned.
- **The audit trail does not cover the cascade, and now says so.** `ON DELETE CASCADE` means
  PostgreSQL removes a deleted run's findings with no Python event, so no per-finding audit row is
  written. `("investigation_runs", "investigation_findings")` is therefore registered in
  `CASCADES_INVISIBLE_TO_AN_ORM_HOOK`, beside the three RCA children of the same parent, and the
  header count in that record is corrected 87 → 88. The alternative — mapping a delete-cascading
  relationship so the ORM issues per-row deletes — was rejected: it hangs a lazy collection off
  `InvestigationRun`, which the async run loads on any attribute touch outside a greenlet, and that
  file's own header records that `MissingGreenlet` failure as the reason its siblings are not mapped
  either. The findings text also survives on `investigation_runs.data`, which the run's own delete
  audit row does cover.
- **New processor?** No. **New egress?** No. **Entra?** Untouched, flag stays false.
- **QGP never writes PAMS.** Nothing here touches PAMS, competence, or Users.
- **Authorisation, and the debt it does not add:** all five endpoints declare
  `investigation:update`, including the GET. `investigation:view` was the brief, and it is not
  implementable today: `User.has_permission` is exact set membership against tokens stored on a
  role, and nothing seeds roles from `src/domain/authz/catalogue.py` (`ADMIN_ROLE_PERMISSIONS` is
  recorded there as "a proposal, not a migration"). A new token is therefore granted to nobody, so
  `investigation:view` would 403 the findings panel for every non-superuser on the day it shipped.
  The catalogue also records that no investigation read token is enforced anywhere today
  (`investigation:read` is RESERVED for exactly that reason), so inventing one for this collection
  alone would be a control that is honest nowhere else. `investigation:update` is held by whoever
  can already save the workspace, which is who this editor is for. Leaving the read on
  `CurrentUser` alone was not available: `AUTHENTICATED_ONLY_DEBT` is at its ceiling and this PR
  does not raise it — five new routes, five permission-gated, census green.
- **The consequence, recorded rather than hidden:** a caller who may read an investigation but not
  update it can no longer see findings *on this panel*. They still see the concatenated string on
  the run payload and in the generated pack. Splitting read from write here needs a granted
  `investigation:view`, which is a role-seeding change, not a route change.
- **Logging:** one info line, `investigation_findings_converted`, carrying an investigation id and
  a row count. No finding text and no identity reaches application logs.
- **What this PR does not claim:** that the closure gate now counts findings (it still reads the
  string — C8), that the flat key is retired (C18), that ordering is enforced unique in the
  database, or that a read-only viewer can see the panel.

## 4) Acceptance Criteria (AC)
- [x] AC-01: `investigation_findings` exists with `tenant_id` NOT NULL → `tenants.id`,
  `investigation_id` NOT NULL → `investigation_runs.id` ON DELETE CASCADE, `sort_order` NOT NULL
  DEFAULT 0, `body` NOT NULL, and one `(investigation_id, sort_order, id)` index.
- [x] AC-02: The migration is create-only, chains to the previous head as the single head, and its
  `downgrade()` drops the index and table.
- [x] AC-03: Model and migration agree on `sort_order`'s default (both declare
  `server_default`), so the declared schema does not read as drift.
- [x] AC-04: `GET /investigations/{id}/findings` returns the rows in `(sort_order, id)` order, with
  `total`, `investigation_id`, and the `findings_text` the legacy readers will see. An empty list
  is a 200, not a 404.
- [x] AC-05: POST appends at the end, PATCH rewrites one body, DELETE removes one and compacts the
  gap, POST `/reorder` applies a permutation. All four return the whole ordered list, because
  `sort_order` is server-assigned and a client given only the new row would have to guess.
- [x] AC-06: A finding id belonging to another run — or another tenant — is a 404 on PATCH and
  DELETE, not a cross-run edit.
- [x] AC-07: A reorder list that is not exactly this run's ids, each once, is a 400 and changes
  nothing.
- [x] AC-08: The first list or write for a run with no rows splits the legacy string into rows and
  commits it; the second call creates nothing. Conversion takes a row lock on the run.
- [x] AC-09: Splitting handles numbered, parenthesised, bulleted, blank-line-separated and
  plain-newline text; keeps continuation lines attached; drops empty bodies; preserves preamble;
  and returns `[]` for blank, whitespace-only or non-string input.
- [x] AC-10: `join(split(x))` preserves bodies for multi-finding text; a single finding keeps its
  exact original wording with no number added.
- [x] AC-11: Every mutation rewrites flat `data["findings"]` and each nested findings section, and
  carries unrelated keys and sections over untouched.
- [x] AC-12: The nested `sections` shape is preserved — dict stays dict, list stays list, a
  non-dict section or a non-string nested slot is left alone, and an empty string does not create
  a section just to hold `""`.
- [x] AC-13: A run whose `data` is null or not a dict gets a fresh object when there is text to
  record, rather than silently keeping no findings string.
- [x] AC-14: All five endpoints are gated on `investigation:update`; the authorisation census
  passes and `MAX_AUTHENTICATED_ONLY_DEBT` is unchanged.
- [x] AC-15: The findings textarea is gone from the summary tab and the summary save no longer
  sends `findings`; the C4 nested dual-write for the other workspace fields is unaffected.
- [x] AC-16: The editor adds, edits, cancels an edit, deletes and moves findings up and down, keeps
  Move-up disabled on the first row and Move-down on the last, and surfaces an API failure as an
  error the user can see rather than a silent no-op.
- [x] AC-17: Every editor label resolves from `en.json` with Welsh parity in `cy.json`; the C9
  `timeline.origin_*` keys survive the rebase.
- [x] AC-18: `docs/contracts/openapi.json` and `openapi-baseline.json` are identical to each other
  and gained only the three new paths and five new schemas.
- [x] AC-19: The new database-level cascade is recorded in `CASCADES_INVISIBLE_TO_AN_ORM_HOOK` with
  the reason it is not mapped as an ORM relationship, so nobody can believe the audit trail covers
  it; the record's own count is corrected with it.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_investigation_findings_rows.py` (**41 passed**): the split branches
  (markers of all six kinds, preamble, continuation lines, blank-line paragraphs, plain newlines,
  CRLF, blank/whitespace/non-string), join round-trip and the single-finding no-prefix rule, the
  JSON sync across dict-sections / list-sections / inline-fields / absent / non-dict / list-valued
  slot / empty-text cases, create-append, update, delete-and-compact, reorder-permutation and
  reorder-mismatch, one-shot conversion, conversion after every finding was deleted, and
  cross-tenant and cross-run isolation on every mutation.
- [x] Unit — `tests/unit/test_investigation_findings_api.py` (**14 passed**): handler contracts,
  404 on a foreign finding, 400 on a reorder mismatch, the router being mounted under
  `/investigations`, every endpoint declaring `investigation:update`, and the migration —
  DDL compiled against the **Postgres** dialect (asserting the columns, FKs, cascade and index)
  plus `upgrade`/`downgrade` symmetry. Deliberately *not* a SQLite round-trip: the migration's
  `DEFAULT now()` is Postgres syntax, and a SQLite-only run either fails on it or forces the
  migration to be written for the wrong database.
- [x] Regression — `pytest tests/unit -k investigation` → **331 passed, none skipped**, including
  the C4 nested hydrate/save suite and C9's `test_investigation_parent_timeline.py` unchanged;
  then the whole unit suite, `pytest tests/unit` → **7551 passed, 11 skipped** (the 11 are
  pre-existing skips this run is explicitly not evidence for).
- [x] Governance guards that the first CI run caught, and the root causes rather than the
  symptoms: `test_admin_grant_statement.py` forbids any `src/**/*.py` outside
  `src/domain/authz/` from naming the proposed admin grant constant — the route docstring
  cited it by name and now describes it instead; `test_delete_cascade_audit_visibility.py`
  required the new cascade to be registered (see the Compliance Delta); and this file's own
  route-mount test read Starlette's `path_format`, which does not exist in the starlette 1.3.1
  that CI resolves out of the unpinned `fastapi` range, so it matched nothing there while passing
  on a local 0.52.1. It now reads `route.path` like every other route census in the suite.
- [x] Contract — `tests/unit/test_gt_openapi_list_routes.py`,
  `test_gt_api_honesty_contract.py`, `test_copilot_openapi_exclusion.py`,
  `test_audit_contract_freeze.py` → 22 passed;
  `scripts/check_openapi_compatibility.py` → no breaking changes.
- [x] Integration — `tests/integration/test_route_shadowing_guard.py` and
  `test_route_authorisation_census.py` → **37 passed** (the census is what proves the five new
  routes did not raise the authenticated-only debt).
- [x] Migration chain — `ScriptDirectory.get_heads()` → `['20261120_inv_c7_findings']`, single
  head. Three suites that assert the head by name were updated to it.
- [x] Frontend — `vitest run` on `InvestigationDetail.test.tsx`,
  `src/pages/investigation/__tests__`, `src/i18n` → **87 passed (12 files)**, of which
  `InvestigationDetail.test.tsx` is 38: rendering findings from the API, add, edit, cancel, delete,
  reorder up/down, disabled edge buttons, the API-error path, `listFindings` being called with the
  run id, and the C4 dual-write assertions retargeted onto `conclusion` now that `findings` no
  longer travels in the summary payload.
- [x] Lint/type — `black --check`, `isort --check-only`, `flake8` (0) and `mypy` clean on the
  changed Python; `tsc --noEmit` and `eslint --max-warnings 0` clean on the changed frontend;
  `scripts/check_import_boundaries.py` OK; `npm run i18n:check` passes (4564 keys, Welsh coverage
  held at 90.9%).
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open an investigation whose findings were typed as a numbered paragraph before C7 —
  the summary tab lists them as separate findings in the original order, with the original words.
- [x] CUJ-02: Add a finding, reload the page — it is still there, last in the list.
- [x] CUJ-03: Edit a finding's text and cancel — nothing changes; edit and save — only that
  finding changes.
- [x] CUJ-04: Move a finding up, then down — the order is what the buttons said, the first row
  cannot move up and the last cannot move down.
- [x] CUJ-05: Delete a finding — the remaining ones stay in order, and a subsequently added
  finding lands at the end rather than in the deleted slot.
- [x] CUJ-06: Delete every finding, then reload — the list is empty and the legacy paragraph does
  not come back.
- [x] CUJ-07: Save the summary tab after editing conclusion and root cause — those still write to
  both the flat and nested JSON shapes (C4), and the findings string reflects the rows rather than
  a textarea.
- [x] CUJ-08: Generate a customer pack / run closure validation on a converted investigation — both
  read the same findings text as before the conversion.
- [x] CUJ-09: Ask for another tenant's investigation findings — refused before any row query.
- [x] CUJ-10: PATCH a finding id that belongs to a different investigation in the same tenant —
  404, and the other run is untouched.

## 7) Observability & Ops
- **Logs:** one info line, `investigation_findings_converted` (investigation id + row count), on
  the single conversion per run. No finding text, no identity.
- **Metrics:** none added.
- **Query cost:** the list is one indexed SELECT on `(investigation_id, sort_order, id)`. A
  mutation adds a `max(sort_order)` or a lookup plus a re-read for the resync — all on the same
  index, all bounded by one run's findings. Conversion additionally takes one `SELECT … FOR UPDATE`
  on the run row, once per run for the life of the run.

## 8) Release Plan
- **Order:** this PR is behind INV-C9 `1de9c8e13883` and must not merge until that SHA is LIVE —
  the Azure chase is one SHA at a time.
- **Staging / prod:** the migration runs on deploy. Confirm `/healthz` and
  `/api/v1/meta/version` `build_sha` on the merge SHA, then on a staging investigation that had a
  multi-line findings paragraph: open the summary tab (rows appear), add one, reorder, delete one,
  and confirm closure validation and the generated pack still read the expected text.
- **No flag to flip.** The editor is live for anyone holding `investigation:update` as soon as the
  image is.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** findings appearing on the wrong run or tenant; the conversion splitting or
  reordering an existing paragraph's words; the closure gate or the pack reading a findings string
  that disagrees with the rows on screen; duplicate rows from a double conversion.
- **Rollback steps:** revert the squash on `main` and redeploy previous LIVE SHA `54dcdb6d7c42`.
  **No data step is required**: every mutation has kept `investigation_runs.data` current in both
  shapes, so the restored textarea reads the up-to-date text. Leave the table in place — it is
  additive and unreferenced by the reverted code; run `downgrade()` only if the table itself must
  go, accepting that row structure and ordering are lost while the text is not.
- **Partial-rollback note:** rolling back the *frontend* alone is not a supported state — the page
  would show the textarea while the rows remained authoritative for nothing, so any subsequent
  textarea save would be overwritten by the next row mutation. Revert the whole squash.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): linked after PR creation
- Migration: `20261120_inv_c7_findings` (additive `CREATE TABLE` + index; tested `downgrade()`)

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts — three new paths and five schemas in
  `docs/contracts/openapi.json` **and** `openapi-baseline.json`, updated together and identical
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification (converted-findings walkthrough above)
- [x] **Gate 4:** Canary (N/A — no flag; the kill path is the revert in §9)
- [x] **Gate 5:** Production verification plan + monitoring ready
