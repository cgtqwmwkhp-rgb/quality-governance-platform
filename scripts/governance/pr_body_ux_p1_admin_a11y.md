# Change Ledger (CL-UX-P1-ADMIN-A11Y)

> **Start gate:** #1760 LIVE — tip `8361516885ce`. `STACK_MAX=1`. Merge ≠ LIVE.
> L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt, CRM-LIB is CRM work.

## 1) Summary
- **Feature / Change name:** Admin P1 a11y — partner webhooks + new form builder
- **User goal:** `/admin/partner-webhooks` and `/admin/forms/new` must pass axe critical/serious rules that currently HOLD the UX coverage gate (score 80).
- **In scope:** Loading status region on PartnerWebhooks; FormBuilder back name, step-name label, expand control, no nested interactives, empty-state contrast, unique field labels.
- **Out of scope:** Entra flag, Assist triad, Exceptions cap, invented EXACT, Dependabot, CRM-LIB, portal P0s.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| UX-P1-01 | Partner webhooks loading | `aria-label` on a generic `div` (`aria-prohibited-attr`) | `role="status"` + sr-only Loading text |
| UX-P1-02 | Form builder back | Icon-only control (`button-name`) | Accessible name "Back to forms" |
| UX-P1-03 | Form builder step row | `role="button"` wrapping a text input (`nested-interactive` + `label`) | Labeled step-name input; separate expand/collapse button |
| UX-P1-04 | Empty step / header contrast | muted + `opacity-50` (`color-contrast`) | Foreground text; decorative icon without opacity fade |

## 3) Compatibility & Data Safety
- Markup/a11y only. No schema, flag, or write-path change.
- **Rollback strategy:** Revert merge and redeploy prior tip `8361516885ce`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| UX coverage P1 a11y | HOLD: 2 pages, score 80 | Same CUJs, axe critical/serious on those two pages addressed |
| TrapGuard / Entra / Assist / Exceptions cap | Untouched | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Partner webhooks loading uses `role="status"`, not `aria-label` on a generic div.
- [x] AC-02: Form builder back control has an accessible name; step name is labelled; expand is a real button with `aria-expanded`.
- [x] AC-03: Step name input is not nested inside `role="button"`.
- [x] AC-04: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB change.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); STG health SHA = PROD health SHA = tip → LIVE / DONE.
- [ ] AC-06: Next UX coverage run on the LIVE SHA reports 0 P1 on these two pages.

## 5) Testing Evidence (link to runs)
- [x] Unit: PartnerWebhooks loading status; FormBuilder back/step/expand names
- [x] Measured P1: UX coverage `31891769295` on LIVE `8361516885ce` — `admin-partner-webhooks` `aria-prohibited-attr`; `admin-forms-new` `button-name`, `label`, `color-contrast`, `nested-interactive`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Webhooks list still loads tenant subscriptions from the API client.
- [x] CUJ-02: New form still creates via admin config API; Add Field palette still works.

## 7) Observability & Ops
- Coverage gate remains HOLD until this image is LIVE and the next UX run is measured. Do not tick Verified from merge.

## 8) Release Plan
1. Branch from LIVE tip `8361516885ce`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Form builder save/add-field regresses; webhook create/list regresses; Entra/Assist invented.
- **Rollback steps:** Revert merge; redeploy `8361516885ce`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1760** @ `8361516885ce`
- UX P1: run `31891769295`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1760 LIVE; L11–L16 held
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
