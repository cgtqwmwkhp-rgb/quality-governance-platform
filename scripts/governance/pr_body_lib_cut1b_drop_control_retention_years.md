# Change Ledger (CL-LIB-CUT1B-DROP-CONTROL-RETENTION-YEARS)

**Base:** branched from `origin/main` tip `6551434021074c39ea287ab5924146dfac850ae4` (STEWARD-14 / CIT-1 `#1698`), which is LIVE on `main` = STG = PROD.

## 1) Summary

- **Feature / Change name:** CUT-1b — drop `controlled_documents.retention_period_years`; the control layer stops being a second retention system of record (F-7 §2 / ADR-0023 amendment 3 / Northern Star R19)
- **User goal (1–2 lines):** "How long do we keep this?" has exactly one answer for a controlled document, and it is the one its category actually gives. A forty-year occupational-health record stops being recorded as a seven-year one.
- **In scope:** drop the column (model + alembic `20261104_lib_cut1b_drop`); derive the obsolete archive's `retention_end_date` from the Register row instead of from that column; extract the read-only `supersede_retention_until` the Register's own supersede path already implemented; two tip-head pins; ADR-0023 amendment 3 + CUT-1 design-note §CUT-1b + F-7 §2 disposition; new focused test module
- **Out of scope:** CUT-1c legacy `documents.retention_until` / `retention_*` backfill (deferred, D2); WJ-1-M2 `content_format`; control `document_access_logs` → `library_document_access_logs` merge (F-7 §3); `IMS 052` records action; any `taxonomy.json` edit; any frontend; any second alembic revision
- **Feature flag / kill switch:** None. A column drop is not flaggable, and the behaviour change it carries is the removal of a value nobody chose. Rollback is the migration revert (§9).

### The defect this closes

**`retention_period_years` was not a dormant parallel column. It was a live writer of Citation's flat seven years.**

```python
retention_period_years: Mapped[int] = mapped_column(Integer, default=7)
```

A SQLAlchemy `default` runs on every INSERT. Every controlled document created since `20260711_create_controlled_documents` was therefore stamped with **seven years** — Citation (ATLAS)'s "7 Years / all employees" position expressed as code — regardless of what its category says. Two of the categories STEWARD-14 decided (`02.08` Occupational Health, `04.08` Asbestos) are **forty-year** records; three are two- or three-year records.

STEWARD-14 retired Citation's flat seven years for the Register five commits ago and recorded that retirement in ADR-0023. It was still being written here. CUT-1 and STEWARD-14 both named the condition for removing it — *"once no writer remains"* — and both were describing this line.

The single reader compounded it:

```python
retention_end_date=_utcnow() + timedelta(days=document.retention_period_years * 365),
```

So the obsolete archive's disposal date was a made-up seven years, measured in 365-day years — the same approximation CUT-1 removed from the Register because it lands ten days early on a forty-year retention, on a queue that hard-deletes.

### What replaces it

Being marked obsolete **is** the document leaving the live set, so the archive's end date is the Register's supersede-anchored answer, read through `document_library_filing_service.supersede_retention_until` — the same function `apply_supersede_retention` now writes through, so the control archive and the Register cannot give different answers.

| Register row (the SoR) | Archive `retention_end_date` |
| --- | --- |
| supersede-anchored, N years | obsolescence + N **calendar** years |
| issue-anchored, `retention_until` already set at file | that date (its clock started at approval; obsolescence does not restart it) |
| event-anchored / indefinite | **NULL** |
| filed before CUT-1, no policy on the row | **NULL** |
| control record not anchored to the Register | **NULL** |
| Register row not visible to this tenant, or the id is stale | **NULL** |

`NULL` is "keep". Disposal hard-deletes the row and the blob, so a question the Register cannot answer must not produce a plausible-looking date. **No shorter clock was invented, and no flat default was reintroduced under another name** — a test asserts `ControlledDocument` now carries **no** column whose name contains `retention`, so a rename is caught as the same defect.

### Why the old value is not migrated onto the Register

It is not a governance fact. It is a constructor default nobody chose. Copying it forward would launder Citation's flat seven years into the system of record CUT-1 and STEWARD-14 built specifically to replace it — and would overwrite the executable policy STEWARD-14 just put there. The migration instead **logs** how many rows held anything other than seven immediately before the drop, so the deploy record shows what was actually destroyed rather than leaving it to inference.

## 2) Impact Map (what changed)

- **Backend:** `src/api/routes/document_control.py` — new `_archive_retention_end_date` (read-only, tenant-scoped, fail-safe NULL); `mark_document_obsolete` uses it and now takes one `obsoleted_at` instant for all three timestamps it wrote separately before. `src/domain/services/document_library_filing_service.py` — `supersede_retention_until` extracted as the read-only form of the supersede clock; `apply_supersede_retention` rewritten to call it and is behaviour-identical (pinned by test).
- **Models:** `ControlledDocument.retention_period_years` **removed**. No column added anywhere.
- **APIs:** No wire change. `retention_period_years` was never on a request or response schema — `DocumentCreate` did not accept it and no response model exposed it, so no client can observe the column's removal. `POST /{id}/obsolete` still returns `retention_end_date`, which was already declared nullable in the handler (`… if record.retention_end_date else None`) and can now actually be `null`.
- **Database:** ONE alembic revision `20261104_lib_cut1b_drop`, sole head, revises `20261103_lib_steward14`. One `DROP COLUMN`. No data written in either direction, on any table.
- **Frontend:** None. No `.ts`/`.tsx` file references the column — asserted by test.
- **Config/env/flags:** None.
- **Dependencies:** None new.
- **Specs:** None. `taxonomy.json` and `steward_retention_decisions.json` untouched.
- **Scripts:** None.
- **CI:** No workflow change.
- **Tests:** NEW `tests/unit/test_lib_cut1b_drop_control_retention_years.py` (26). Two alembic tip-head pins advanced (`test_job_lifecycle_ux_w4`, `_w5`). No existing test weakened, skipped or rewritten.
- **Docs:** ADR-0023 amendment 3; `library-cut1-retention-access-sor.md` §CUT-1b + head line; F-7 §2 disposition row + implementation-waves row.

### Why a read, and not a write

The control layer asking the Register a question is the convergence. The control layer *writing* the Register's `retention_until` would be a second writer of the one clock — the same defect this slice removes, arriving from the other direction — and marking a control record obsolete is not, in general, the Register's supersede event (the Register has its own supersede path in `supersede_prior_approved_by_pel_doc_ref`). `_archive_retention_end_date` therefore only reads, and a test asserts `supersede_retention_until` leaves the document unmodified.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** The column is unreachable from any API, schema, script or frontend file, so removing it is invisible on the wire. The only behaviour change is which value lands in `obsolete_document_records.retention_end_date` for *new* obsolescences.
- **Tolerant reader / strict writer applied?** Yes, in the direction that matters. The derivation is a tolerant reader: an absent anchor, a cross-tenant or stale `library_document_id`, a policy the CUT-1 grammar refused, and a legacy row with no policy all return `None` rather than raising or guessing. The migration tolerates an absent table and an absent column (the WI-2 / WJ-0 / CUT-1 / STEWARD-14 pattern) and is idempotent in both directions.
- **Breaking changes:** None on the wire. One deliberate behaviour change: a new obsolete record can now carry `retention_end_date = NULL` where it previously always carried "seven years from today". That is the point — the previous value was fabricated. `retention_required` stays `True`, so a NULL end date reads as "keep, pending a decision", not "no retention".
- **Migration plan:** Forward-only `DROP COLUMN` on `controlled_documents`, guarded by an inspector check. Runs on PostgreSQL and on the SQLite parts of the suite use (verified — §5).
- **Rollback strategy (DB):** `alembic downgrade 20261103_lib_steward14` recreates the column as `Integer NOT NULL DEFAULT 7`, exactly as `20260711_create_controlled_documents` built it. **This is a schema restore, not a data restore, and the revision's docstring says so.** Every existing row will read seven whether or not seven was ever its value. The point of the downgrade is that an older application image expecting the column can start; it is not a way to recover a retention decision, because the column never held one.

### Safety invariants

Disposal hard-deletes, so the only acceptable direction is "keeps things longer, or refuses to answer".

1. **Nothing gets a shorter clock than before.** The value being removed was seven years for every document. Every replacement path either produces the category's own (longer, for the forty-year categories) period, the date the Register already held, or `NULL` — and `NULL` never reaches a disposal queue. `obsolete_document_records` is not a disposal queue in the first place: nothing in the codebase reads `retention_end_date` to delete anything.
2. **Calendar years, not `* 365`.** `test_the_years_are_calendar_years_not_365_day_years` asserts a forty-year clock lands on the calendar date and is strictly later than the old `timedelta(days=40 * 365)` would have put it.
3. **Seven is unreachable.** `test_a_forty_year_record_gets_forty_years_not_citations_seven`, plus `test_the_control_record_holds_no_retention_field_under_any_name` so the default cannot come back wearing a different label.
4. **Existing archive rows are not re-dated.** The migration writes no data. Re-dating an archive nobody re-reviewed is the same error that made CUT-1c a deferred slice rather than a quick win.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| F-7 §2 retention homes | 2 live SoRs — the Register row, and a parallel integer on the control record | **1**. `controlled_documents` holds no retention fact under any name; asserted by test |
| Citation (ATLAS) flat 7y | Retired for the Register (STEWARD-14) but **still written on every controlled-document INSERT** | **Not written anywhere.** No `default=7`, no `* 365`, no application or alembic code path names the column |
| R19 (retention is years + a basis, disposal date calculable) | Control archive date derived from a number with no basis at all | Derived from the Register's `retention_years` + `retention_anchor` + `retention_basis`, or refused as NULL |
| Premature-destruction risk | A 40-year record's archive was dated 7 × 365 days out | Category period, in calendar years, or NULL. Never shorter |
| Fail-safe on an unanswerable case | Always produced a date (seven years) | Produces `NULL` for 6 named cases; `retention_required` stays `True` so it reads as "keep" |
| Cross-tenant read on the derivation path | n/a (no read) | Tenant-scoped `SELECT`; a foreign Register row yields `NULL`, not another tenant's policy. Asserted by test |
| Register clock has one writer | `apply_supersede_retention` | Unchanged — the control layer reads through the shared helper and writes nothing. Asserted by test |
| One alembic head | `20261103_lib_steward14` | `20261104_lib_cut1b_drop`, still sole head |
| Anti-dupe (F-3 / L-49) | 7 file homes, 0 twins, critical 0 | Unchanged: no new table, no new file home, one fewer duplicate column |
| Import boundaries (D09) | Clean | Clean — the route imports a `src/domain/services` peer it already imports four others from |

## 4) Acceptance Criteria (AC)

- [x] **AC-01 (column gone):** `controlled_documents.retention_period_years` is dropped by `20261104_lib_cut1b_drop` and absent from `ControlledDocument.__table__` and from the mapper
- [x] **AC-02 (no writer):** No `default=7` and no retention column of any name remains on the control record; a rename would fail `test_the_control_record_holds_no_retention_field_under_any_name`
- [x] **AC-03 (no reader):** No file under `src/` or `scripts/` and no `.ts`/`.tsx` under `frontend/src/` references the column in code; within `alembic/versions/` only the create revision and this drop revision name it outside a docstring
- [x] **AC-04 (derived from the SoR):** The obsolete archive's `retention_end_date` comes from the Register row via `supersede_retention_until`, the same helper the Register's own supersede path writes through
- [x] **AC-05 (fail-safe):** Unanchored, cross-tenant, stale-id, no-policy, event-anchored and indefinite all yield `NULL`; `retention_required` stays `True`
- [x] **AC-06 (calendar-exact):** Years are added as calendar years, not `* 365`; a forty-year clock is strictly later than the old expression produced
- [x] **AC-07 (naive datetime):** The derived value is naive UTC, matching `obsolete_document_records.retention_end_date` (`timestamp without time zone`) — the asyncpg contract this module documents in `_utcnow`
- [x] **AC-08 (read, not write):** Deriving the date does not mutate the Register row; `apply_supersede_retention` is behaviour-identical after the extraction
- [x] **AC-09 (alembic):** `20261104_lib_cut1b_drop` is the sole head, revises STEWARD-14, is declared in exactly one file, contains exactly one drop operation, writes no data in either direction, and tolerates an absent table or column
- [x] **AC-10 (honest downgrade):** Downgrade restores `Integer NOT NULL DEFAULT 7` and states in the revision that the values do not come back
- [x] **AC-11 (docs):** ADR-0023 amendment 3, CUT-1 design note §CUT-1b, and F-7 §2 all record the drop; no doc still says the column is not dropped
- [ ] **AC-12:** Full CI green on this SHA

## 5) Testing Evidence (link to runs)

Run locally at this SHA on Python 3.11.15 with the repo's pinned toolchain:

- [x] `pytest tests/unit/test_lib_cut1b_drop_control_retention_years.py` — **26 passed**, none skipped
- [x] `pytest tests/unit/test_job_lifecycle_ux_w4.py tests/unit/test_job_lifecycle_ux_w5.py` — **123 passed** (the two advanced tip-head pins)
- [x] `pytest tests/unit -k "retention or document_control or filing or disposal or obsolete or cut1 or steward or library or supersede"` — **432 passed, 2 skipped** (both pre-existing: `notification_logs` / `token_blacklist` declared operational rather than retention-governed)
- [x] `pytest tests/unit tests/contract` — **6931 passed, 0 failed** (79 skipped, 59 xfailed). Baseline on the STEWARD-14 tip was 6906 passed / 78 skipped; the delta is this PR's 26 new tests, and the one-test difference in the skip count is the order-dependent `test_write_contract_roundtrip` probe skips, which vary between runs on an unchanged tree
- [x] `black --check src/ tests/` — clean (1406 files); `isort --check-only --settings-path pyproject.toml src/ tests/` — clean
- [x] `flake8 src/ tests/ --count` — **0**
- [x] `mypy src/ --config-file pyproject.toml` — **Success: no issues found in 601 source files**
- [x] `python scripts/check_import_boundaries.py` — **OK: All import boundaries respected**
- [x] `python scripts/validate_library_anti_dupe.py` — file_homes 7/7, coverage_twins 0, freetext 0, **critical=0, advisory=0**
- [x] `python scripts/validate_migration_naming.py` — 257 checked, **0 violations**
- [x] `python scripts/validate_schema_constraints.py` / `validate_tenant_id_not_null.py` — **critical=0** (pre-existing `WebhookSubscription.url` advisory only)
- [x] `python scripts/check_adr_lifecycle.py` — **All 24 ADRs pass**
- [x] `alembic heads` (via `ScriptDirectory`, exercised by the W4/W5 pins) — `['20261104_lib_cut1b_drop']`, single; `down_revision` = `20261103_lib_steward14`
- [x] Migration exercised on SQLite (ad-hoc probe, not committed): upgrade drops exactly that column, leaves sibling columns and all three seeded rows intact, and is idempotent on a second run; downgrade restores the column `NOT NULL DEFAULT 7` with every row reading `7` — including the row that had held `40`, which is exactly why it is called a schema restore; both directions are tolerated against a database with no `controlled_documents` table at all, without raising
- [ ] Full CI on this PR — pending
- [ ] Staging / Prod tip verify — after merge

**Not verified locally:** `alembic upgrade head` against PostgreSQL and the `alembic check` drift gate (no local database). The model and the migration were changed together and in the same direction, so there is nothing for `alembic check` to find; the DDL is a plain `DROP COLUMN` and the counting SQL is ANSI, both executed against SQLite as above. The obsolete route itself was verified by unit-testing `_archive_retention_end_date` directly against an in-memory `documents` table — the `@postgres_only` integration test `test_obsolete_writes_naive_obsolete_and_retention_dates` is what exercises the full endpoint against Postgres, and it runs in CI, not here. The production row distribution of the dropped column was **not** observed (no operator access from the authoring environment); the migration logs it at upgrade time instead.

## 6) Critical Journeys Verified (CUJ)

- [x] **CUJ-01 — Obsolete a controlled document anchored to a forty-year Register record.** Previously the archive was dated seven years out. It is now dated forty calendar years from the day it was obsoleted. Covered by `test_a_supersede_anchored_register_row_starts_its_clock_at_obsolescence`, `test_the_years_are_calendar_years_not_365_day_years`, `test_a_forty_year_record_gets_forty_years_not_citations_seven`.
- [x] **CUJ-02 — Obsolete a document the Register cannot answer for.** An unanchored control record, a pre-CUT-1 legacy row, an event-anchored rule, an indefinite rule, a cross-tenant id and a stale id all record `retention_end_date = NULL` with `retention_required = True`. Nothing raises and nothing 500s. Covered by six tests in §2 of the new module.
- [x] **CUJ-03 — The Register's own supersede path is unaffected.** `apply_supersede_retention` still never brings a disposal date forward and still leaves a non-supersede row alone, after being rewritten to share the helper. Covered by `test_apply_supersede_retention_still_writes_through_the_shared_helper`, `test_apply_supersede_retention_leaves_a_non_supersede_row_alone`, `test_reading_the_supersede_date_does_not_write_it`, plus CUT-1's and STEWARD-14's unmodified retention suites (431 passed, above).
- [x] **CUJ-04 — The default cannot come back.** Re-adding the column, re-adding it under a different name, or reading it from application code, the frontend, or a future alembic revision each fail a named test rather than quietly restoring a second SoR.

## 7) Observability & Ops

- **Logs:** `20261104_lib_cut1b_drop` logs, at `alembic.runtime.migration` INFO immediately before the `DROP`, the total row count and how many rows held a value other than the default seven. Production row counts could not be queried from the authoring environment, so the deploy log is the record of what was actually destroyed rather than an assertion made in advance. If that second number is zero — which the code makes likely, since no route, schema or script ever set the column — the drop destroyed only the default. A non-zero count is then a records question about specific documents, visible rather than inferred. It also logs and skips when the column is already absent.
- **Metrics / Alerts:** None new.
- **Runbook:** `docs/governance/library-cut1-retention-access-sor.md` §CUT-1b explains where an obsolete archive's date now comes from and the six cases that produce `NULL`. F-7 §2 records the disposition.
- **Records action outside this repository:** `IMS 052` still records these documents as living in Citation with a flat seven-year retention. It must be updated or withdrawn to match. Code cannot do this, and it remains the last open step of the Citation cutover.

## 8) Release Plan (Local → Staging → Canary → Prod)

- Squash-merge to `main` when CI is green. Parent merges; this PR does not self-merge.
- Promote through `CI - Default` → `Build, Push and Deploy to Azure` (staging then production). `20261104_lib_cut1b_drop` runs in the deploy's `alembic upgrade head`.
- **Ordering note:** the drop is not backward-compatible with the *previous* application image, which still maps the column. The deploy runs `alembic upgrade head` and rolls the image together, so the exposure is the roll window. A `SELECT *`-style read from an old replica during that window would fail on the missing column; nothing in this codebase does that (the ORM enumerates columns), but it is the honest description of the risk in a column drop.
- **DONE bar:** tip SHA LIVE on STG *and* PROD with healthz 200 and the ACA image tag containing the tip SHA. Merge alone is not DONE.

## 9) Rollback Plan (Mandatory)

- **Rollback trigger:** `alembic upgrade` failure on staging; a 500 from `POST /document-control/{id}/obsolete`; any evidence that an obsolete archive record is being dated earlier than the Register's policy allows.
- **Rollback steps:** Revert the merge commit on `main` and let the pipeline deploy the reverted state; for a backend-only regression, `Emergency Rollback - Production` restores the previous container image first. Because the reverted image maps the column again, the database must go back too: `alembic downgrade 20261103_lib_steward14` recreates it as `Integer NOT NULL DEFAULT 7`. **That restores the schema, not the values** — every row will read seven. Since seven is exactly what the column held for every row that was never edited by hand, and nothing in the codebase ever set it to anything else, the practical loss is nil; the migration log written at upgrade time says whether that was true on this database. `documents.retention_until` and `obsolete_document_records` are not written by this revision in either direction, so no document and no archive loses a retention date on rollback.
- **Owner:** Platform Engineering (Library spine) — David Harris

## 10) Evidence Pack (links)

- CI run(s): linked once checks complete on this SHA
- Base tip: `6551434021074c39ea287ab5924146dfac850ae4` (STEWARD-14 / CIT-1 `#1698`)
- Authority: ADR-0023 (+ CUT-1, STEWARD-14 / CIT-1, and CUT-1b amendments), F-7 §2, Northern Star R19, PEL-HSEQ-5014 v6
- Design note: `docs/governance/library-cut1-retention-access-sor.md` §CUT-1b
- Depends: CUT-1 `#1695` LIVE, STEWARD-14 / CIT-1 `#1698` LIVE (the Register retention columns and the decisions that populate them)

## 11) Honest remainder (not defects introduced here)

- **Existing `obsolete_document_records` rows keep their fabricated seven-year dates.** The migration does not re-date them, deliberately: recomputing an archive date for records nobody re-reviewed is exactly the error that made CUT-1c a deferred slice. Nothing reads those dates to delete anything, so they are stale data rather than a disposal risk — but they are stale, and a future slice that makes the control archive actionable must clean them first.
- **CUT-1c is still deferred.** Rows filed before CUT-1 carry no `retention_anchor`, so `supersede_retention_until` returns whatever `retention_until` the old parser gave them, or `None`. For a control record anchored to such a row the archive date is therefore `NULL`. That is the fail-safe answer and it is honest, but it means the derivation is only as good as the Register row, and for legacy rows the Register row is not yet good.
- **The obsolete archive is not surfaced anywhere.** No UI shows `retention_end_date`, so a `NULL` that means "a steward must decide" is currently visible only in the database. Surfacing "kept until, because" belongs with the WJ-1 Front Sheet.
- **Other flat seven-year retentions exist and are out of scope.** `src/core/retention_config.py` (incidents, complaints, audit runs/logs at 2555 days) and `AuditLogConfig.retention_days` are platform data-retention policy for non-document entities; `EvidenceRetentionPolicy.STANDARD`'s docstring mentions seven years for case evidence. F-7 §2 marks all of these **keep** — they are not document-library retention and CUT-1b does not touch them. They are named here so "no flat seven anywhere" is not claimed more broadly than it is true.
- **The integration test `test_obsolete_writes_naive_obsolete_and_retention_dates` now exercises the NULL path.** It creates an unanchored control document and asserts the endpoint returns 200, which it still does; its name and assertion message mention `retention_end_date`, which is now `null` for that document. The test is correct and unmodified — it tests that the endpoint does not 500 on a naive-datetime bind — but a reader could take its name as a claim that a date is always written. Left alone rather than edited, per "no test rewritten to suit a change".
- **Control `document_access_logs` is still a second access-log spine** (F-7 §3, "merge writers once control folds"). Untouched here.
- **UX Functional Coverage Gate** is expected to be irrelevant to this PR (no frontend change) and was not treated as blocking, per the standing instruction on this slice.

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Dependency LIVE — STEWARD-14 / CIT-1 `#1698` in production (`main` = STG = PROD at `65514340`); branched from that tip
- [ ] **Gate 2:** CI green on this SHA
- [x] **Gate 3:** One alembic head (`20261104_lib_cut1b_drop` on STEWARD-14); no parallel revision; exactly one DDL operation; no data write; no `taxonomy.json` edit; no frontend; no `collaborative_*`
- [x] **Gate 4:** Anti-dupe gate clean (one duplicate column removed, none added; no new file home). **No test weakened, skipped or rewritten.** Two tip-head pins advanced per the WI-1 / WI-2 / WJ-0 / CUT-1 / STEWARD-14 precedent — the only change is the expected head string and its failure message.
- [ ] **Gate 5:** DONE = tip LIVE on STG + PROD with healthz 200 and ACA image at tip SHA
