# Change Ledger (CL-AUDITS-N2-FOLLOWUP)

> **Start gate:** #1777 LIVE — tip `fd173bb7f51`. `STACK_MAX=1`. Merge ≠ LIVE.
> David unlocked **N2 only**. Entra flag stays false. A4 stays 3 columns. Dependabot is not this belt. CRM-LIB is CRM work.
> Fourth view and CAPA product rewrite are not this slice.

## 1) Summary
- **Feature / Change name:** N2 — Findings follow-up honesty for the active chip
- **User goal:** The Findings tab is the follow-up register for the selected programme. Empty and truncation copy must not pretend the tenant (or another programme) is empty.
- **In scope:** Empty Findings names the active programme chip. Tenant-wide truncation uses `Showing {loaded} of {total} findings` (same pattern as N1 runs). Programme-scoped empty does not show tenant findings from other chips.
- **Out of scope:** A4 four columns. Fourth view. CAPA rewrite. Entra flag. Dependabot. New calendar SoR. EXACT.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| N2-01 | Findings empty + programme chip | "No findings recorded yet" | "No {programme} findings" + honesty that other programmes may still have follow-up |
| N2-02 | Findings truncation (tenant view) | Long KPI-explainer sentence | `Showing {loaded} of {total} findings` |
| N2-03 | Findings truncation (chip/clause subset) | Filter honesty | Unchanged |

## 3) Compatibility & Data Safety
- No schema change. No alembic. Client copy + existing `findingsTotal` only.
- **Rollback strategy:** Revert merge and redeploy `fd173bb7f51`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Follow-up vs chip | Empty Findings could look tenant-empty when a 0-count chip is selected | Empty names the chip |
| Truncation honesty | Findings banner explained KPI internals | Same N1 loaded-of-total pattern |
| A4 / Entra / Dependabot | Refused | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Planet Mark chip at 0 → Findings empty names Planet Mark; Internal findings are not listed.
- [x] AC-02: Tenant Findings truncation banner is `Showing {loaded} of {total} findings`.
- [x] AC-03: Subset (chip/clause) truncation copy unchanged. A4 stays 3 columns. No Entra/Dependabot/CAPA rewrite/fourth view.
- [ ] AC-04: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `Audits.test.tsx` — programme-empty Findings; Showing N of M
- [x] Unit: `auditsFindingsModel.test.ts` — empty names program; truncation format
- [ ] Hosted CI — pending

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Internal findings exist; Planet Mark chip 0; Findings empty names Planet Mark (unit).
- [x] CUJ-02: Truncated tenant findings page shows Showing loaded of total (unit).

## 7) Observability & Ops
- FE copy only. No new metrics.

## 8) Release Plan
1. Branch from LIVE tip `fd173bb7f51`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Empty Findings still says tenant-empty on a 0-count chip; truncation omits loaded vs total; A4 becomes 4 columns.
- **Rollback steps:** Revert merge; redeploy `fd173bb7f51`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1777** @ `fd173bb7f51`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1777 LIVE; N2 unlocked; Entra/A4/Dependabot held
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
