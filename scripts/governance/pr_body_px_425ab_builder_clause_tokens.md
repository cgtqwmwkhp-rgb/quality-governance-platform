# Change Ledger (CL-PX-425AB-BUILDER-CLAUSE-TOKENS)

> **Start gate:** #1791 LIVE @ `cf83b823300f`. `STACK_MAX=1`. Merge ≠ LIVE.
> David lock 2026-08-19: continue T5 PX-425a/b (W0 UAT LIVE-01 — builder clause
> tokens reach findings). T2 PX-425c matcher is already LIVE and unchanged here.
> Out of scope: T6 PX-427 cert POST. Entra flag stays false. Exceptions cap 200.

## 1) Summary
- **Feature / Change name:** PX-425a/b persist builder clause tokens as strings on findings
- **User goal:** Complete a 9001-templated run and have the resulting findings carry a clause token, so the live standards matrix can join them to a cell. LIVE-01 found 0 of 37 question-generated findings carrying one, which is why cell cover could not move.
- **In scope:** Widen `clause_ids` on the audit question/finding write **and** read schemas from `List[int]` to `List[int | str]`. Make the builder ISO Clause control write `clause_ids` (string tokens) as well as `regulatory_reference`. Preserve pre-existing integer catalogue ids through a save. Cap `regulatory_reference` on update at the column width. Unit + vitest cover.
- **Out of scope:** PX-427 `POST /certificates`. Changing `token_matches_clause` (T2, LIVE). Backfilling the 37 existing findings. Copying clause tokens onto auto-escalated risks. Inventing integer catalogue ids or a framework prefix. Schema migration. `control_ids` typing.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| PX-425A-01 | Builder ISO Clause box → API | Sent on neither `regulatory_reference` nor `clause_ids`; the field was local-only and never persisted | `buildQuestionPayload` sends both; explicit `null` when cleared |
| PX-425A-02 | Builder read-back | `isoClause` read from `regulatory_reference` only, so a question mapped by tokens alone read blank and the next save wiped it | Falls back to the stored token strings; integer catalogue ids ride through in `clauseCatalogIds` |
| PX-425A-03 | ISO Clause input | No length cap; >200 chars would 422 the whole template save | `maxLength={200}` matches the `String(200)` column |
| PX-425B-01 | `AuditQuestionCreate/Update.clause_ids` | `List[int]` — `"9001-8.5.1"` is a 422, `"7.2"` uncoercible | `List[int \| str]`; tokens kept verbatim as strings, ints still ints |
| PX-425B-02 | `AuditQuestionResponse.clause_ids` | `List[int]` — a stored token would 500 `GET /templates/{id}` | `List[int \| str]` |
| PX-425B-03 | `AuditFindingCreate/Update.clause_ids` | `List[int]` | `List[int \| str]` (parity with `AuditFindingResponse`, already untyped `list`) |
| PX-425B-04 | `AuditQuestionUpdate.regulatory_reference` | No `max_length` while the column is `String(200)` | `max_length=200`, mirroring Create |
| PX-425B-05 | Auto-create finding | Already copied `question.clause_ids_json` → `finding.clause_ids_json_legacy`; the source was always empty | Unchanged code, now fed real tokens; covered by test |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Widening only. Every payload that validated before still validates and still yields the same Python values (`[1,2,3]` stays `[1,2,3]`, ints are not stringified). `extra="forbid"` is untouched on all four write schemas.
- **Breaking changes:** None. The only tightening is `AuditQuestionUpdate.regulatory_reference` gaining the `max_length=200` that Create already had and that the column already enforced; a >200-char value was a 500 before and is a 422 now.
- **Migration plan:** None. `audit_questions.clause_ids_json` and `audit_findings.clause_ids_json_legacy` are existing `JSON` columns that already hold strings on the import path.
- **Backfill:** None. The 37 existing findings stay unmapped; re-authoring the template and re-running is the honest route, and back-dating tokens onto a finished audit would invent coverage.
- **Rollback strategy:** Revert merge; redeploy prior tip. Tokens already written stay in the JSON column and are simply not readable through the narrowed schema until the revert is itself reverted.
- **Contract baseline:** `openapi-baseline.json` and `docs/contracts/openapi.json` patched at exactly the six affected properties rather than regenerated, because the committed artefacts have pre-existing drift against `app.openapi()` (unrelated paths and ~20 schemas) and a full regeneration would sweep that drift into this PR. `test_openapi_baseline_matches_contracts_artifact` still passes (the two files remain identical) and `check_openapi_compatibility.py` reports no breaking change.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Finding → matrix cell join | 0 of 37 question-generated findings carried a clause token; the graph had nothing to join | A 9001-templated run writes `9001-8.5.1`-shaped tokens onto its findings |
| Coverage honesty | Clearing the ISO Clause box left nothing to clear (it never persisted) | Clearing it writes `null`, so a deleted claim stops painting |
| Invented catalogue ids | n/a | None invented; integer ids are preserved, never synthesised from clause text |
| Invented framework framing | n/a | None; a bare `8.5.1` is stored bare. No `9001-` prefix is guessed from a template that never names a standard |
| Invented EXACT / S4 / Entra | Unchanged | Unchanged |
| Exceptions 200 / A4 four lanes | Unchanged | Unchanged |
| extra=forbid honesty | Unknown fields 422 | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `AuditQuestionCreate` accepts string clause tokens (`"9001-8.5.1"`, `"7.2"`, `"8"`) and keeps them as strings; integer catalogue ids still validate as ints; unknown fields still 422 under `extra="forbid"`.
- [x] AC-02: Auto-create copies `question.clause_ids_json` onto `finding.clause_ids_json_legacy`, and the copied token satisfies the LIVE PX-425c matcher for cells `8` and `8.5` (unit asserts both). An unmapped question still yields `clause_ids = None`.
- [x] AC-03: The builder ISO Clause control writes `clause_ids` string tokens **and** `regulatory_reference`; an empty box writes explicit nulls; pre-existing integer catalogue ids survive the save.
- [x] AC-04: A stored token round-trips — `AuditQuestionResponse` validates `["9001-8.5.1"]` instead of 500ing, and `mapApiToTemplate` reads it back into the box.
- [x] AC-05: Contract artefacts describe the shipped schema; `check_openapi_compatibility.py` PASSED, no breaking change.
- [ ] AC-06: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.
- [ ] AC-07: After LIVE, complete a 9001-templated mock run and snapshot the 9001 matrix cells **before** attributing cell-cover movement to T5.

## 5) Testing Evidence (link to runs)
- [x] Unit (local): `tests/unit/test_audit_clause_tokens_px_425ab.py` — 15 passed.
- [x] Unit (local, regression): full `tests/unit` — 7046 passed, 11 pre-existing skips, 0 failed.
- [x] Contract (local): `tests/contract` — 441 passed, 68 skipped, 59 xfailed, 0 failed.
- [x] Frontend (local): `frontend/src/pages/audit-builder/templateHelpers.test.ts` — 25 passed; builder-adjacent suites 93 passed; `tsc --noEmit` clean; `eslint --max-warnings 0` clean on touched files.
- [x] Format (local): `isort` + `black` + `flake8` on touched Python.
- [ ] Hosted CI — pending PR checks.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Author sets ISO Clause `9001-8.5.1` on a question → payload carries `clause_ids: ["9001-8.5.1"]` and `regulatory_reference` (vitest).
- [x] CUJ-02: Failing answer on that question auto-creates a finding carrying `["9001-8.5.1"]`, which `token_matches_clause` joins to 9001 cells `8` and `8.5` (unit).
- [x] CUJ-03: Author clears the box → `clause_ids: null` and `regulatory_reference: null`, so the cell stops being painted from a deleted claim (vitest).
- [x] CUJ-04: A question mapped by tokens with no `regulatory_reference` reads back into the box and re-saves without losing its tokens or its integer catalogue ids (vitest).
- [ ] CUJ-05: LIVE-01 mock 9001 audit → matrix cell cover, on prod after this image is LIVE.

## 7) Observability & Ops
- No new signals. A question whose ISO Clause text is prose rather than a clause token is stored verbatim and paints nothing — the failure direction is under-claiming cover, never over-claiming it.
- TrapGuard and `requires_framed_tokens` still own cross-family and un-carried-framework rejection; this PR changes neither.
- Rollback: revert. Findings created while this was LIVE keep their tokens in the JSON column.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after required CI green (`STACK_MAX=1`).
2. Staging: save a question with ISO Clause `9001-8.5.1`, reload the builder and confirm the box round-trips; `/api/v1/health` SHA = tip.
3. Promote PROD; Production **Build and Deploy SUCCESS (not skipped)**; STG=PROD=MAIN SHA.
4. After LIVE, run the LIVE-01 mock 9001 audit and snapshot matrix cells before claiming cover movement. Supervisor then takes T6 PX-427; do not mix it into T5.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** `GET /templates/{id}` 500s on a token-mapped question; template save 422/500s; clause tokens written as integers; a cell paints from a cleared ISO Clause box; unknown fields accepted on question or finding write.
- **Rollback steps:** Revert merge; redeploy prior tip via governed Staging → Production; re-verify ACA image SHA.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `fix/px-425ab-builder-clause-tokens`
- Ledger: `scripts/governance/pr_body_px_425ab_builder_clause_tokens.md`
- Predecessor: PX-425c framed sub-clause roll-up (`scripts/governance/pr_body_px_425c_framed_subclause_rollup.md`) — matcher, LIVE, unchanged
- UAT: W0 Operator Proofs 2026-08-19 LIVE-01

# Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit + vitest tests (run locally before PR)
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** LIVE SHA match; T6 not started until T5 is LIVE
