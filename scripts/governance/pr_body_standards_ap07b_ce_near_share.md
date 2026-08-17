# Change Ledger (CL-STANDARDS-AP07B-CE-NEAR-SHARE)

> **Start gate:** #1783 LIVE — tip `111ac4a54f26`. `STACK_MAX=1`. Merge ≠ LIVE.
> AP-07 leftover: CE↔CE+ NEAR proposed-share. Not scheme EXACT.

## 1) Summary
- **Feature / Change name:** AP-07b CE↔CE+ NEAR proposed-share
- **User goal:** On a Cyber Essentials NEAR cell (e.g. firewalls), propose the same evidence onto CE+ with the required addition named. Coverage does not count until an operator confirms.
- **In scope:** `NearShareService` second family `{ce, cep}`; existing ISO family unchanged; CHAS/SSIP/PM/UVDB still refused.
- **Out of scope:** Invented CHAS/SSIP/PM/UVDB EXACT. Entra flag. Exceptions 200. A4 four columns. Licensed marks. S4 trees.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| AP07B-01 | NearShare ISO | ISO NEAR peers offered | Unchanged |
| AP07B-02 | NearShare CE | `no_iso_near_peers` on CE firewalls | CE↔CE+ NEAR candidates with `addition_text`; PROPOSED only |
| AP07B-03 | ExactShare | EXACT-only | Unchanged |
| AP07B-04 | CHAS source | Refused | Still refused |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Same API. Additional candidates only for CE/CE+ NEAR cells.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy:** Revert merge and redeploy `111ac4a54f26`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| CE NEAR treated as EXACT | CE firewalls had no proposed-share | Same NEAR path as ISO: PROPOSED + auto_applied; never CONFIRMED on apply |
| Scheme EXACT | CHAS/SSIP/PM/UVDB ExactShare absent | Unchanged |
| Cross-family mix | ISO filter blocked CE | Families stay separate: ISO↔ISO, CE↔CE+; no ISO↔CE |

## 4) Acceptance Criteria (AC)
- [x] AC-01: CE firewalls NEAR plan offers CEP and surfaces `addition_text`.
- [x] AC-02: ISO 4.1 NEAR plan still offers ISO peers only.
- [x] AC-03: CHAS source still `no_iso_near_peers`.
- [x] AC-04: Apply still writes PROPOSED + auto_applied; never CONFIRMED in apply().
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit (local): `test_standards_near_share_service`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator on CE firewalls sees CE+ NEAR proposed-share naming independent technical verification.
- [x] CUJ-02: ExactShare on ISO 4.1 still `no_exact_peers`.

## 7) Observability & Ops
- Conflict prefix remains `NEAR_SHARE_*`.
- Exceptions inbox still pages at 200.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after required CI green (`STACK_MAX=1`; admin-squash authorised).
2. Staging: CE firewalls workspace → near-share banner → propose. Confirm CHAS still has no EXACT/NEAR share.
3. Promote PROD; verify `/api/v1/health` version = main tip; Production **Build and Deploy SUCCESS (not skipped)**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** CE apply confirms coverage, or CHAS/SSIP/PM/UVDB start offering EXACT/NEAR share.
- **Rollback steps:** Revert merge commit; redeploy prior tip `111ac4a54f26` via governed Staging → Production path.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `feat/ap07b-ce-near-share`
- Ledger: `scripts/governance/pr_body_standards_ap07b_ce_near_share.md`
- Parent LIVE: #1783 @ `111ac4a54f26`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
