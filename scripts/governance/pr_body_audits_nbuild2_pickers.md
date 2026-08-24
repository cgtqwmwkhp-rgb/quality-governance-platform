# Change Ledger (CL-AUDITS-NBUILD2-PICKERS)

> **Start gate:** #1774 LIVE — tip `935604f61`. `STACK_MAX=1`. Merge ≠ LIVE.
> David said **continue** (hardened 20m conveyor). L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt, CRM-LIB is CRM work.
> N1 locate, N-BUILD-3, alembic, A4, and merging AssessmentRun are not this slice.

## 1) Summary
- **Feature / Change name:** N-BUILD-2 — honest pickers by purpose
- **User goal:** Create/schedule pickers offer only templates whose `instrument:*` tag matches the page purpose. Wrong-purpose `?templateId=` is not silently used.
- **In scope:** AssessmentCreate skills-only picker + empty author link. InductionCreate induction-only picker + empty author link. Audits schedule modal audit-only picker (untagged counts as audit). Honour matching `?templateId=`; refuse wrong-purpose seed.
- **Out of scope:** N1 locate (Comfort/Compact, chips, truncation). N-BUILD-3. Alembic / new tables / `instrument_kind` column. Entra. EXACT. A4 four-column board. Merging AssessmentRun. Overloading `audit_type`. Moving Workforce Assessments under Audits. UVDB/PM twin. Dependabot.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| NB2-01 | AssessmentCreate `/workforce/assessments/new` | All published templates | Skills instrument only. Empty → `/audit-templates/new?instrument=skills` |
| NB2-02 | InductionCreate `/workforce/training/new` | All published templates | Induction instrument only. Empty → `/audit-templates/new?instrument=induction` |
| NB2-03 | Audits schedule modal | All published operational templates | Audit instrument only; untagged included as audit. Skills/induction hidden |
| NB2-04 | `?templateId=` seed | Any published id selected | Matching purpose only. Wrong purpose left unselected with honesty copy |

## 3) Compatibility & Data Safety
- No schema change. No alembic. List payload already returns `tags` (`AuditTemplateResponse.tags` ← `tags_json`; client `AuditTemplate.tags`). Client-side `parseInstrument` filter only.
- `audit_type` unchanged. Instrument remains `tags_json` (`instrument:audit` / `instrument:skills` / `instrument:induction`).
- **Rollback strategy:** Revert merge and redeploy `935604f61`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Purpose vs audit_type | Identity tagged; pickers still mixed | Pickers filter by `parseInstrument`; `audit_type` not overloaded |
| Workforce assessments under Audits | Refused | Untouched — skills/induction still create via Workforce routes |
| Invented EXACT / Entra / A4 | Refused | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: AssessmentCreate picker shows only published `instrument:skills` templates. Empty state links to `/audit-templates/new?instrument=skills` labelled to author a skills assessment.
- [x] AC-02: InductionCreate picker shows only `instrument:induction`. Empty state links to `/audit-templates/new?instrument=induction`.
- [x] AC-03: Audits schedule modal shows only audit (untagged counts as audit). Skills/induction do not appear. No Comfort/Compact/chips/truncation.
- [x] AC-04: Matching `?templateId=` still seeds. Wrong-purpose seed is not selected; honesty copy / empty state shown instead of running the wrong instrument.
- [x] AC-05: Reuses `parseInstrument` / `parseInstrumentTag`. No `instrument_kind` column. No query-param API change (list already includes `tags`).
- [x] AC-06: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB/N1/N-BUILD-3/alembic/A4/AssessmentRun merge.
- [ ] AC-07: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `AssessmentCreate.test.tsx` — wrong-purpose hidden; empty author link; wrong-purpose seed refused
- [x] Unit: `InductionCreate.test.tsx` — same for induction
- [x] Unit: `Audits.test.tsx` — schedule options exclude skills/induction; untagged included
- [x] Unit: `auditInstrument.test.ts` — `templatesMatchingInstrument`
- [ ] Hosted CI — pending

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Skills create picker hides audit/induction/untagged templates (unit).
- [x] CUJ-02: No skills templates → author link to builder with `?instrument=skills` (unit).
- [x] CUJ-03: Schedule Audit picker includes untagged + `instrument:audit`; excludes skills/induction (unit).

## 7) Observability & Ops
- FE filter only. No new metrics.

## 8) Release Plan
1. Branch from LIVE tip `935604f61`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Skills/induction templates appear on Audits schedule; AssessmentCreate can start an audit/induction instrument; wrong-purpose `templateId` is silently selected; `audit_type` overloaded; alembic added.
- **Rollback steps:** Revert merge; redeploy `935604f61`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1774** @ `935604f61`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1774 LIVE; L11–L16 held; continue given
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
