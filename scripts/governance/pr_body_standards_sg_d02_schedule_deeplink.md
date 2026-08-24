# Change Ledger (CL-STANDARDS-SG-D02-SCHEDULE-DEEPLINK)

> **Start gate:** Int-W10 (#1744) LIVE — tip `437ff409046f`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Standards SG-D-02 — Compliance Schedule deep-links in programme.
- **User goal:** From an Evidence Workspace cell, open the Compliance Schedule SoR with clause and framework context. Schedule stays the obligation register — not a second Standards list.
- **In scope:** Workspace “Open Compliance Schedule” deep-link; Schedule reads `clause` + `framework` query params; client-filter when an obligation mentions the clause; honesty banner when none do (full register shown).
- **Out of scope:** Cert countdown (D3); SLA/owner columns (D4); export appendix (D5); cell-aggregate schedule rows; Entra flag; TrapGuard/ingest; Alembic; inventing EXACT for CHAS/SSIP/PM/UVDB.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-D-02-01 | Evidence Workspace | Audits/Actions/Risks/Certs/Evidence deep-links only | + Open Compliance Schedule with `?clause=&framework=` |
| SG-D-02-02 | Compliance Schedule URL | `view` only | Reads programme `clause` + `framework`; banner + optional client filter |
| SG-D-02-03 | Empty filter | N/A | Zero matches → full register + honesty copy (never a fake empty list) |

## 3) Compatibility & Data Safety
- No schema / migration / API change. Query params are additive.
- Filter is client-side on the existing register payload (`page_size: 100`).
- **Rollback strategy:** Revert merge and redeploy prior tip `437ff409046f`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Second Standards register | Workspace could not reach Schedule SoR from a cell | Deep-link only; Schedule remains SoR |
| Empty-state honesty | N/A | No obligation citing the clause does not claim zero obligations |
| Cover / EXACT / catalogues | Unchanged | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Workspace cell exposes a Schedule deep-link to `/compliance-schedule?clause={n}&framework={id}`.
- [x] AC-02: Landing with those params shows a programme-context banner on the obligations view.
- [x] AC-03: Obligations whose title/basis/description/reference mention the clause are listed; others are hidden when at least one matches.
- [x] AC-04: Zero matches still shows the full register and says so. Never an invented empty list.
- [x] AC-05: “Show all” clears clause/framework params and restores the full register.
- [x] AC-06: No Alembic; TrapGuard/ingest/`covers_framework`/Entra flag untouched. D3–D5 out of scope.
- [ ] AC-07: Hosted CI green; STG+PROD SUCCESS; STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `frontend/src/pages/compliance/__tests__/scheduleProgrammeContext.test.ts`
- [x] FE: `frontend/src/pages/compliance/__tests__/EvidenceWorkspaceHost.scheduleDeepLink.test.tsx`
- [x] FE: `frontend/src/pages/__tests__/ComplianceSchedule.programmeDeepLink.test.tsx`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: ISO 9001 · 6.1.3 workspace → Schedule with context; matching legal-register row shown.
- [x] CUJ-02: Clause with no mentioning obligation still shows the live register.

## 7) Observability & Ops
- No new telemetry. Query params are the only context channel.
- Health SHA matching the merge commit is **not** sufficient if staging/prod deploy fails.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `437ff409046f` (`STACK_MAX=1`).
2. Implement + focused unit green; open PR with this ledger.
3. Merge after CI green; STG verify; PROD verify; only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Workspace invents a second obligation list; Schedule empties when no clause match; D3–D5 / Entra / TrapGuard accidentally land.
- **Rollback steps:** Revert merge; redeploy prior tip `437ff409046f` via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_sg_d02_schedule_deeplink.md`
- Parent LIVE gate: **PR #1744** (Int-W10) @ `437ff409046f`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1744 LIVE confirmed
- [x] **Gate 1:** Focused unit tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
