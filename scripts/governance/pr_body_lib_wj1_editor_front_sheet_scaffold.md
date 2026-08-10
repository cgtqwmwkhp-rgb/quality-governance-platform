# Change Ledger (CL-LIB-WJ1-EDITOR-FRONT-SHEET-SCAFFOLD)

**Depends:** WJ-0 `#1693` LIVE tip `409e585b960` (STG=PROD).

## 1) Summary
- **Feature / Change name:** Library WJ-1 prep — native draft editor package shell + Front Sheet band stub (L-34…L-39 design lock)
- **User goal (1–2 lines):** After WJ-0 drops CRDT, Policy authors will draft native docs in-app and see a Front Sheet on binary docs — this PR only scaffolds the unmounted package so the later Detail PR stays small and size-limit-safe.
- **In scope:** NEW `frontend/src/library-editor/**` shell + Front Sheet stub; ADR-0024 (Proposed); size-limit notes; design note; Vitest smoke; this ledger
- **Out of scope:** DocumentDetail body / version publish; collaborative_* drop (WJ-0); alembic; WI-1 CEL; WI-2 file homes; document_graph; Documents list/upload; editing `.size-limit.json`
- **Feature flag / kill switch:** None — package is unmounted. Kill switch for later mount is “do not lazy-import”.

## 2) Impact Map (what changed)
- **Frontend:** `frontend/src/library-editor/**` (new only)
- **Backend:** None
- **APIs:** None
- **Database:** None — no Alembic
- **Config/env/flags:** None
- **Dependencies:** None new
- **Tests:** Vitest scaffold suite
- **Docs:** ADR-0024; `docs/governance/library-wj1-*.md`; this Change Ledger
- **Contract baseline:** Unchanged

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive unmounted FE package + docs. No runtime path changes.
- **Tolerant reader / strict writer applied?** N/A (no API)
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — revert merge / redeploy prior tip

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| L-14c editor stance documented in-repo | Canvas/plan only | ADR-0024 Proposed + design note |
| CRDT / Office forbidden before editor | Risk of mounting over collaborative_* | Explicit WJ-0 dependency; shell honesty copy |
| Shell size-limit | Index 187 kB budget | Unchanged — notes prescribe lazy chunk for implement PR |
| DocumentDetail single-owner | WB-1 layers LIVE | Prep does not touch Detail (WJ-1 owns later) |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `frontend/src/library-editor` exports NativeDraftEditorShell + FrontSheetBand + lazy loader
- [x] AC-02: No edits to DocumentDetail, Documents, collaborative_*, alembic, WI-1/WI-2, document_graph
- [x] AC-03: `.size-limit.json` untouched; size-limit notes document future chunk budget
- [x] AC-04: ADR-0024 + design note land under docs/
- [x] AC-05: Vitest scaffold suite passes locally
- [ ] AC-06: Full CI — on PR (OPEN after WJ-0 PROD gate for merge)

## 5) Testing Evidence (link to runs)
- [ ] Targeted Vitest `libraryEditorScaffold.test.tsx` — run on PR
- [ ] Full CI — on PR
- [ ] Staging / Prod tip verify — N/A until merge after WJ-0 LIVE

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Package imports resolve; shell shows WJ-0 waiting honesty; Front Sheet renders stub fields (unit)

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** None
- **Runbook updates:** None until implement PR

## 8) Release Plan (Local → Staging → Canary → Prod)
- **OPEN PR** after WJ-0 PROD. Merge only as prep ahead of Detail mount, or squash into WJ-1 implement PR.
- **DONE bar:** Conveyor marks WJ-1 PROD only after editor + Front Sheet LIVE on tip with size-limit green — not this scaffold alone.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Unlikely — unmounted code. If docs/ADR numbering conflicts, revert.
- **Rollback steps:** Revert merge; no DB rollback.
- **Owner:** Platform Engineering (Library spine) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Depends: WJ-0 DROP collaborative_* PROD

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [ ] **Gate 1:** WJ-0 PROD LIVE (hard dependency for mount; merge of scaffold-only may proceed earlier if conveyor allows docs/FE-unmounted prep — confirm at open-PR time)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** No DocumentDetail / publish path in diff
