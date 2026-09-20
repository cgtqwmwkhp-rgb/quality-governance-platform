# Change Ledger (CL-INV-C4-NESTED-WRITER)

> Adjacent, not fixed here: the pack renders every section it finds, so an RCA answer now stored
> under both `section_4_root_cause` and the legacy `rca` alias appears twice in a generated pack
> until C13 dedupes at render. Flat-key *readers* stay exactly where they are — dropping them is
> the C18 contraction. No findings table (C7).

## 1) Summary
- **Feature / Change name:** INV-C4 — write nested investigation JSON from the detail page
- **User goal:** A finding, conclusion or 5-Whys answer typed in the workspace must reach the
  report. Creation-from-a-record writes `data.sections.<section>.<field>`; the detail page writes
  flat `data.findings`. The template closure walk (`iter_run_section_values`) descends
  `data.sections` and returns, and the pack builder copies `data.sections` only, so everything
  typed on the workspace was invisible to both. C3 shipped the reader for the two shapes; this is
  the writer.
- **In scope:** New `merge_nested_workspace_fields` (idempotent dual-write), called on the two
  investigation persist paths (PATCH + autosave); nested hydration and dual-write save on the
  detail page's Summary and RCA cards.
- **Out of scope:** Pack rendering (C13), dropping the flat-key readers (C18), findings table (C7),
  `investigation_service.py` (owned by open PR #1853 / C5), `investigation_pack_pdf.py`.
- **Feature flag / kill switch:** None. Kill SHA = LIVE `836ed31f7452`. The merge only *adds* the
  missing copy of a value, so reverting the squash leaves every row readable by both shapes.

## 2) Impact Map (what changed)
- **Frontend:** `frontend/src/pages/investigation/investigationNestedData.ts` (new);
  `InvestigationDetail.tsx` — Summary/RCA hydrate nested-first and save both shapes.
- **Backend:** `src/domain/services/investigation_data_writer.py` (new);
  `src/api/routes/investigations.py` — merge applied to the `data` blob in `update_investigation`
  and `autosave_investigation` before assignment.
- **APIs:** No contract change. No new request or response field, so `openapi-baseline.json` is
  untouched.
- **Database / flags:** none. No column, no Alembic migration — this is JSON content, not schema.
- **Workflows/jobs:** none. No startup job rewrites production rows.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive on both sides. Flat keys keep being written and keep being
  read; the nested copy is added beside them. The C3 precedence rule is unchanged: when both shapes
  hold content, the nested value stands.
- **Breaking changes:** none.
- **Migration plan:** Backfill is lazy — the merge runs on every write, so a row converts the next
  time it is saved. No bulk rewrite in this PR; `merge_nested_workspace_fields` is exported so a
  later batch can reuse the same function rather than reimplementing the rules.
- **Rollback strategy (DB):** Revert the squash. Rows already merged stay valid: both shapes hold
  the same value and the pre-C4 readers read the flat key.
- **Write-path safety:** The merge never deletes a key, never overwrites a non-empty value on
  either side, and never replaces a structured value (empty array or dict) with workspace text. A
  malformed payload is left alone rather than 500-ing: a non-dict `data`, a non-dict `sections`, a
  non-dict section, and malformed list entries are all passed through untouched. The input dict is
  not mutated. List-shaped `sections` keep the list shape — converting it to a dict would newly
  expose those sections to the closure walk, which is a behaviour change this PR does not make.

## Compliance Delta
- **PII touched?** Yes, incidentally: `lead_investigator` and the narrative fields can name people.
  No new collection, no new exposure, no new processor — the same value is stored twice inside the
  same JSON column on the same row, under the same tenant and the same permissions
  (`investigation:update`). Nothing is logged.
- **Lawful basis / retention:** unchanged (legitimate interest, existing investigation retention).
- **Secondary effect, stated plainly:** because a nested finding/conclusion is now copied onto the
  flat key, two existing flat-only readers start seeing data they previously missed on such rows —
  the summary completion gate (`collect_summary_readiness_blockers`) and lessons promotion
  (`extract_lessons_text`, which already preferred nested `section_7`). Neither is loosened: the
  gate passes only because the findings genuinely exist, and promotion still refuses to overwrite
  case text that is already present.
- **What this PR does not claim:** that the pack layout is now correct (C13), that flat keys are
  gone (C18), or that historical rows are already converted (they convert on next write).

## 4) Acceptance Criteria (AC)
- [x] AC-01: A flat workspace field is copied into its section — `findings`, `conclusion`,
  `lead_investigator` into `section_3_investigation_findings`; `problem_statement`, `root_cause`,
  `contributing_factors`, `why_1`…`why_5` into `section_4_root_cause`.
- [x] AC-02: RCA fields also land in the legacy `rca` alias section, because the default template
  (id=1) declares its root-cause section as `rca` and the closure walk takes section keys from the
  template.
- [x] AC-03: A nested value is copied onto the flat key when that key is missing or empty.
- [x] AC-04: When both shapes hold content the nested value stands and the flat key is untouched,
  matching `read_investigation_field` (C3).
- [x] AC-05: Nothing is invented — both sides empty creates no key and no section, and a blob with
  no workspace fields comes back unchanged.
- [x] AC-06: Idempotent — merging an already merged blob changes nothing.
- [x] AC-07: Empty string is a value, not `None`; content on one side beats an empty or
  whitespace-only string on the other; an empty array keeps its type instead of taking text.
- [x] AC-08: List-shaped `sections` are merged into the matching `{id, fields}` entry (appended if
  absent) and stay a list; malformed shapes are passed through without raising.
- [x] AC-09: Unrelated keys survive — `source_snapshot`, `customer_pack_visibility`, mapping logs,
  every other section.
- [x] AC-10: PATCH and autosave both store the merged blob, so an older client that still sends
  flat keys is converted server-side; the autosave revision event records what was stored.
- [x] AC-11: The detail page hydrates Summary and RCA from the nested section when the flat key is
  empty, and saves to both shapes so an edit cannot be masked by the stale copy.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_investigation_data_writer.py` (25 tests): flat→nested, nested→flat,
  nested-wins, alias + contract section, unrelated keys, no mutation, idempotence, empty string,
  empty array, malformed payloads, list-shaped sections.
- [x] Unit — `tests/unit/test_investigation_nested_write_persist.py` (4 tests): PATCH and autosave
  wiring, including the nested→flat direction the summary gate reads.
- [x] Regression — `pytest tests/unit -k investigation` (243 passed, none skipped).
- [x] Frontend — `vitest run src/pages/__tests__/InvestigationDetail.test.tsx` (28 passed):
  nested save payload for findings and for whys in both RCA sections, plus nested hydration.
- [x] Lint/type — `black --check`, `flake8`, `mypy` on the changed Python; `tsc --noEmit` and
  `eslint --max-warnings 0` on the changed frontend.
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Type findings and a conclusion on the workspace Summary card, save — the value is
  stored flat *and* under `section_3_investigation_findings`, so the closure walk and the pack can
  see it.
- [x] CUJ-02: Type a 5-Whys chain and a root cause on the RCA tab, save — stored flat and under
  both `section_4_root_cause` and `rca`, so the gate sees it whichever template the run uses.
- [x] CUJ-03: Open an investigation whose findings arrived nested from the template run — the
  editors show that text instead of an empty box, and re-saving does not lose it.
- [x] CUJ-04: An older client that sends flat keys only still ends up with nested data, because the
  merge runs on the server persist path.
- [x] CUJ-05: A malformed or unrelated `data` blob is saved unchanged — no 500, no invented keys.

## 7) Observability & Ops
- **Logs:** none added. The merge is silent by design; logging narrative fields would put
  investigation PII in application logs.
- **Metrics:** none.

## 8) Release Plan
- **Staging / prod:** no schema change and no flag. Confirm `/healthz` and
  `/api/v1/meta/version` `build_sha` on the merge SHA, then save a finding on a staging
  investigation and confirm the stored blob carries `data.sections`.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** a production payload that comes back from PATCH with a workspace field
  changed rather than added, or a closure gate that flips from BLOCKED to OK without content.
- **Rollback steps:** Revert the squash on `main` and redeploy previous LIVE SHA `836ed31f7452`.
  No data step: merged rows stay readable by the pre-C4 flat readers.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- No migration

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (new helper + persist hook; no contract change)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
