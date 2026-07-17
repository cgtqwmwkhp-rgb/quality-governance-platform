# Investigation HSG245 levels — Wave B

## Summary

Introduces the four-level HSG245 investigation model without changing the Investigations list chrome:

- adds `minimal` as a first-class investigation level and maps negligible / near-miss potential to it;
- replaces positional closure validation with named, level-aware section gates;
- presents the level-appropriate report scope in the Investigation Detail Report tab, including the HIGH HSG245 analysis, SMART CAPA, fishbone, and management-system/risk-assessment review pack;
- lets Template Builder administrators persist a section `min_level` (`minimal` through `high`) alongside existing field removal / required controls.

Wave C customer-pack omit/approval RBAC is explicitly out of scope.

## Gate 0 — Scope and branch

- [x] Branch starts from `origin/main`: `path11/inv-hsg245-levels-wave-b`
- [x] No rebase or edits to Wave A PR #1109
- [x] No list-page chrome changes in `Investigations.tsx`
- [x] No customer-pack omit/approval/RBAC implementation

## Gate 1 — Contract and domain model

- [x] `InvestigationLevel.MINIMAL = "minimal"` added
- [x] Investigation API/client exposes the level
- [x] Template Contract v2.2 defines MINIMAL and the named HIGH-only HSG245, CAPA, fishbone, and management-system review sections

## Gate 2 — Level-aware behaviour

- [x] Closure validation uses a named section's `min_level` rather than the former first-N-section heuristic
- [x] Existing named contract sections retain backward-compatible gates
- [x] Template Builder serializes and restores `min_level`
- [x] Detail Report tab shows only the report sections in scope for the run level

## Gate 3 — HIGH report depth

- [x] HIGH report scope includes structured place/plant/people/process and immediate/underlying/root-cause analysis
- [x] HIGH report scope includes SMART CAPA, fishbone, and management-system/risk-assessment review
- [x] MEDIUM retains concise root-cause analysis; MINIMAL omits deep RCA

## Gate 4 — Verification

- [x] `pytest tests/unit/test_investigation_service.py tests/integration/test_investigation_stage2.py -q` — 26 passed
- [x] `npx vitest run src/pages/investigation/__tests__/hsg245ReportSections.test.ts src/pages/investigation-builder/__tests__/templateHelpers.test.ts src/pages/investigation-builder/__tests__/contractSections.test.ts` — 9 passed
- [x] `npm run build` — passed

## Gate 5 — Risk and follow-up

- [x] No Alembic migration: `min_level` is additive JSON structure metadata
- [x] Existing templates without `min_level` default safely to MINIMAL unless they use a named contract section with a defined gate
- [x] Customer-pack section omit remains reserved for Wave C

## Acceptance criteria

- [x] AC-01: No Wave A list-page changes in this PR.
- [x] AC-03: Investigation level supports four values, including `minimal`.
- [x] AC-05: Minimal/low do not require deep RCA; HIGH has detailed RCA/HSG245 analysis, CAPA, fishbone, and management-system review.
- [x] AC-06: Template Builder can set section `min_level` and admins can remove/reduce fields through the existing builder controls.
- [ ] AC-07/AC-08: Customer-pack omit approval is Wave C and intentionally excluded.

## Critical user journeys

- [x] CUJ-01: A negligible/near-miss potential source creates a MINIMAL investigation with facts, immediate actions, and sign-off only.
- [x] CUJ-02: An investigator opens a HIGH run's Report tab and sees the complete HSG245 report scope.
- [x] CUJ-03: A Template Builder administrator assigns a section's minimum level and the setting persists in template structure JSON.
- [x] CUJ-04: Closure validation skips a HIGH-only section for MEDIUM and blocks it for HIGH when its required fields are incomplete.
