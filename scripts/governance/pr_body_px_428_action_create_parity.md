# Change Ledger (CL-PX-428-ACTION-CREATE-PARITY)

> **Start gate:** #1790 LIVE @ `9d0bb9818dd1`. `STACK_MAX=1`. Merge ≠ LIVE.
> David lock 2026-08-19: continue T4 PX-428 (W0 UAT P2 — owner_email + clause_reference on ActionCreate).
> Supervisor continues through T6 after each tip is LIVE. Entra flag stays false.
> Out of scope: PX-425a/b builder tokens. PX-427 cert POST. ActionUpdate owner_email. timestamptz.

## 1) Summary
- **Feature / Change name:** PX-428 accept owner_email + clause_reference on ActionCreate
- **User goal:** Echoing a GET ActionResponse into POST /actions/ returns 201, persists the owner, and stores the clause on CAPA rows. extra=forbid stays.
- **In scope:** ActionCreate fields. Three-way owner agreement. Persist clause_reference on CAPA sources (max 50). Frontend ActionCreate type. Close the clause_reference write-contract gap.
- **Out of scope:** PX-425a/b. PX-427. Adding owner_email to ActionUpdate. Dropping extra=forbid. Schema migration.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| PX-428-01 | POST `/actions/` with `owner_email` | 422 extra inputs not permitted | Resolves through `_resolve_requested_owner`; 201 with owner |
| PX-428-02 | POST `/actions/` with `clause_reference` | 422 | Persisted on CAPA sources; 400 on incident/rta/complaint/investigation |
| PX-428-03 | Three-way owner | owner_id vs assigned_to_email only | owner_id + assigned_to_email + owner_email must identify the same user |
| PX-428-04 | extra=forbid | Stays | Unknown fields still 422 |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive optional fields. Existing owner_id / assigned_to_email clients unchanged.
- **Breaking changes:** None.
- **Migration plan:** None. `capa_actions.clause_reference` already exists (String 50).
- **Rollback strategy:** Revert merge; redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Actions write/read parity | GET owner_email / clause_reference could not be posted | Echoed GET fields accepted and persisted where the model owns them |
| Invented EXACT / S4 / Entra | Unchanged | Unchanged |
| extra=forbid honesty | Unknown fields 422 | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: POST with owner_email and/or clause_reference is not 422. extra=forbid stays for unknown fields.
- [x] AC-02: Three-way owner agreement: contradictory spellings 400; matching spellings resolve to one user.
- [x] AC-03: clause_reference persisted on CAPA create (max 50). Rejected on non-CAPA sources.
- [x] AC-04: Unit tests. Integration tests for owner_email on incident create. Contract gap for ActionResponse.clause_reference closed.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit (local): `tests/unit/test_actions_px_428_create_parity.py` — 9 passed. Related action units 13 passed.
- [ ] Integration: `TestActionOwnerPersistence` owner_email cases
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: ActionCreate accepts owner_email + clause_reference; unknown field still 422 (unit).
- [x] CUJ-02: Three-way owner agree / disagree (unit).
- [x] CUJ-03: audit_finding create persists clause_reference and assigned_to_id from owner_email (unit).
- [ ] CUJ-04: LIVE-02 create path after this image is LIVE.

## 7) Observability & Ops
- Contradictory owners still raise BadRequestError with the disagreeing spellings named.
- Rollback: revert. Prior 422 on owner_email / clause_reference returns.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after required CI green (`STACK_MAX=1`; admin-squash authorised).
2. Staging: POST with owner_email 201; `/api/v1/health` SHA = tip.
3. Promote PROD; Production **Build and Deploy SUCCESS (not skipped)**; STG=PROD=MAIN SHA.
4. After LIVE, supervisor takes T5 PX-425a/b. Do not mix cert POST into T4.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Unknown fields accepted; contradictory owners persist; clause_reference dropped on CAPA create; incident create 422 regresses on valid owner_id.
- **Rollback steps:** Revert merge; redeploy prior tip via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `fix/px-428-action-create-parity`
- Ledger: `scripts/governance/pr_body_px_428_action_create_parity.md`
- UAT: W0 Operator Proofs 2026-08-18 PX-428

# Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit tests (run locally before PR)
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** LIVE SHA match; T5 not started until T4 is LIVE
