# Change Ledger (CL-INV-C8-CLOSURE-FINDINGS-ROWS)

> Adjacent, not fixed here: the generated pack still prints the concatenated
> `data.findings` string (INV-C13, blocked on C15 #1857 owning
> `investigation_pack_pdf.py`). Flat-key readers elsewhere stay until INV-C18.
> Dual-write on row mutation is unchanged (C7). No RCA (C10), no ICAM (C12),
> no competence, no PAMS, no Entra, no CB-UI-5.

## 1) Summary
- **Feature / Change name:** INV-C8 — closure validation onto finding rows
- **User goal:** Complete and close must ask "does this investigation have
  findings?" against the `investigation_findings` rows C7 introduced, not
  against the leftover flat JSON key. Today a run whose findings exist only as
  rows (or only nested from INV-C4) is blocked from complete/close, and a run
  whose string is stale can close incorrectly. This is the gate that blocks
  every user; it ships alone with its own smoke.
- **In scope:** the summary-tab `MISSING_FINDINGS` check in
  `collect_summary_readiness_blockers`; a tenant-scoped read helper on
  `InvestigationFindingsService`; lazy conversion of a leftover legacy string
  through C7's existing splitter when the table is empty; unit tests and a
  dedicated smoke.
- **Out of scope:** pack rendering (C13/C15), retiring the flat key (C18),
  findings CRUD, alembic, OpenAPI, the detail-page editor, timeline, RCA, ICAM,
  competence, PAMS, Entra, CB-UI-5.
- **Feature flag / kill switch:** None. Kill SHA = LIVE `3b3244d15f79` (INV-C7).
  Reverting the squash restores the flat-key gate; rows and the dual-written
  string remain.

## 2) Impact Map (what changed)
- **Database:** none. C7's `investigation_findings` table is already LIVE.
- **Migration:** none.
- **Backend:** `src/domain/services/investigation_closure_helpers.py` — findings
  presence is a tenant-scoped row probe (fail closed), with one-shot C7
  conversion when the table is empty; `collect_summary_readiness_blockers` is
  async so it can query. `src/domain/services/investigation_findings_service.py`
  — additive `has_non_empty_findings` read helper; CRUD unchanged.
  `src/api/routes/investigations.py` — the collector awaits the helper (one
  call site; the probe tenant is still the run's, from
  `resolve_investigation_closure_scope`).
- **Frontend:** none (backend-only).
- **APIs:** none. `MISSING_FINDINGS` is the same reason code.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** the gate moves onto rows; C7 still dual-writes the
  concatenated string on every mutation so the pack (and any remaining flat
  readers) stay in step. This PR does not drop those readers.
- **Lazy conversion:** if the table is empty and a leftover flat *or nested*
  findings string exists, C7's `ensure_converted` splits it once under the
  existing row lock. Blank / whitespace / non-string input still yields no
  rows — nothing is invented. Empty rows + empty string remain
  `MISSING_FINDINGS`.
- **Whitespace-only bodies** do not count as a finding.
- **Fail closed:** a tenant mismatch, a missing run id, or a probe error is
  "findings missing", never a clean close over findings nobody can see, and
  never an HTTP 500 on the complete/close path.
- **GET `/closure-validation` may persist a conversion.** `get_db` commits a
  successful request. That is the same "read that writes, once" C7 already
  does on `GET /findings`.
- **Breaking changes:** none of the public contract. A run that previously
  closed on a stale non-empty string with empty rows will now be blocked
  (honest). A run that was blocked with rows and an empty flat key will now
  pass the findings part of the gate.
- **QGP never writes PAMS.**

## Compliance Delta
- **PII touched?** No new PII and no new audience. The gate now *reads* the
  same investigator prose C7 already stores as rows. Conversion may copy that
  prose from JSON into rows — the same one-shot C7 conversion, not a new
  collection.
- **Lawful basis / retention:** unchanged.
- **New processor?** No. **New egress?** No. **Entra?** Untouched, flag stays
  false.
- **QGP never writes PAMS.** Nothing here touches PAMS, competence, Users, or
  CB-UI-5.
- **Authorisation:** unchanged. The probe uses the run's tenant after
  `resolve_investigation_closure_scope` (cross-tenant still
  `TENANT_ACCESS_DENIED` before any findings query). The row query re-filters
  on `tenant_id`.
- **Logging:** `investigation_closure_findings_probe_failed` on a probe
  exception (investigation id + tenant id). No finding text, no identity.

## 4) Acceptance Criteria (AC)
- [x] AC-01: At least one non-empty `investigation_findings` row for the run
  and tenant satisfies the findings gate when the flat `data.findings` key is
  empty or absent.
- [x] AC-02: Empty rows plus an empty leftover string still produce
  `MISSING_FINDINGS` (honest block).
- [x] AC-03: Nested-only legacy (`data.sections…findings`, empty flat key)
  converts once through C7 then passes; wording is not invented.
- [x] AC-04: Another tenant's rows do not satisfy the gate; asking with a
  mismatched tenant id fails closed even when this run has rows.
- [x] AC-05: A whitespace-only row does not count as a finding.
- [x] AC-06: A findings-probe error fails closed (`MISSING_FINDINGS`) rather
  than HTTP 500 on complete/close.
- [x] AC-07: A stale non-empty flat string with empty rows does not pass
  (after C7 delete-all the string is `""`; a mocked empty-row probe still
  blocks).
- [x] AC-08: Existing closure tests are not skipped or loosened; mocked
  fixtures stub the new row probe the same way they already stub open-work.
- [x] AC-09: Findings CRUD behaviour is unchanged (additive read helper only).
- [x] AC-10: Pack PDF / draw modules, alembic, OpenAPI, InvestigationDetail,
  timeline, competence, PAMS, Entra are untouched.
- [x] AC-11: Own smoke: rows without a flat string are not blocked solely for
  `MISSING_FINDINGS`; empty findings still are.

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_investigation_closure_findings_rows.py` **9 passed**:
  rows vs empty flat key, empty block, nested convert, stale string after
  delete, tenant isolation, mismatch fail-closed, probe-error fail-closed,
  blank legacy invents nothing, whitespace-only row does not count.
- [x] Unit — existing `test_investigation_closure_*.py` (**28 passed**, none
  skipped) and `test_investigation_completion_gate.py` (**9 passed**; two new
  collector assertions, existing ones held). Mocked fixtures stub the new row
  probe the same way they already stub open-work.
- [x] Regression — `pytest tests/unit -k investigation` → **342 passed**, none
  skipped (includes C7 findings CRUD unchanged).
- [x] Smoke — `tests/smoke/test_inv_c8_closure_findings_rows.py` **1 passed**
  (C8-owned; enterprise smoke untouched).
- [x] Lint — `black --check`, `isort --check-only`, `flake8` (0) and `mypy`
  clean on the changed Python; `scripts/check_import_boundaries.py` OK.
- [ ] Full CI — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: An investigation with finding rows and no flat `data.findings`
  string is not blocked solely for `MISSING_FINDINGS`.
- [x] CUJ-02: An investigation with no rows and no leftover string is still
  blocked with `MISSING_FINDINGS`.
- [x] CUJ-03: A nested-only pre-C7 findings paragraph converts on the first
  closure check and then passes the findings gate.
- [x] CUJ-04: Another organisation's finding rows cannot unblock this run.

## 7) Observability & Ops
- **Logs:** `investigation_closure_findings_probe_failed` (investigation id +
  tenant id) if the row probe throws. Conversion itself is C7's existing
  one-shot insert; GET `/closure-validation` may persist it via `get_db`
  commit.
- **Metrics:** none added.
- **Query cost:** one indexed `SELECT` on
  `(investigation_id, sort_order, id)` per readiness probe (twice on GET
  closure-validation, which already ran two summary probes). Conversion adds
  C7's existing `SELECT … FOR UPDATE` + insert, at most once per run.

## 8) Release Plan
- **Order:** behind INV-C7 LIVE `3b3244d15f79`. Do **not** merge while C15
  #1857 is the Azure tip — Azure is one SHA at a time.
- **Staging / prod:** after this SHA is the deploy tip, confirm `/healthz` and
  `/api/v1/meta/version` `build_sha`, then on a run that has finding rows and
  an empty flat key: GET `/closure-validation` must not list
  `MISSING_FINDINGS`; a run with no rows and no string still must.
- **No flag to flip.**

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** complete/close 500s; every investigation blocked for
  `MISSING_FINDINGS` despite visible rows; investigations closing with empty
  rows because a stale string was trusted (should not happen on this SHA —
  that was the pre-C8 defect).
- **Rollback steps:** revert the squash on `main` and redeploy previous LIVE
  SHA `3b3244d15f79`. **No data step:** C7's table and dual-written string
  remain; the restored gate reads the string again. Rows are not dropped.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): linked after PR creation
- Kill SHA: `3b3244d15f79` (INV-C7 LIVE)

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts — no contract change; `MISSING_FINDINGS`
  retained
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification (findings-rows walkthrough above)
- [x] **Gate 4:** Canary (N/A — no flag; the kill path is the revert in §9)
- [x] **Gate 5:** Production verification plan + monitoring ready
