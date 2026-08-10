# Change Ledger (CL-LIB-STEWARD14-CIT1-CITATION-CUTOVER)

**Base:** branched from `origin/main` tip `c7d507d91e20c104781e16eaddaf5b5b2c10e7f8` (WJ-1-M1 `#1697`). CUT-1 `#1695` is LIVE, so `document_categories.retention_years` / `retention_anchor` already exist in production.

## 1) Summary

- **Feature / Change name:** STEWARD-14 + CIT-1 — the fourteen accepted category retention decisions, and the Citation (ATLAS) cutover they unblock (ADR-0023 amendment 2 / F-7 §2; Northern Star R19)
- **User goal (1–2 lines):** Every filable category can now calculate a disposal date, so "how long do we keep this, and why" has an answer for the whole Register — and the answer survives a reseed. Citation's flat "7 Years / all employees" position stops being the fallback truth for library retention.
- **In scope:** `specs/governance-library/steward_retention_decisions.json` (new SSOT); `library_steward_retention` (new module, one precedence point); seed path made decision-first; readiness gate classifies decision-first, reports provenance and orphans; `--fail-on-blockers` wired into `CI - Default`; alembic `20261103_lib_steward14`; ADR-0023 amendment + CUT-1/F-7 doc amendments; tests
- **Out of scope:** dropping `controlled_documents.retention_period_years` (CUT-1b); backfilling legacy `documents.retention_until` / `documents.retention_*` (CUT-1c); any change to `taxonomy.json` `retention_rule`; any frontend; any change to the filing/supersede precedence CUT-1 shipped
- **Feature flag / kill switch:** **None, deliberately.** See §7 and the "Citation flag vs documented retirement" note below. There is no Citation system-of-record flag in QGP and none was invented — QGP does not read retention from Citation at runtime, so the flag would have had nothing on the other end of it.

### The two defects this closes

**1. CUT-1 left fourteen categories with no executable retention, so Citation was not actually retired for them.** ADR-0023's amendment says so explicitly: *"Citation (ATLAS) is not retired for a category until a steward has given that category a retention decision."* Fourteen of the seventy-three filable categories name two periods or a condition one integer cannot hold. All fourteen are now decided, and the gate reports **0 blockers**.

**2. The seed would have erased any decision on the next reseed.** `seed_document_categories` re-derived both retention columns from prose on *every* run and wrote the result unconditionally. CUT-1's own design note told stewards to resolve a blocker by setting the two columns on the `document_categories` row — so the documented workflow was one a redeploy, a CI smoke run, or an admin clicking "reload seed" would silently undo, re-opening the cutover gate on production while CI stayed green against the checked-in files. The decision is now an **input** to the seed, so a reseed restores it.

### The fourteen decisions

Accepted 2026-08-10 by the Governance Library steward. **`taxonomy.json` `retention_rule` is unchanged** — the prose is the governance authority and the R19 basis, and nothing in it was shortened, lengthened or reworded to make a decision fit.

| Category | Prose (unchanged) | Decision |
| --- | --- | --- |
| 02.02 COSHH | `Current; 40 years where linked to exposure monitoring` | 40y · supersede |
| 02.04 Method Statements & SSoW | `Current + 3 years (contract life + 6 years if contractual)` | 6y · supersede |
| 02.05 Permits to Work | `3 years (longer if incident-related)` | 3y · issue |
| 02.06 Checklists & Inspection Forms | `Completed: 3 years` | 3y · issue |
| 02.07 Incident Management | `3 years minimum (to age 21 if a minor); investigations 6 years` | 6y · issue |
| 02.08 Occupational Health | `Health records: 40 years` | 40y · issue |
| 03.04 Drills, Evacuation & PEEPs | `3 years (PEEPs: current, restricted)` | 3y · supersede |
| 04.08 Asbestos | `Register current; exposure records 40 years` | 40y · supersede |
| 04.10 Insurance | `EL certificates: 40 years recommended; others 6 years` | 40y · issue |
| 06.02 Daily Walkaround & Defect Reports | `15 months (longer if incident-related)` | 2y · issue |
| 06.04 O-Licence & Tachograph | `Tacho data 12 months; working time records 2 years` | 2y · issue |
| 07.03 External Audits & Certification | `Certificates current; reports 6 years` | 6y · supersede |
| 08.03 Waste Management | `Consignment notes 3 years; transfer notes 2 years` | 3y · issue |
| 08.04 Environmental Aspects & Spill Response | `Register current; incidents 6 years` | 6y · supersede |

One principle explains all fourteen, and it is **enforced by test**, not left as prose:

- Where the prose names more than one period, **the longest leg governs** the whole category. Taking the shorter leg is exactly the pre-CUT-1 defect.
- A period stated in months **rounds up** to the next whole year (R19 makes retention a count of years).
- Where the prose says the current issue is kept, the anchor is **`supersede`**, so a live document has no disposal date at all.
- A per-document extension the register cannot evaluate ("longer if incident-related", "to age 21 if a minor", "if contractual") is **not** a category default; it stays a steward action on the document.

## 2) Impact Map (what changed)

- **Backend:** NEW `src/domain/services/library_steward_retention.py` — loads and validates the decision file and owns the single precedence point `resolve_category_retention(taxonomy_id, retention_rule)`. `document_category_seed_data` projects the two columns in `load_taxonomy_categories` (they are `DocumentCategory` columns, so the function named for building those rows now builds them). `document_category_service._machine_readable_retention` reads the projection off the row instead of deriving a second opinion.
- **Models:** None. No new column, no new table, no schema change anywhere.
- **APIs:** None. `DocumentCategoryResponse` exposes `retention_rule` only; the two machine-readable columns are not on the wire. `DocumentResponse`'s three CUT-1 retention fields are unchanged in shape — fourteen categories' *values* stop being NULL.
- **Database:** ONE alembic revision `20261103_lib_steward14`, sole head, revises `20261102_lib_cut1_sor`. Pure data — `UPDATE document_categories SET retention_years, retention_anchor WHERE taxonomy_id = …` for exactly fourteen rows. No DDL. `documents.retention_until` is not written in either direction.
- **Frontend:** None.
- **Config/env/flags:** None.
- **Dependencies:** None new.
- **Specs:** NEW `specs/governance-library/steward_retention_decisions.json`. `taxonomy.json` **untouched**.
- **Scripts:** `citation_cutover_readiness.py` — classifies decision-first, reports `source` (`steward_decision` / `taxonomy_prose`) and the rationale per category, and reports **orphan** decisions (a `taxonomy_id` no filable category carries). `--fail-on-blockers` now also fails on an orphan and prints a `::error::` line.
- **CI:** `schema-constraint-lint` (already in `all-checks`) gains a `Citation cutover readiness gate (CIT-1)` step running `--fail-on-blockers`.
- **Tests:** NEW `tests/unit/test_lib_steward14_retention_decisions.py` (86). Two alembic tip-head pins advanced (`test_job_lifecycle_ux_w4`, `_w5`). One CUT-1 assertion tightened — see Gate 4.
- **Docs:** ADR-0023 second amendment; `library-cut1-retention-access-sor.md` §STEWARD-14 + corrected "Resolving a blocker"; F-7 implementation-waves row; `specs/governance-library/README.md` file table.

### Why the decision file, and not extra keys in `taxonomy.json`

Two different facts, two homes (F-7 §4). `retention_rule` is the governance prose; the decision is a steward's *reading* of it, with an author, a date and a rationale. Putting years/anchor beside the prose would make one file answer for both and lose the attribution R19 asks for. Conversely the decision file copies **no prose** — a test asserts that none of the fourteen `retention_rule` strings appears anywhere in it.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Purely additive at the data level. No schema change, no API change, no removed behaviour.
- **Tolerant reader / strict writer applied?** Yes, in the direction that matters. The decision file is validated strictly on load — a bad anchor, a non-positive year count, a duplicate `taxonomy_id`, a missing rationale or missing attribution **raises**, and the whole set is refused rather than partially read. A half-read decision set would be written to the database by the next reseed with no way to tell which categories were decided and which derived. The migration tolerates absent columns (as WI-2 / WJ-0 / CUT-1 do) and is idempotent.
- **Breaking changes:** None on the wire. One behaviour change by design: documents in the fourteen categories can now acquire a `retention_until`, where under CUT-1 they never could. That is the point of the slice, and §"Safety invariants" below is how it is kept honest.
- **Migration plan:** Forward-only data UPDATE on fourteen rows matched by `taxonomy_id`, using ANSI SQL that runs on PostgreSQL and on the SQLite parts of the suite use. The decision table in the migration is a **frozen literal**, not an import of the JSON — a migration that reads live files changes meaning whenever those files change. A test asserts the snapshot still equals the decision file, so drift fails CI.
- **Rollback strategy (DB):** `alembic downgrade 20261102_lib_cut1_sor` sets both columns back to NULL for exactly those fourteen `taxonomy_id` values — the state CUT-1 left them in, since every one was refused by the prose grammar, so there is no earlier non-NULL value to restore. NULL is also the fail-safe direction: no executable policy means no disposal date, so the effect of a downgrade is that those documents are **kept**. `retention_rule` prose and `documents.retention_until` are untouched by both directions.

### Safety invariants

Disposal hard-deletes the row and the blob, so the only acceptable direction is "keeps things longer". Three assertions, all over all fourteen:

1. **`test_no_decision_is_shorter_than_the_longest_period_its_prose_names`** — the accepted period, in months, is ≥ the longest period the prose names. This is the strong one: a decision shorter than any leg of its prose has silently discarded a governance requirement, which is precisely how the pre-CUT-1 parser turned *"3 years minimum …; investigations 6 years"* into 3.
2. **`test_no_decision_disposes_earlier_than_the_pre_cut1_parser`** — reproduces the pre-CUT-1 expression (first `\d+ years?` match, from approval, 365-day years) and asserts the new earliest disposal date is never earlier. Thirteen of fourteen are strictly later.
3. **`test_prose_naming_a_kept_current_issue_is_anchored_on_supersede`** — a rule that keeps the current issue cannot start its clock at issue. Anchoring one of those at `issue` is the CUT-1 defect arriving by a new route.

And `test_steward14_did_not_edit_the_taxonomy_prose` asserts all fourteen rules are *still* rules the CUT-1 grammar refuses — if one now parses on its own, the prose was quietly edited and the "decision" is decorative.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| R19 retention computable, with a basis | 59/73 categories; 14 refused with a named reason | **73/73**. Basis is still the taxonomy prose; the decision adds an author, a date and a rationale |
| ADR-0023 cutover precondition (F-7 §2) | Gate runnable, **14 blockers**, `--fail-on-blockers` opt-in | Gate **0 blockers**, wired into `CI - Default` so a re-opened blocker fails the build |
| Citation (ATLAS) flat 7y / all-employees retention | Not retired for 14 categories; effectively the fallback truth | **Retired for the library Register.** Per-category gate clear for every category; recorded in ADR-0023 amendment 2 |
| Reseed vs a steward decision | Reseed silently reset the two columns to the prose derivation, re-opening the gate on production | Decision is a seed input; reseed **restores** it. Pinned by `test_reseeding_does_not_wipe_the_steward_decisions` |
| Provenance of a category's retention | Indistinguishable — a number was a number | Gate reports `source` = `steward_decision` \| `taxonomy_prose` plus the rationale; the SSOT names who accepted it and when |
| Inert / mis-keyed decision | n/a | Reported as an **orphan** and fails `--fail-on-blockers`. An orphan is worse than a blocker: it reads as cleared while changing nothing |
| Premature destruction risk | 14 categories kept indefinitely (safe but not an answer) | No decision is shorter than the longest period its prose names, and none disposes earlier than pre-CUT-1 — both asserted |
| Governance prose integrity | — | `taxonomy.json` unchanged; decision file copies no prose; all 14 rules still refused by the grammar on their own — all three asserted |
| Anti-dupe (F-3 / L-49) | 7 file homes, 0 twins, critical 0 | Unchanged: 7/7, 0 twins, **critical=0, advisory=0**. No new table, no new file home |
| One alembic head | `20261102_lib_cut1_sor` | `20261103_lib_steward14`, still sole head |
| Import boundaries (D09) | Clean | Clean — the new module is a pure `src/domain/services` peer with no ORM/session import |

## 4) Acceptance Criteria (AC)

- [x] **AC-01 (STEWARD-14 recorded):** All fourteen decisions live in one SSOT with `accepted_by`, `accepted_on` and a rationale each; the file holds only `taxonomy_id` + years + anchor + rationale and copies no taxonomy prose
- [x] **AC-02 (prose untouched):** `taxonomy.json` `retention_rule` is byte-identical to `main`, and all fourteen rules are still refused by the CUT-1 grammar on their own
- [x] **AC-03 (never shorter):** No decision is shorter than the longest period its prose names, and none brings a disposal date forward of pre-CUT-1
- [x] **AC-04 (anchors):** Every rule that keeps the current issue is anchored on `supersede`, so a live document has no disposal date
- [x] **AC-05 (seed prefers the decision):** `load_taxonomy_categories` / `_machine_readable_retention` / `seed_document_categories` all resolve decision-first; a category with no decision still derives from prose, and an undecided unreadable rule still projects to NULL
- [x] **AC-06 (reseed is non-destructive):** Four consecutive reseeds leave all fourteen decisions intact, and a reseed restores a decision cleared by hand
- [x] **AC-07 (gate clear):** `citation_cutover_readiness` reports `blockers == 0`, `blocker_reasons == {}`, 14 decisions applied, 0 orphaned, and still accounts for all 73 filable categories (42 computable + 31 clockless)
- [x] **AC-08 (gate wired):** `--fail-on-blockers` runs in `CI - Default` (`schema-constraint-lint`, which is in `all-checks`), and fails on an orphan decision as well as a blocker
- [x] **AC-09 (alembic):** `20261103_lib_steward14` is the sole head, revises CUT-1, exactly one file declares it, carries no DDL, never names `retention_until` or `controlled_documents`, and downgrade clears only the fourteen
- [x] **AC-10 (no drift):** The migration's frozen decision table still equals the decision file, asserted in CI
- [x] **AC-11 (ADR/doc amendment):** ADR-0023 amendment 2 records the retirement; the CUT-1 design note's now-incorrect "set the columns on the row" instruction is corrected rather than left to mislead
- [ ] **AC-12:** Full CI green on this SHA

## 5) Testing Evidence (link to runs)

Run locally at this SHA on Python 3.11.15 with the repo's pinned toolchain:

- [x] `pytest tests/unit/test_lib_steward14_retention_decisions.py` — **86 passed**
- [x] `pytest tests/unit tests/contract` — **6906 passed, 0 failed** (78 skipped, 59 xfailed)
- [x] `black --check src/ tests/` — clean (1405 files); `isort --check-only --settings-path pyproject.toml src/ tests/` — clean
- [x] `flake8 src/ tests/ --count` — **0**
- [x] `mypy src/ --config-file pyproject.toml` — **Success: no issues found in 601 source files**
- [x] `python scripts/check_import_boundaries.py` — **OK: All import boundaries respected**
- [x] `python scripts/validate_library_anti_dupe.py` — file_homes 7/7, coverage_twins 0, freetext 0, **critical=0, advisory=0**
- [x] `python scripts/validate_migration_naming.py` — 256 checked, **0 violations**
- [x] `python scripts/validate_schema_constraints.py` / `validate_tenant_id_not_null.py` — **critical=0** (pre-existing `WebhookSubscription.url` advisory only)
- [x] `python scripts/check_adr_lifecycle.py` — **All 24 ADRs pass**
- [x] `alembic heads` (via `ScriptDirectory`) — `['20261103_lib_steward14']`, single; `down_revision` = `20261102_lib_cut1_sor`
- [x] `python -m scripts.governance.library.citation_cutover_readiness --fail-on-blockers` — **exit 0**; 73 filable, 42 executable, 31 clockless, **0 blocked**, 14 decisions applied, 0 orphaned
- [x] Migration exercised on SQLite (ad-hoc probe, not committed): upgrade sets exactly the 14 expected `(taxonomy_id, years, anchor)` triples and nothing else; downgrade returns those 14 to NULL and leaves all 73 `retention_rule` prose values intact; upgrade is idempotent across repeated runs; the columns-absent path is tolerated without raising
- [ ] Full CI on this PR — pending
- [ ] Staging / Prod tip verify — after merge

**Not verified locally:** `alembic upgrade head` against PostgreSQL and the `alembic check` drift gate (no local database). This revision adds no columns and no models changed, so there is nothing for `alembic check` to find; the data SQL is ANSI and was executed against SQLite as above. CI runs both.

## 6) Critical Journeys Verified (CUJ)

- [x] **CUJ-01 — File into a previously blocked category and get a real retention:** A document is approved into 02.08 Occupational Health. Under CUT-1 it carried no policy and no disposal date; it now carries 40 years anchored at issue, with the taxonomy prose as its basis. Covered by `test_the_seed_loader_projects_the_decision_onto_the_category_columns`, `test_seed_writes_the_accepted_decisions_to_the_category_rows`, `test_the_basis_stays_the_taxonomy_prose`, and CUT-1's unmodified `test_steward_override_on_the_category_wins_over_the_prose` (the filing path already preferred the stored columns).
- [x] **CUJ-02 — Dispose without destroying early:** No decision can make a document disposable before its prose allows, or before the pre-CUT-1 behaviour did; a supersede-anchored decision gives a live document no disposal date at all and starts its clock only on supersede. Covered by `test_no_decision_is_shorter_than_the_longest_period_its_prose_names`, `test_no_decision_disposes_earlier_than_the_pre_cut1_parser`, `test_prose_naming_a_kept_current_issue_is_anchored_on_supersede`, `test_a_supersede_anchored_decision_gives_a_live_document_no_disposal_date`, plus CUT-1's whole-taxonomy invariant and the W5 disposal policy-freeze suite (both unmodified, still green).
- [x] **CUJ-03 — Reseed / redeploy without losing the decision:** An admin reloads the seed, or the platform redeploys and re-runs it. All fourteen decisions are still on the rows afterwards, and a decision someone cleared by hand is restored. Covered by `test_reseeding_does_not_wipe_the_steward_decisions`, `test_reseed_restores_a_decision_someone_cleared_by_hand`, `test_seed_leaves_undecided_unreadable_categories_null`.
- [x] **CUJ-04 — The gate stays honest:** A taxonomy edit that re-opens a blocker, or a decision aimed at a `taxonomy_id` no category carries, fails `CI - Default` instead of quietly un-retiring Citation for that category. Covered by `test_the_citation_cutover_gate_has_no_blockers_left`, `test_the_gate_still_accounts_for_every_filable_category`, `test_the_gate_says_which_categories_were_decided_rather_than_derived`, `test_fail_on_blockers_exits_zero_now_that_the_gate_is_clear`, `test_every_decision_names_a_filable_level_2_category`.

## 7) Observability & Ops

- **Logs:** `20261103_lib_steward14` logs how many of the fourteen decisions matched a row (`alembic.runtime.migration`), so a production upgrade that matched fewer than fourteen is visible in the deploy log rather than inferred. It also logs and skips when CUT-1's columns are absent, matching the WI-2 / WJ-0 / CUT-1 pattern. No new runtime logging.
- **Metrics / Alerts:** None new. The honest signal for this slice is the readiness gate, which is a CI check rather than a gauge because its output is a list of governance decisions, not a number that trends.
- **Runbook:** `docs/governance/library-cut1-retention-access-sor.md` §"Resolving a blocker" now documents the correct route (add to the decision file with a rationale) and explicitly retracts the previous instruction to edit the row, explaining why that was unsafe. §STEWARD-14 documents the four rules a new decision must satisfy and the tests that enforce them.
- **Citation flag vs documented retirement:** There is **no** Citation system-of-record feature flag in this repository — the only `atlas`-named code is the training-matrix CSV import, a different surface. None was added. Citation is an external system QGP does not read retention from at runtime, so a `CITATION_SOR` boolean would be a switch with nothing on the other end: flipping it would change no code path, while making the retirement *look* controlled. What makes the retirement real is (a) executable retention on all 73 categories, (b) the `--fail-on-blockers` gate that keeps it that way, and (c) the ADR-0023 amendment recording the decision. **`IMS 052` still records these documents as living in Citation with a flat 7-year retention and must be updated or withdrawn to match** — a records action outside this repository, and the one remaining step of the cutover that code cannot do.

## 8) Release Plan (Local → Staging → Canary → Prod)

- Squash-merge to `main` when CI is green. Parent merges; this PR does not self-merge.
- Promote through `CI - Default` → `Build, Push and Deploy to Azure` (staging then production). `20261103_lib_steward14` runs in the deploy's `alembic upgrade head`.
- **DONE bar:** tip SHA LIVE on STG *and* PROD with healthz 200 and the ACA image tag containing the tip SHA. Merge alone is not DONE.

## 9) Rollback Plan (Mandatory)

- **Rollback trigger:** `alembic upgrade` failure on staging; the disposal queue offering candidates from any of the fourteen categories that a reviewer judges premature; `Citation cutover readiness gate (CIT-1)` failing on `main` after merge.
- **Rollback steps:** Revert the merge commit on `main` and let the pipeline deploy the reverted state; for a backend-only regression, `Emergency Rollback - Production` restores the previous container image first. If the data must also go back, `alembic downgrade 20261102_lib_cut1_sor` returns the fourteen categories to NULL — which stops them producing any disposal date at all, so the rollback direction is "keep", not "destroy". Note the revert alone is enough in practice: a reverted seed re-derives from prose and refuses all fourteen again. No document loses a retention date on downgrade; `documents.retention_until` is never written by this revision.
- **Owner:** Platform Engineering (Library spine) — David Harris

## 10) Evidence Pack (links)

- CI run(s): linked once checks complete on this SHA
- Base tip: `c7d507d91e20c104781e16eaddaf5b5b2c10e7f8` (WJ-1-M1 `#1697`)
- Authority: ADR-0023 (+ CUT-1 amendment, + STEWARD-14 / CIT-1 amendment), F-7 §2, Northern Star R19, PEL-HSEQ-5014 v6
- SSOT: `specs/governance-library/steward_retention_decisions.json`
- Design note: `docs/governance/library-cut1-retention-access-sor.md` §STEWARD-14
- Depends: CUT-1 `#1695` LIVE (the two category columns), WJ-1-M1 `#1697` merged

## 11) Honest remainder (not defects introduced here)

- **Legacy rows filed before CUT-1 still carry the old parser's date.** CUT-1c is deferred, so `documents.retention_until` is not backfilled. Worse, those rows have `documents.retention_anchor` NULL, so `apply_supersede_retention` returns early and does **not** repair them on supersede — the repair CUT-1 documented only works for rows filed with a policy on them. Nothing in this PR makes that worse, and no code here reads those rows, but it is the real state of the estate and CUT-1c should say so.
- **06.02 is the one place a document becomes disposable that was not before, measured against pre-CUT-1.** Its prose says `15 months`; the old regex matched only `\d+ years?`, found nothing, and kept those records indefinitely. The accepted 2 years is longer than the prose requires — but it is a disposal date where there was none. Measured against **CUT-1 as it is live today**, all fourteen gain a disposal date, which is the intended effect of making retention executable.
- **`controlled_documents.retention_period_years` still exists** and is still written by the control layer. CUT-1b removes it once no writer remains.
- **The decision file is not admin-editable.** Recording a new decision is a PR, which is the right cost for a governance decision that changes what gets destroyed — but it does mean a steward cannot self-serve. If that becomes a real constraint, the answer is an admin surface that writes this file through review, not a database edit that the next reseed silently reverts.
- **Retention is still not visible to a user.** `DocumentCategoryResponse` does not expose the two columns and no frontend consumes them. Surfacing "kept until, because" belongs with the WJ-1 Front Sheet.
- **UX Functional Coverage Gate** is expected to be irrelevant to this PR (no frontend change) and was not treated as blocking, per the instruction on this slice.

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Dependency LIVE — CUT-1 `#1695` in production (the two `document_categories` retention columns exist); branched from `origin/main` tip `c7d507d9`
- [ ] **Gate 2:** CI green on this SHA
- [x] **Gate 3:** One alembic head (`20261103_lib_steward14` on CUT-1); no parallel revision; no DDL; no `retention_until` write; no `controlled_documents` touch; no `collaborative_*`
- [x] **Gate 4:** Anti-dupe gate clean (no new file home, no coverage twin, no free-text standards column). **No test weakened.** Two tip-head pins advanced per the WI-1 / WI-2 / WJ-0 / CUT-1 precedent. One CUT-1 assertion tightened rather than relaxed: `test_migration_is_the_sole_head_on_wj0` matched *any mention* of `20261102_lib_cut1_sor` in `alembic/versions/`, which would have failed for any future revision naming CUT-1 as its `down_revision` — i.e. for the linear chain working as intended. Its own failure message says "exactly one file may **declare**", so the check now matches the `revision: str = …` declaration, which is the property it was written to protect. Renamed to `test_migration_declares_cut1_exactly_once_on_wj0`, and the equivalent assertion is applied to the new revision.
- [ ] **Gate 5:** DONE = tip LIVE on STG + PROD with healthz 200 and ACA image at tip SHA
