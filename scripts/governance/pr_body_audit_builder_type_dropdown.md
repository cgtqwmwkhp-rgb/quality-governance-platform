# Change Ledger (CL-AUDIT-BUILDER-TYPE-DROPDOWN-SCROLL)

## File allowlist (exclusive)
- `frontend/src/pages/audit-builder/QuestionEditor.tsx`
- `frontend/src/pages/audit-builder/__tests__/questionTypeMenuPlacement.test.ts`
- `scripts/governance/pr_body_audit_builder_type_dropdown.md`

**Out of scope:** Backend, Document Spine, Investigation builder redesign, package.json.

## 1) Summary
- **Feature / Change name:** Audit/Assessment Builder question-type dropdown scroll fix
- **User goal:** Scroll through all question types (Checklist, Short/Long Text, Numeric, Date, Photo, Signature) when the menu is open.
- **In scope:** Portal listbox scroll + viewport-clamped max height; ignore in-menu scroll for dismiss.
- **Out of scope:** Changing the type catalogue; native `<select>` rewrite.
- **Feature flag / kill switch:** None — revert commit.

## 2) Impact Map (what changed)
- **Frontend:** `QuestionTypeSelector` in QuestionEditor — scroll listener + placement helper.
- **Backend / APIs / Schemas / Database:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UX fix; same QUESTION_TYPES values.
- **Tolerant reader / strict writer applied?** N/A.
- **Breaking changes:** None.
- **Migration plan:** N/A.
- **Rollback strategy (DB):** Revert commit only.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Question-type menu remains open while scrolling inside the list
- [x] AC-02: Menu max-height clamps to available viewport so overflow-y scroll engages
- [x] AC-03: All QUESTION_TYPES remain selectable (including types below Multiple Choice)
- [x] AC-04: Outer page scroll / Escape / outside click still dismisses the menu

## 5) Testing Evidence (link to runs)
- [x] Unit: `questionTypeMenuPlacement.test.ts`
- [ ] CI — this PR checks
- [ ] Tip LIVE glance — open Audit Builder type menu and scroll to Signature

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Audit Builder → question → open type dropdown → scroll → select Short Text
- [x] CUJ-02: Assessment/Audit Builder draft → change Yes/No to Photo via scrolled menu

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** N/A
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open type menu mid-page; scroll to last option; select.
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same glance on tip SWA.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Menu cannot open / types missing
- **Rollback steps:** Revert squash-merge; force_deploy previous SHA
- **Owner:** Tip-owner conveyor

## 10) Evidence Pack (links)
- CI: this PR
- Root cause: capture-phase `scroll` listener closed menu on in-list scroll

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts — FE-only listbox behaviour
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) — N/A
- [ ] **Gate 5:** Production verification plan + monitoring ready
