# Change Ledger (CL-PX-424-CAPA-CLOSE-NAIVE-UTC)

> **Start gate:** #1787 LIVE @ `2a0d0745d5f1`. `STACK_MAX=1`. Merge ≠ LIVE.
> David lock 2026-08-18: continue PX-424 (W0 UAT P0 — CAPA close HTTP 500).
> Entra flag stays false. A4 four lanes stay. Exceptions cap 200. No S4 / EXACT.

## 1) Summary
- **Feature / Change name:** PX-424 CAPA close via unified Actions does not 500
- **User goal:** Close CAPA-2026-0010 from the finding close button / PATCH `/actions/{id}?source_type=audit_finding` so the finding close-gate can lift.
- **In scope:** Naive-UTC writes onto CAPAAction datetime columns in `src/api/routes/actions.py`. AST guard + Postgres PATCH tests.
- **Out of scope:** timestamptz migration. PX-425/426/427/428. Entra. S4. Scheme EXACT. Dependabot.
- **Feature flag / kill switch:** None. Revert this PR. Dedicated `/capa/{id}/transition` already wrote naive UTC and stays the fallback.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| PX-424-01 | PATCH `/actions/{id}` CAPA terminal status | `completed_at = datetime.now(timezone.utc)` → asyncpg DataError → 500 | `_naive_utc_now()` naive UTC; 200; bridge can close the finding |
| PX-424-02 | PATCH/POST CAPA `due_date` with `Z` | aware fromisoformat → same 500 class | `_as_capa_naive` before write |
| PX-424-03 | Incident/RTA/complaint actions | timezone-aware columns | Unchanged — still `datetime.now(timezone.utc)` |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** No schema change. Existing naive rows stay valid.
- **Breaking changes:** None.
- **Migration plan:** None. timestamptz for `capa_actions` is a later PR.
- **Rollback strategy:** Revert merge; redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| CAPA/NC close loop | Finding close gated on un-closeable CAPA (open NC blocks EXACT auto-share) | Unified Actions close writes; residue CAPA-2026-0010 / FND-2026-0203 can be closed |
| Invented EXACT / S4 / Entra | Unchanged | Unchanged |
| Exceptions 200 / A4 four lanes | Unchanged | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: CAPA `completed_at` assignment in `isinstance(..., CAPAAction)` bodies uses `_naive_utc_now()`.
- [x] AC-02: CAPA create/PATCH `due_date` is naive before flush.
- [x] AC-03: Unit AST + helper tests. Postgres PATCH `status=completed` from IN_PROGRESS → 200; `due_date` with Z → 200.
- [ ] AC-04: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.
- [ ] AC-05: On prod, PATCH CAPA-2026-0010 completed succeeds; FND-2026-0203 close-gate lifts (operator cleanup after LIVE).

## 5) Testing Evidence (link to runs)
- [x] Unit (local): `tests/unit/test_actions_capa_naive_datetimes.py`
- [x] Integration (Postgres, skip on SQLite): `tests/integration/test_actions_capa_close_naive_datetime.py`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: PATCH audit_finding CAPA from in_progress → completed without 500 (Postgres).
- [x] CUJ-02: PATCH Zulu due_date on an open CAPA without 500 (Postgres).
- [ ] CUJ-03: Prod residue CAPA-2026-0010 close after this image is LIVE.

## 7) Observability & Ops
- No new metrics. Failed close previously appeared as generic 500.
- Rollback: revert. `/capa/{id}/transition` remains the naive writer.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after required CI green (`STACK_MAX=1`; admin-squash authorised).
2. Staging: PATCH a test CAPA completed; `/api/v1/health` SHA = tip.
3. Promote PROD; Production **Build and Deploy SUCCESS (not skipped)**; STG=PROD=MAIN SHA.
4. Close CAPA-2026-0010 then FND-2026-0203 on prod. Leave RSK-2026-0001 unless David says close.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** CAPA PATCH completed 500s; finding close-gate still stuck; incident action close regresses.
- **Rollback steps:** Revert merge; redeploy prior tip via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `fix/px-424-capa-close-naive-utc`
- Ledger: `scripts/governance/pr_body_px_424_capa_close_naive_utc.md`
- UAT: W0 Operator Proofs 2026-08-18 PX-424

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit tests (run locally before PR)
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
