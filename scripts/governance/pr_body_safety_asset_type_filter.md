# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Safety Asset Register — filter by asset type
- **User goal (1–2 lines):** Let users narrow the KPI board and asset lists to one equipment type (e.g. Fire Extinguisher) from the toolbar.
- **In scope:** Board-level type select; filters KPIs, Assets / By engineer / By vehicle / By type rollups; persist selection in localStorage
- **Out of scope:** Multi-select types; server-side paging by type; check-and-challenge Audit Builder coach
- **Feature flag / kill switch:** N/A — UI filter only

## 2) Impact Map (what changed)
- **Frontend:** `frontend/src/pages/SafetyAssetRegister.tsx`
- **Backend / APIs / DB / workflows / deps:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UI
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change

## 4) Acceptance Criteria (AC)
- [x] AC-01: Toolbar “Asset type” select lists loaded types + “All types”
- [x] AC-02: Selecting a type scopes hero KPIs and Assets / rollup tables to that type
- [x] AC-03: Selection persists across reload via localStorage; clears if type disappears
- [x] AC-04: Upload (CES) view hides the type filter (not applicable)

## 5) Testing Evidence
- [x] Local code review of filter pipeline (hide removed → type → hero band → search)
- [ ] CI on this PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Select Fire Extinguisher → All count drops to FE inventory; PE* rows visible
- [x] CUJ-02: Clear to All types → full board restored
- [x] CUJ-03: Hide removed + type filter compose correctly

## 7) Observability & Ops
- No change

## 8) Release Plan
- Squash-merge → SWA bake → smoke Asset Register type filter

## 9) Rollback Plan
- Revert merge commit / prior tip

## 10) Evidence Pack
- CI linked after PR create

---

# Gate Checklist
- [x] Gate 0–1
- [x] Gate 2 (CI)
- [ ] Gate 3–4 staging/canary
- [x] Gate 5 prod verification plan
