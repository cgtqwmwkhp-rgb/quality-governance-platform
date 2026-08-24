# Change Ledger (CL-UX-P1-FORMS-CONTRAST)

> **Start gate:** #1761 LIVE — tip `ec07e0ecafb9`. `STACK_MAX=1`. Merge ≠ LIVE.
> L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt, CRM-LIB is CRM work.

## 1) Summary
- **Feature / Change name:** Admin form builder residual P1 color-contrast
- **User goal:** `/admin/forms/new` must pass axe `color-contrast` so the UX coverage gate can leave CANARY 90.
- **In scope:** Delete-form control text; on-page helper/placeholder contrast on FormBuilder.
- **Out of scope:** Entra flag, Assist triad, Exceptions cap, invented EXACT, Dependabot, CRM-LIB, global `--destructive` token retune, other pages.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| UX-P1-05 | Delete form control | `text-destructive` on outline (`hsl(0 85% 55%)` ≈ 4.2:1 vs white) | `text-foreground` + `border-destructive/40` (danger from border, AA text) |
| UX-P1-06 | Helper / placeholder copy | `text-muted-foreground` / default placeholder | `text-foreground-secondary` / `placeholder:text-foreground-secondary` |

## 3) Compatibility & Data Safety
- Markup/a11y only. No schema, flag, or write-path change.
- **Rollback strategy:** Revert merge and redeploy prior tip `ec07e0ecafb9`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| UX coverage P1 a11y | CANARY 90: 1 residual P1 `color-contrast` on `admin-forms-new` | Same CUJs; axe color-contrast on that page addressed |
| TrapGuard / Entra / Assist / Exceptions cap | Untouched | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Delete form is not `text-destructive`; uses `text-foreground`.
- [x] AC-02: Visible helper/placeholder text on `/admin/forms/new` uses foreground-secondary, not muted.
- [x] AC-03: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB change.
- [ ] AC-04: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); STG health SHA = PROD health SHA = tip → LIVE / DONE.
- [ ] AC-05: Next UX coverage run on the LIVE SHA reports 0 P1 on `admin-forms-new`.

## 5) Testing Evidence (link to runs)
- [x] Unit: FormBuilder delete control is not `text-destructive`
- [x] Measured P1: UX coverage `31895825268` on LIVE `ec07e0ecafb9` — `admin-forms-new` 1 serious `color-contrast`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: New form still creates via admin config API; Add Field palette still works.
- [x] CUJ-02: Back / step name / expand names from #1761 are unchanged.

## 7) Observability & Ops
- Coverage gate stays CANARY until this image is LIVE and the next UX run is measured. Do not tick Verified from merge.

## 8) Release Plan
1. Branch from LIVE tip `ec07e0ecafb9`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Form builder save/add-field regresses; Entra/Assist invented.
- **Rollback steps:** Revert merge; redeploy `ec07e0ecafb9`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1761** @ `ec07e0ecafb9`
- UX P1: run `31895825268`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1761 LIVE; L11–L16 held
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
