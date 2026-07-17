# Change Ledger (CL-INV-LIST-COMPACT-SEVERITY)

## 1) Summary
- **Feature / Change name:** INV-LIST-A — compact Investigations work queue + level badge + drop INC043 chrome
- **User goal:** Investigations list is a dense work queue; opening a row goes to the investigation report (not a 5 Whys card strip); Template Builder has no INC043 label
- **In scope:** Compact list UI; remove Why 1–3 preview; navigate to detail; expose `level` on API/FE; soft-clean Template Builder user-facing INC043 copy
- **Out of scope:** Wave B four-level gating / detailed HIGH sections; Wave C customer-pack omit approval; Alembic
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `Investigations.tsx`, `Investigations.test.tsx`, `investigationsClient.ts`, Template Builder + checklist copy
- **Backend / APIs / DB:** `InvestigationRunResponse.level` (optional, additive)
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive OpenAPI field; list UX only
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Compact list rows; no Why 1–3 / “Not documented” RCA strip
- [x] AC-02: Header button reads “Template Builder” with no INC043
- [x] AC-03: List shows investigation level badge when API provides `level`
- [x] AC-04: Row click navigates to `/investigations/:id` (report), not 5 Whys modal

## 5) Testing Evidence (link to runs)
- [x] Frontend Vitest — Investigations (15 passed, local)
- [x] OpenAPI compatibility — additive `level` PASS (local)
- [ ] CI after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Safety & Cases → Investigations → compact rows → Open report route
- [x] CUJ-02: Template Builder entry has no INC043 in chrome

## 7) Observability & Ops
- Existing trackError on list load retained

## 8) Release Plan (Local → Staging → Canary → Prod)
- Staging/Prod: open Investigations; confirm dense rows + level badges; click opens detail report

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** List unusable / navigation broken
- **Rollback steps:** Revert squash-merge
- **Owner:** Platform / Investigations track

## 10) Evidence Pack (links)
- Tip base: `15eab9f8` (#1107)
- Soft conflict: #1105 also touches `Investigations.tsx` — rebase after this merges

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Compact list + level + INC043 chrome removal implemented
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Rollback plan verified
- [x] **Gate 5:** Evidence pack / LIVE honesty noted

## Exclusive allowlist (this PR)
- `frontend/src/pages/Investigations.tsx`
- `frontend/src/pages/__tests__/Investigations.test.tsx`
- `frontend/src/api/investigationsClient.ts`
- `frontend/src/pages/investigation-builder/InvestigationTemplateBuilder.tsx`
- `frontend/src/pages/investigation-builder/ContractSectionChecklist.tsx`
- `src/api/schemas/investigation.py`
- `scripts/governance/pr_body_inv_list_compact_severity.md`

Made with [Cursor](https://cursor.com)
