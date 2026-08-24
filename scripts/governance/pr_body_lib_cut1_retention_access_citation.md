# Change Ledger (CL-LIB-CUT1-RETENTION-ACCESS-CITATION)

**Depends:** WK-1 `#1690` and WJ-1 `#1694` LIVE — tip `c2f4e9a41fca2dc70c1f97341c755eb6afe47bea` (MAIN = STG = PROD, healthz/readyz 200).

## 1) Summary

- **Feature / Change name:** Library CUT-1 — Retention + Access converge onto one QGP system of record; Citation cutover gate (ADR-0023 / F-7 §2 §3; Northern Star R19 / R26)
- **User goal (1–2 lines):** A steward can see *why* a document is kept until a given date, and the disposal queue can no longer destroy a record earlier than its governance rule allows. Access has one vocabulary instead of two disagreeing ones.
- **In scope:** `library_retention_policy` resolver (one retention); machine-readable retention on `document_categories` + `documents`; supersede-anchored clocks; one access vocabulary in `library_rules` with the control layer folded onto it; Citation cutover readiness gate; alembic `20261102_lib_cut1_sor`; docs
- **Out of scope:** DocumentDetail / WJ-1 editor mount; any `collaborative_*` reintroduction; a second alembic head; dropping `controlled_documents.retention_period_years`; frontend surfacing; backfilling legacy `documents.retention_*`
- **Feature flag / kill switch:** None. Behaviour change is "fewer documents become disposal candidates", which is fail-safe. `LIBRARY_DISPOSAL_EXECUTE` remains `false` by default and is unchanged.

### The defect this closes

Retention was one line — `re.search(r"(\d+)\s*years?")`, first match wins, clock always starts at approval. Against the checked-in taxonomy that produced disposal dates that are **too early**, on a queue whose execute path hard-deletes the row, the blob and the vectors:

| Taxonomy rule | Before | Why it was wrong |
| --- | --- | --- |
| `3 years minimum (to age 21 if a minor); investigations 6 years` | 3 years from approval | Silently discarded the six-year investigation leg |
| `Current + superseded 6 years` | 6 years from **approval** | Rule means six years after *supersede*; a document current for ten years was disposable the day it stopped being current |
| `Life of asset + 6 years` | 6 years from approval | Clock starts when the asset goes — an event QGP does not hold |
| `Tacho data 12 months; working time records 2 years` | 2 years | Two record types, two periods; one was discarded |
| `Health records: 40 years` | 40 years, 10 days short | `timedelta(days=365*40)` drifts by the leap days |

Every rule now resolves to `(years, anchor, basis)` or to a **named refusal**. 30 of the 44 distinct rules resolve; 14 name two periods or a condition that no single integer can represent and are left for a steward. A refused rule leaves `retention_until` NULL, and NULL is never a disposal candidate — so the conservative outcome of unreadable prose is keep, not destroy.

## 2) Impact Map (what changed)

- **Backend:** NEW `src/domain/services/library_retention_policy.py`; `library_rules` (vocabulary home); `document_library_filing_service`, `document_library_lifecycle_service`, `document_library_disposal_service`, `document_category_service`
- **Models:** `documents` +`retention_years` +`retention_anchor` +`retention_basis`; `document_categories` +`retention_years` +`retention_anchor`
- **APIs:** `DocumentResponse` and `DisposalCandidateResponse` gain three optional read-only fields. `POST/PUT /api/v1/document-control` converge `access_level`; default changes `internal` → `all_staff`
- **Database:** ONE alembic revision `20261102_lib_cut1_sor`, sole head, revises `20261101_lib_wj0_drop` (WJ-0). Additive columns + category backfill + control access normalisation. `documents.retention_until` is not written in either direction
- **Frontend:** None
- **Config/env/flags:** None
- **Dependencies:** None new
- **Scripts:** NEW `scripts/governance/library/citation_cutover_readiness.py`
- **Tests:** NEW `tests/unit/test_lib_cut1_retention_policy.py` (97); two alembic tip-head pins advanced; write-contract baseline records three derived fields
- **Docs:** NEW `docs/governance/library-cut1-retention-access-sor.md`; F-7 dispositions updated; ADR-0023 amendment
- **Contract baseline:** `tests/contract/_write_contract_baseline.py` — `DocumentResponse` gains the three derived retention fields beside `retention_until`

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive columns and additive optional response fields. No endpoint, method or required field removed or added.
- **Tolerant reader / strict writer applied?** Yes. Reads tolerate NULL policy columns throughout (`getattr` defaults, `policy_from_stored` returns `None` on an unknown anchor). The write path refuses an off-vocabulary `access_level` rather than defaulting one.
- **Breaking changes:** None to the wire contract. One behaviour change: a control record anchored to a Register row now takes that row's access level instead of its own. That is the converge, and the Register is the SoR per F-7 §3.
- **Migration plan:** Forward-only additive DDL, then two data steps — project 30 readable taxonomy rules onto the new category columns, and fold `controlled_documents.access_level` onto the one vocabulary (anchored rows take the Register's level first). Both use ANSI SQL that runs on PostgreSQL and SQLite.
- **Rollback strategy (DB):** `downgrade()` drops the five added columns. `documents.retention_until` is untouched, so no document loses a disposal date. The access-vocabulary fold is deliberately **not** reversed: the parallel vocabulary is what F-7 §3 retires, and re-splitting it would restore the defect. Recorded in the migration docstring.

### Safety invariant

Converging retention may keep documents **longer**; it must never make one disposable earlier, because disposal is destruction. `test_cut1_never_brings_a_disposal_date_forward` reproduces the pre-CUT-1 expression and asserts this across **every rule in the checked-in taxonomy**. Zero violations. `apply_supersede_retention` carries the property into the data by taking the *later* of the stored and newly calculated dates, so a legacy row whose date was computed from approval is repaired on supersede rather than honoured.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| R19 retention computable (years + basis) | Free-text prose; regex guess at approval | `(years, anchor, basis)` resolved once, copied onto the document at file, or refused with a reason |
| ADR-0023 cutover prerequisite | Asserted in an ADR risk note | Runnable gate: 73 filable categories → 28 executable, 31 clockless by design, 14 blocked |
| R28 disposal answerable | Queue showed a date and category prose | Queue shows the policy the date came from, read off the document |
| R26 access vocabulary | Three literals in two modules; control layer on a fourth (`internal`) | One home (`library_rules.LIBRARY_ACCESS_LEVELS`); control folds onto it; anchored rows take the Register's level |
| Read-side RBAC | Fails closed on unknown value | Unchanged — normalisation is write-side only, so no value nobody validated becomes a grant |
| Premature destruction risk | Multi-clause and supersede-anchored rules disposed early | No rule can produce an earlier date than before; unreadable rules produce none |
| Anti-dupe (F-3 / L-49) | 7 file homes, 0 twins | Unchanged: 7/7, 0 twins, 0 critical. No new table |
| One alembic head | `20261101_lib_wj0_drop` | `20261102_lib_cut1_sor`, still sole head |
| `collaborative_*` | Dropped by WJ-0 | Not reintroduced; not referenced |

## 4) Acceptance Criteria (AC)

- [x] **AC-01 (R19):** Every taxonomy retention rule resolves to `(years, anchor, basis)` or to a named refusal; the resolver is total and no rule falls through silently
- [x] **AC-02 (safety):** No rule's disposal date moves earlier than pre-CUT-1, asserted over the whole checked-in taxonomy
- [x] **AC-03 (anchors):** A supersede-anchored rule has no disposal date while the document is current, and gets one at supersede; event-anchored and indefinite rules never get one
- [x] **AC-04 (one retention):** The policy is copied onto the document at file, so a later taxonomy edit cannot re-date filed documents; re-approval under a new anchor clears the stale date
- [x] **AC-05 (one Access):** One vocabulary home; anchored control rows take the Register level; no alias widens access; an off-vocabulary write is refused
- [x] **AC-06 (R26 unweakened):** `assert_access_level_required` still refuses `internal` and `None` on the library write path
- [x] **AC-07 (alembic):** `20261102_lib_cut1_sor` is the sole head, revises WJ-0, and exactly one file declares it
- [x] **AC-08 (no drift):** The migration's frozen backfill still agrees with the live resolver, asserted in CI
- [x] **AC-09 (cutover gate):** `citation_cutover_readiness.py` reports blockers and never proposes a number for one
- [ ] **AC-10:** Full CI green on this SHA

## 5) Testing Evidence (link to runs)

Run locally at this SHA against Python 3.11.15 with the repo's pinned toolchain:

- [x] `pytest tests/unit/test_lib_cut1_retention_policy.py` — **97 passed**
- [x] `pytest tests/unit tests/contract` — **6819 passed, 0 failed** (79 skipped, 59 xfailed)
- [x] `black --check src/ tests/` (black 26.5.1) — clean; `isort --check-only` — clean; `flake8 src/ tests/` — **0**
- [x] `mypy src/ --config-file pyproject.toml` — **Success: no issues found in 600 source files**
- [x] `python scripts/validate_library_anti_dupe.py` — file_homes 7/7, coverage_twins 0, freetext 0, **critical=0, advisory=0**
- [x] `alembic heads` — `20261102_lib_cut1_sor (head)`, single
- [x] `python -m scripts.governance.library.citation_cutover_readiness` — 73 filable, 28 executable, 31 clockless, 14 blocked
- [ ] Full CI on this PR — pending
- [ ] Staging / Prod tip verify — after merge

**Not verified locally:** `alembic upgrade head` against PostgreSQL and the `alembic check` drift gate (no local database). The ORM columns and the migration DDL were written to match exactly — `SmallInteger` / `String(20)` / `Text` on both sides — and CI runs both.

## 6) Critical Journeys Verified (CUJ)

- [x] **CUJ-01 — File and retain:** A document is approved into a category. Its retention policy is copied onto the row; an issue-anchored rule gets a disposal date immediately, a supersede-anchored one gets none until it is superseded, and an unreadable rule gets neither a date nor a fabricated number. Covered by `test_issue_anchored_rule_gets_its_date_at_approval`, `test_supersede_anchored_rule_has_no_disposal_date_while_current`, `test_event_and_indefinite_rules_get_no_date_at_all`.
- [x] **CUJ-02 — Dispose without destroying early:** The disposal queue only ever offers documents whose governance rule has genuinely expired, and shows the reviewer the policy the date came from. No taxonomy rule can produce an earlier date than it did before this change; a legacy row carrying a too-early date is repaired on supersede rather than honoured. Covered by `test_cut1_never_brings_a_disposal_date_forward`, `test_supersede_never_shortens_a_legacy_date`, and the existing W5 disposal policy-freeze suite (unmodified, still green).
- [x] **CUJ-03 — Bring under control:** A control record anchored to a Register document reports the same access level as the Register, and an off-vocabulary level is refused rather than silently stored. Covered by `test_anchored_control_record_takes_the_register_access_level`, `test_control_record_refuses_an_off_vocabulary_access_level`.

## 7) Observability & Ops

- **Logs:** The migration logs per-table skips when a table or column is absent (`alembic.runtime.migration`), matching the WI-2 / WJ-0 pattern. No new runtime logging.
- **Metrics / Alerts:** None new. The honest signal for this slice is the cutover readiness report, which is a script rather than a metric because its output is a list of business decisions, not a gauge.
- **Runbook:** `docs/governance/library-cut1-retention-access-sor.md` documents how a steward resolves a blocked category — set `retention_years` + `retention_anchor` on the category; the prose stays as the R19 basis and `taxonomy.json` needs no edit.

## 8) Release Plan (Local → Staging → Canary → Prod)

- Squash-merge to `main` when CI is green. Parent merges; this PR does not self-merge.
- Promote through `CI - Default` → `Build, Push and Deploy to Azure` (staging then production).
- **DONE bar:** tip SHA LIVE on STG *and* PROD with healthz 200 and the ACA image tag containing the tip SHA. Merge alone is not DONE.

## 9) Rollback Plan (Mandatory)

- **Rollback trigger:** `alembic upgrade` failure on staging; any 5xx on `POST/PUT /api/v1/document-control`; disposal queue returning candidates it did not return before.
- **Rollback steps:** Revert the merge commit on `main` and let the pipeline deploy the reverted state; for a backend-only regression, `Emergency Rollback - Production` restores the previous container image first. If the schema must also go back, `alembic downgrade 20261101_lib_wj0_drop` drops the five added columns. No document loses a retention date on downgrade — `retention_until` is never written by this revision. The access-vocabulary fold is not reversed by design.
- **Owner:** Platform Engineering (Library spine) — David Harris

## 10) Evidence Pack (links)

- CI run(s): linked once checks complete on this SHA
- Base tip: `c2f4e9a41fca2dc70c1f97341c755eb6afe47bea` (WJ-1 `#1694`), verified MAIN = STG = PROD
- Authority: ADR-0023 (+ CUT-1 amendment), F-7 §2 §3, Northern Star R19 / R26 / R28, PEL-HSEQ-5014 v6
- Design note: `docs/governance/library-cut1-retention-access-sor.md`
- Depends: WK-1 `#1690` LIVE, WJ-1 `#1694` LIVE

## 11) Honest remainder (not defects introduced here)

- **14 categories still have no executable retention.** They name two periods or a condition; no single integer represents them. This PR builds the mechanism and lists them; the decisions are a business input. Until then those documents are kept, never disposed.
- **`L-51` / `L-19` have no in-repo text.** The conveyor names them but the requirement wording lives in the external `library-world-class-ux-plan` canvas. This PR was built against the in-repo authority that *is* checked in (ADR-0023, F-7, R19/R26/R28) and the conveyor's own one-line scope, "one retention · one Access · QGP SoR". Worth confirming against the canvas before marking the L-numbers closed.
- **`controlled_documents.retention_period_years` still exists** and is still written by the control layer. CUT-1 stops it being an independent SoR for access; the retention column drop needs the control converge to remove the writers first (F-7 §2).
- **No frontend.** `Documents.tsx` does not consume `access_level` or `retention_until` today, so nothing regressed — but retention is not yet visible to a user outside the API and the disposal queue. Surfacing it belongs with the WJ-1 Front Sheet.
- **Legacy `documents.retention_*` are not backfilled.** A filed document's retention was decided at file time; deriving it now from today's category would be inventing an attestation.

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Dependencies PROD LIVE — WK-1 `#1690`, WJ-1 `#1694`, tip `c2f4e9a41` STG = PROD, healthz 200
- [ ] **Gate 2:** CI green on this SHA
- [x] **Gate 3:** One alembic head (`20261102_lib_cut1_sor` on WJ-0); no parallel revision; no `collaborative_*`; no DocumentDetail / WJ-1 editor mount touched
- [x] **Gate 4:** Anti-dupe gate clean (no new file home, no coverage twin, no free-text standards column); no test weakened — the two head pins advanced per WI-1 / WI-2 / WJ-0 precedent, and the pre-existing retention test passes unmodified
- [ ] **Gate 5:** DONE = tip LIVE on STG + PROD with healthz 200 and ACA image at tip SHA
