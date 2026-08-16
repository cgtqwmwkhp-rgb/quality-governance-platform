# Change Ledger (CL-AUDITS-NBUILD1-IDENTITY)

> **Start gate:** #1773 LIVE — tip `3f078f96d`. `STACK_MAX=1`. Merge ≠ LIVE.
> David said **continue** (hardened 20m conveyor). L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt, CRM-LIB is CRM work.
> N-BUILD-2 picker filter, N1 locate, alembic, A4, and merging AssessmentRun are not this slice.

## 1) Summary
- **Feature / Change name:** N-BUILD-1 — Audit & Assessment Builder identity
- **User goal:** One builder authors checklists for audits, skills assessments, and inductions. Purpose is a tag (`instrument:*`), not `audit_type`.
- **In scope:** Nav/library copy, purpose chooser, instrument chips, stamp `tags_json` on save, post-publish CTA, `?templateId=` seed on Audits / AssessmentCreate / InductionCreate, PATCH `tags` → `tags_json`.
- **Out of scope:** N-BUILD-2 picker filter. N1 locate. Alembic / new tables. Entra. EXACT. A4 four-column board. Merging AssessmentRun. Overloading `audit_type`. Moving Workforce Assessments under Audits. UVDB/PM twin. Dependabot.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| NB1-01 | Nav label | Audit Builder (`nav.audit_builder`) | Audit & Assessment Builder. Route `/audit-templates`. Hub id `assurance` |
| NB1-02 | Library | Audit Template Library | Audit & Assessment Library + purpose chooser + All/Audits/Skills/Inductions chips |
| NB1-03 | New template | `/audit-templates/new` | `/audit-templates/new?instrument=audit\|skills\|induction` required to save |
| NB1-04 | Tags | PATCH setattr `tags` (not persisted) | PATCH remaps `tags` → `tags_json`. Untagged LIVE templates default to audit and stamp on save |
| NB1-05 | Post-publish CTA | Audit scheduling copy only | Purpose-matched run: `/audits`, `/workforce/assessments/new`, `/workforce/training/new` with `?templateId=` |

## 3) Compatibility & Data Safety
- No schema change. No alembic. `audit_type` still defaults to inspection.
- Instrument is `tags_json` (`instrument:audit` / `instrument:skills` / `instrument:induction`). Existing builder_brief / source_case tags are preserved.
- **Rollback strategy:** Revert merge and redeploy `3f078f96d`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Purpose vs audit_type | One builder labelled audit-only | Purpose is a tag; inspection `audit_type` unchanged |
| Workforce assessments under Audits | Refused | Untouched — skills/induction still create via Workforce routes |
| Invented EXACT / Entra / A4 | Refused | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Nav `nav.audit_builder` is Audit & Assessment Builder; route `/audit-templates`; hub id `assurance`.
- [x] AC-02: Library title/subtitle match the operator contract. + New Template opens a 3-card purpose chooser and navigates with `?instrument=`.
- [x] AC-03: Instrument chips All · Audits · Skills · Inductions. Untagged LIVE templates default to Audit.
- [x] AC-04: New template cannot save without a purpose. Existing untagged templates default to audit and stamp `instrument:audit` on save. Other tags preserved.
- [x] AC-05: After publish, primary CTA matches purpose (`templateId` query). AssessmentCreate / InductionCreate / Audits honour `?templateId=`.
- [x] AC-06: PATCH `/templates/{id}` writes `tags_json`, not an unknown `tags` attr.
- [x] AC-07: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB/N-BUILD-2/N1/alembic/A4/AssessmentRun merge.
- [ ] AC-08: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `auditInstrument.test.ts`
- [x] Unit: `AuditTemplateLibrary.test.tsx` (chooser + chips)
- [x] Unit: Layout still asserts `nav.audit_builder` key
- [x] Unit: AssessmentCreate / InductionCreate `?templateId=` seed
- [x] Unit: PATCH tags → `tags_json` in `test_audit_template_routes.py`
- [ ] Hosted CI — pending

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator opens New Template, picks Skills, lands on `/audit-templates/new?instrument=skills` (unit).
- [x] CUJ-02: Untagged library templates appear under Audits chip (unit).
- [x] CUJ-03: Save stamps `instrument:*` without dropping `builder_brief` / `source_case` (unit).

## 7) Observability & Ops
- FE + one PATCH remap. No new metrics.

## 8) Release Plan
1. Branch from LIVE tip `3f078f96d`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** New Template navigates without instrument; PATCH drops tags or setattr `tags`; skills/induction CTA opens the wrong run type; `audit_type` overloaded.
- **Rollback steps:** Revert merge; redeploy `3f078f96d`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1773** @ `3f078f96d`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1773 LIVE; L11–L16 held; continue given
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
