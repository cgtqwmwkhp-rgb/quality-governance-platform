# Change Ledger (CL-PX-425C-FRAMED-SUBCLAUSE-ROLLUP)

> **Start gate:** #1788 LIVE @ `16b45b6c82b4`. `STACK_MAX=1`. Merge ≠ LIVE.
> David lock 2026-08-18: continue T2 PX-425c (W0 UAT P1-slice — framed sub-clause tokens).
> Entra flag stays false. A4 four lanes stay. Exceptions cap 200. No S4 / EXACT.
> Out of scope: PX-425a/b builder tokens, PX-426/427/428, backfill.

## 1) Summary
- **Feature / Change name:** PX-425c framed sub-clause tokens roll up to parent cells
- **User goal:** A finding stored as `9001-8.5.1` covers the ISO 9001 matrix cell `8` (and `8.5`), so LIVE-01 cell cover can move once builder tokens exist. This PR writes nothing.
- **In scope:** Compose framework-strip with child→parent inside `token_matches_clause`. Unit snapshot of top-level 9001 cells.
- **Out of scope:** Builder `clause_ids` write path (PX-425a/b). Backfill. Matcher changes that let a parent paint a child. Invented scheme EXACT.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| PX-425C-01 | `token_matches_clause("9001-8.5.1", cell 8)` | false (strip and startswith never compose) | true |
| PX-425C-02 | `token_matches_clause("9001-8", cell 8.5)` | false | false (child→parent only) |
| PX-425C-03 | `token_matches_clause("14001-8.5.1", 9001 cell 8)` | false | false (no new cross-family child→parent) |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Read-model only. No schema, no writes, no backfill.
- **Breaking changes:** None. Bare `8.5.1`→cell `8` and exact framed `9001-7.5`→`7.5` stay.
- **Migration plan:** None. Existing framed findings start joining parent cells on next matrix read.
- **Rollback strategy:** Revert merge; redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Matrix cell cover from framed NC tokens | `9001-8.5.1` missed cell `8`; LIVE-01 looked uncovered even when a clause token existed | Child tokens roll up to the parent cell in the same family |
| Borrowed / cross-family paint | Exact-suffix `14001-8` vs 9001 cell `8` still TrapGuard's job | Child→parent does not add `14001-8.5.1`→9001 cell `8` |
| Invented EXACT / S4 / Entra | Unchanged | Unchanged |
| Exceptions 200 / A4 four lanes | Unchanged | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `token_matches_clause(9001-8.5.1, cell 8)` is true; `iso9001:8.5.1` likewise.
- [x] AC-02: `token_matches_clause(9001-8, cell 8.5)` is false.
- [x] AC-03: Top-level 9001 snapshot `[4..10]` for token `9001-8.5.1` hits only cell `8`.
- [x] AC-04: `14001-8.5.1` does not roll up onto 9001 cell `8`. Exact-suffix `14001-8` vs cell `8` unchanged.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.
- [ ] AC-06: After LIVE, snapshot 9001 matrix cells on prod before attributing cover movement to T5/T6.

## 5) Testing Evidence (link to runs)
- [x] Unit (local): `tests/unit/test_standards_cell_aggregate_service.py` — 42 passed, including PX-425c cases. TrapGuard 46 + exact-share 8 passed.
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Framed operation token `9001-8.5.1` matches 9001 cell `8` and `8.5`, not cell `7`.
- [x] CUJ-02: Parent framed token `9001-8` does not paint cell `8.5`.
- [ ] CUJ-03: LIVE observational 9001 % snapshot after this image is LIVE. Do not treat that delta as LIVE-01 (builder still sends no tokens — PX-425a/b).

## 7) Observability & Ops
- No new metrics. Cover changes appear on `/compliance/cell-aggregate/matrix` on the next read.
- Rollback: revert. Prior matcher behaviour returns immediately (no data rewrite).

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after required CI green (`STACK_MAX=1`; admin-squash authorised).
2. Staging: `/api/v1/health` SHA = tip; 9001 cell snapshot if a framed finding exists.
3. Promote PROD; Production **Build and Deploy SUCCESS (not skipped)**; STG=PROD=MAIN SHA.
4. Do not start PX-425a/b until David says continue.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** A parent cell paints from a child of another family; or a parent token paints a child cell; or 9001 cover jumps without a same-family framed token.
- **Rollback steps:** Revert merge; redeploy prior tip via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `fix/px-425c-framed-subclause-rollup`
- Ledger: `scripts/governance/pr_body_px_425c_framed_subclause_rollup.md`
- UAT: W0 Operator Proofs 2026-08-18 PX-425c

# Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit tests (run locally before PR)
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** LIVE SHA match; T3 not started
