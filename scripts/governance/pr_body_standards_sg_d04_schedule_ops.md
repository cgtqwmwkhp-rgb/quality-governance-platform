# Change Ledger (CL-STANDARDS-SG-D04-SCHEDULE-OPS)

> **Start gate:** SG-D-03b (#1747) LIVE — tip `74de898f4268`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Standards SG-D-04 — Evidence workspace Schedule ops strip.
- **User goal:** See the Compliance Schedule owner, days until next due, and the existing 60/30/7 notify band on the cell workspace without leaving `/compliance`.
- **In scope:** Read `GET /api/v1/compliance-schedule/requirements`; pick soonest obligation that mentions the cell clause; display owner / days / notify band; honest empty and load-error copy. Keep D2 deep-link.
- **Out of scope:** New owner table; cell-aggregate fork; new notifier / Celery task; Alembic; D5 export; Entra flag; TrapGuard/ingest; inventing EXACT for CHAS/SSIP/PM/UVDB; changing sidebar default view.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-D-04-01 | Evidence workspace | Schedule deep-link only | + owner, days-to-due, notify band from Schedule SoR |
| SG-D-04-02 | No matching obligation | Operator had to open Schedule to learn that | Honest empty copy; still a Schedule link |
| SG-D-04-03 | Notify-before-surveillance | Reminder job already exists on Schedule | Display the same 60/30/7/overdue band; no second mailer |
| SG-D-04-04 | Index gzip budget | 205 kB | 206 kB — shell i18n keys only; strip stays on lazy ComplianceEvidence chunk |

## 3) Compatibility & Data Safety
- Frontend read of an existing GET. No schema, no writer.
- **Rollback strategy:** Revert merge and redeploy prior tip `74de898f4268`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Obligation SoR | Schedule register + D2 deep-link | Unchanged SoR; workspace is a read |
| Fake SLA / owner | N/A | Blank owner → Unassigned; no clause match → empty, not a fabricated row |
| Cover / EXACT / catalogues | Unchanged | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Soonest Schedule row whose text mentions the cell clause drives owner + days + notify band.
- [x] AC-02: Unrelated register rows (e.g. FRA) never paint the cell.
- [x] AC-03: Blank `owner_name` displays Unassigned; load failure does not crash the workspace.
- [x] AC-04: D2 deep-link still opens `/compliance-schedule?clause=&framework=`.
- [x] AC-05: No Alembic; no cell-aggregate fork; TrapGuard/ingest/`covers_framework`/Entra/D5 untouched.
- [x] AC-05b: Index gzip ceiling 205→206 kB ledgered; UI not on the App shell.
- [ ] AC-06: Hosted CI green; STG+PROD SUCCESS; STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] FE unit: `frontend/src/pages/compliance/__tests__/scheduleOpsPick.test.ts`
- [x] FE: `frontend/src/pages/compliance/__tests__/ScheduleOpsStrip.test.tsx`
- [x] FE: existing D2 deep-link test still green
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator opens a 9001 / 6.1.3 cell whose Schedule row mentions 6.1.3 → strip shows that row's owner, days, notify band.
- [x] CUJ-02: Operator opens a cell with no matching obligation → empty honesty copy; Open Compliance Schedule still works.

## 7) Observability & Ops
- No new telemetry. Load failures stay on-screen; Schedule remains the place to edit owner / due date.
- Notify band is display of the existing reminder windows. It does not send mail.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `74de898f4268` (`STACK_MAX=1`).
2. Focused Vitest green; open PR with this ledger.
3. Merge after CI green; STG verify; PROD verify; only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Strip invents an owner or obligation; paints FRA onto an ISO cell; new notifier lands; cell-aggregate grows a schedule fork.
- **Rollback steps:** Revert merge; redeploy prior tip `74de898f4268` via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_sg_d04_schedule_ops.md`
- Parent LIVE gate: **PR #1747** (SG-D-03b) @ `74de898f4268`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1747 LIVE confirmed
- [x] **Gate 1:** Focused FE tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
