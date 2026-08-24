# Change Ledger (CL-PX-426-CAPA-GET-OR-CREATE)

> **Start gate:** #1789 LIVE @ `be076fd1070a`. `STACK_MAX=1`. Merge ≠ LIVE.
> David lock 2026-08-18: continue T3 PX-426 (W0 UAT P2 — idempotent CAPA create + honest ribbon).
> Entra flag stays false. A4 four lanes stay. Exceptions cap 200. No S4 / EXACT.
> Out of scope: PX-425a/b, PX-427, PX-428, unique-index drop, page_size raise, timestamptz.

## 1) Summary
- **Feature / Change name:** PX-426 idempotent CAPA create + honest findings-loop load
- **User goal:** Create & assign CAPA on a finding that already has a CAPA (auto-created or off page 1) returns the existing row with assignee. The ribbon never labels that CAPA as missing.
- **In scope:** Get-or-create on `uq_capa_actions_tenant_audit_finding_source`. Findings loop resolves missing rows by `source_id`.
- **Out of scope:** PX-425a/b builder tokens. PX-427 cert POST. PX-428 owner_email on ActionCreate. Dropping the unique index. Raising the 100-row page.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| PX-426-01 | POST `/actions/` same audit finding | Unique index → IntegrityError → 409 "reference number already exists" | Existing CAPA returned (201) with assignee |
| PX-426-02 | Findings loop `list(1, 100)` | Off-page CAPA looks missing; ribbon says Create & assign | Resolve by `source_id`; ribbon shows Assign + email |
| PX-426-03 | Unique index | Stays | Unchanged. page_size stays 100 (cap 500). |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** No schema change. First POST still inserts. Second POST reads the existing row.
- **Breaking changes:** None. Reference-number collisions that are not a finding unique hit still 409.
- **Migration plan:** None.
- **Rollback strategy:** Revert merge; redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Actions = SoR for finding CAPA | Shortcut 409 / ribbon lie | Get-or-create + source_id resolve |
| Invented EXACT / S4 / Entra | Unchanged | Unchanged |
| Exceptions 200 / A4 four lanes | Unchanged | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Second POST for the same `audit_finding` `source_id` returns the existing CAPA (id + reference + assignee). Unique index stays.
- [x] AC-02: Findings loop loads an off-page CAPA via `source_id` and does not show Create & assign.
- [x] AC-03: Unit + frontend tests. Postgres integration for the unique-index path.
- [ ] AC-04: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.
- [ ] AC-05: LIVE-02 shortcut retest: Create & assign on a finding whose CAPA is off page 1. Assignee sticks.

## 5) Testing Evidence (link to runs)
- [x] Unit (local): `tests/unit/test_actions_px_426_get_or_create.py` — 2 passed. `test_actions_audit_finding.py` still 2 passed.
- [x] Frontend (local): `Audits.findings-closure.test.tsx` + ribbon — 10 passed.
- [ ] Integration (Postgres): `tests/integration/test_actions_capa_get_or_create.py` — hosted CI.
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Unique-index IntegrityError on audit_finding create returns existing CAPA (unit).
- [x] CUJ-02: Off-page CAPA resolved by source_id; ribbon is Assign, not Create (frontend).
- [ ] CUJ-03: LIVE-02 shortcut after this image is LIVE.

## 7) Observability & Ops
- Get-or-create logs `PX-426 get-or-create: returning existing CAPA`.
- Rollback: revert. Prior 409 on the unique index returns.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after required CI green (`STACK_MAX=1`; admin-squash authorised).
2. Staging: second POST same finding returns existing id; `/api/v1/health` SHA = tip.
3. Promote PROD; Production **Build and Deploy SUCCESS (not skipped)**; STG=PROD=MAIN SHA.
4. Do not start PX-425a/b, PX-427, or PX-428 until David says continue.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Second POST creates a second CAPA; unique index dropped; ribbon still lies; incident create 409 regresses.
- **Rollback steps:** Revert merge; redeploy prior tip via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `fix/px-426-capa-get-or-create`
- Ledger: `scripts/governance/pr_body_px_426_capa_get_or_create.md`
- UAT: W0 Operator Proofs 2026-08-18 PX-426

# Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit tests (run locally before PR)
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** LIVE SHA match; T4 not started
