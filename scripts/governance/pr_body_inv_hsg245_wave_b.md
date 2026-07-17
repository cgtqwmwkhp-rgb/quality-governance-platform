# Change Ledger (CL-INV-HSG245-WAVE-B)

## 1) Summary
- **Feature / Change name:** INV-HSG245-WAVE-B — four-level HSG245 investigation model + level-aware section gates
- **User goal:** Investigations use `minimal` through `high` levels with named section gates, level-scoped Report tab content, and Template Builder `min_level` controls — without changing the Investigations list page (Wave A / #1109)
- **In scope:** Domain model, closure validation, Detail Report tab, Template Builder `min_level`, contract v2.2
- **Out of scope:** Wave A list chrome; Wave C customer-pack omit/approval RBAC; Alembic
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `InvestigationDetail.tsx`, investigation-builder (Template Builder, contract sections, helpers), HSG245 report sections — **not** `Investigations.tsx`
- **Backend / APIs / DB:** `InvestigationLevel.MINIMAL`, level-aware closure validation, additive API `level` field
- **Config/env/flags:** None
- **Dependencies:** Merged #1109 on main (`be8e3f2d`)

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive `min_level` JSON metadata; templates without `min_level` default safely to MINIMAL
- **Breaking changes:** None — named contract sections retain backward-compatible gates
- **Migration plan:** N/A (no Alembic)
- **Rollback strategy:** Revert squash-merge

## 4) Acceptance Criteria (AC)
- [x] AC-01: No Wave A list-page changes in this PR
- [x] AC-02: Closure validation uses named section `min_level` instead of positional first-N heuristic
- [x] AC-03: Investigation level supports four values, including `minimal`
- [x] AC-04: Detail Report tab shows only sections in scope for the run level
- [x] AC-05: Minimal/low omit deep RCA; HIGH includes HSG245 analysis, SMART CAPA, fishbone, management-system review
- [x] AC-06: Template Builder persists section `min_level` alongside existing field controls

## 5) Testing Evidence (link to runs)
- [x] `pytest tests/unit/test_investigation_service.py tests/integration/test_investigation_stage2.py -q` — 26 passed
- [x] `npx vitest run src/pages/investigation/__tests__/hsg245ReportSections.test.ts src/pages/investigation-builder/__tests__/templateHelpers.test.ts src/pages/investigation-builder/__tests__/contractSections.test.ts` — 9 passed
- [x] `npm run build` — passed
- [ ] CI after merge + Change Ledger fix

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Negligible/near-miss source creates MINIMAL investigation with facts, immediate actions, sign-off only
- [x] CUJ-02: Investigator opens HIGH run Report tab and sees complete HSG245 report scope
- [x] CUJ-03: Template Builder admin assigns section `min_level` and setting persists in template JSON
- [x] CUJ-04: Closure validation skips HIGH-only section for MEDIUM and blocks for HIGH when incomplete

## 7) Observability & Ops
- Existing investigation timeline / closure-validation endpoints unchanged; level surfaced on API responses

## 8) Release Plan (Local → Staging → Canary → Prod)
- Merge after Wave A (#1109) on main; verify Template Builder + Detail Report tab per level on staging

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Level gating blocks valid closures or hides required report sections
- **Rollback steps:** Revert squash-merge
- **Owner:** Platform / Investigations track

## 10) Evidence Pack (links)
- Wave A merged: #1109 (`be8e3f2d`)
- Tip base at branch open: `15eab9f8`
- Customer-pack omit/approval reserved for Wave C

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Contract/domain model — MINIMAL level + v2.2 sections
- [x] **Gate 2:** Level-aware closure validation + Template Builder `min_level`
- [x] **Gate 3:** HIGH report depth (HSG245, CAPA, fishbone, mgmt-system review)
- [ ] **Gate 4:** CI green after merge
- [x] **Gate 5:** No Alembic; Wave C RBAC explicitly deferred

Made with [Cursor](https://cursor.com)
