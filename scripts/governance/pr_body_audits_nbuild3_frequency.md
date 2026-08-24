# Change Ledger (CL-AUDITS-NBUILD3-FREQUENCY)

> **Start gate:** #1776 LIVE — tip `b80c8c58796`. `STACK_MAX=1`. Merge ≠ LIVE.
> David said **continue** (hardened 20m conveyor). L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt, CRM-LIB is CRM work.
> N2, A4 four columns, Findings redesign, a new calendar SoR, alembic, and merging AssessmentRun are not this slice.

## 1) Summary
- **Feature / Change name:** N-BUILD-3 — ongoing skills via existing frequency + calendar
- **User goal:** After a skills/induction template is published, operators can open the existing training calendar. Create pages show the template's stored `frequency` (when present) and join to `/calendar?types=training`. No invented next-due date.
- **In scope:** `instrumentCalendarHref` for skills/induction → `/calendar?types=training`. Builder published secondary CTA + PublishDialog link. AssessmentCreate / InductionCreate cadence strip using list `frequency` already on `AuditTemplateResponse`.
- **Out of scope:** New recurrence engine. New calendar SoR. Alembic / `instrument_kind` column. A4 four columns. N2. Entra. EXACT. Merging AssessmentRun. Overloading `audit_type`. Moving Workforce Assessments under Audits. UVDB/PM twin. Dependabot.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| NB3-01 | Builder published CTA | Run CTA only | Skills/induction also get **Open training calendar** → `/calendar?types=training`. Audit unchanged |
| NB3-02 | PublishDialog | After-publish run link only | Skills/induction also link the training calendar |
| NB3-03 | AssessmentCreate | No cadence join | Selected skills template shows stored `frequency` (or unset honesty) + calendar link |
| NB3-04 | InductionCreate | No cadence join | Same for induction |

## 3) Compatibility & Data Safety
- No schema change. No alembic. `frequency` already on `AuditTemplateResponse` / model. Client list type now reads it.
- Calendar SoR unchanged (`CalendarView` already honours `?types=training`).
- **Rollback strategy:** Revert merge and redeploy `b80c8c58796`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Cadence vs new scheduler | Frequency stored; create pages did not join calendar | Join to existing `/calendar?types=training`; no next-due invention |
| Workforce assessments under Audits | Refused | Untouched — skills/induction still create via Workforce routes |
| Invented EXACT / Entra / A4 | Refused | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Skills/induction builder CTA includes Open training calendar → `/calendar?types=training`. Audit purpose has no calendar CTA.
- [x] AC-02: AssessmentCreate selected template shows stored frequency when present; otherwise unset honesty. Link href is `/calendar?types=training`.
- [x] AC-03: InductionCreate same join. No new calendar SoR. No recurrence engine.
- [x] AC-04: List `AuditTemplate.frequency` is read-only from existing serializer. No alembic. No `instrument_kind` column.
- [x] AC-05: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB/N2/A4/AssessmentRun merge.
- [ ] AC-06: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `auditInstrument.test.ts` — calendar href skills/induction only
- [x] Unit: `AssessmentCreate.test.tsx` — frequency + calendar href
- [x] Unit: `InductionCreate.test.tsx` — frequency + calendar href
- [ ] Hosted CI — pending

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Skills create with `frequency: quarterly` shows cadence strip and `/calendar?types=training` (unit).
- [x] CUJ-02: Audit instrument calendar href is null (unit).
- [x] CUJ-03: Induction create joins the same calendar (unit).

## 7) Observability & Ops
- FE join only. No new metrics.

## 8) Release Plan
1. Branch from LIVE tip `b80c8c58796`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** New calendar SoR added; next-due invented; alembic added; audit purpose routed to training calendar; AssessmentRun merged.
- **Rollback steps:** Revert merge; redeploy `b80c8c58796`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1776** @ `b80c8c58796`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1776 LIVE; L11–L16 held; continue given
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
