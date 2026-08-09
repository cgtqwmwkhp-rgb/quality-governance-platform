# Change Ledger (CL-LIB-NS-EXP-BAND-EMPTY-COPY)

## 1) Summary
- **Feature / Change name:** Library Northern Star W8 follow-up — Structure map honest empty copy when a cascade band has no documents
- **User goal (1–2 lines):** Choosing an empty L1–L5 band must not claim the focus document has no confirmed implements relationships.
- **In scope:** Canvas empty-state copy in `DocumentStructureMap.tsx` + regression test.
- **Out of scope:** Aggregate API, IMS052, orphan board, Function filter.
- **Feature flag / kill switch:** Unchanged — Structure map still behind `document_graph` + `document_graph_structure_map`.

## 2) Impact Map (what changed)
- **Frontend:** `DocumentStructureMap.tsx` empty canvas copy distinguishes band-empty from no-implements; test added.
- **Backend / APIs / Database / Config:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UX copy only.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy (DB):** N/A — revert commit.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Empty-band honesty on Structure map | Canvas reused “no confirmed implements” copy | Explicit “no documents in this cascade band” copy |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Selecting a band with zero documents shows band-empty copy, not implements-missing copy.
- [x] AC-02: Selecting a band with documents still focuses and renders the map.
- [x] AC-03: Vitest covers the band-empty canvas path.

## 5) Testing Evidence (link to runs)
- [x] `DocumentStructureMap.test.tsx` — 7 passed locally
- [ ] Full CI — on PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator opens Structure map, clicks an empty L1 band, sees band-empty copy.
- [x] CUJ-02: Operator clicks L3 (populated), picker and map still work.

## 7) Observability & Ops
- No new signals. Copy-only.

## 8) Release Plan
1. Merge to `main` after CI green.
2. Tip-chase STG/PROD via governed deploy.
3. Smoke: `/documents/structure` with flags on — empty band shows honest copy.

## 9) Rollback Plan (Mandatory)
- **Trigger:** Empty-band copy regresses or misleads operators.
- **Rollback steps:** Revert the merge commit; redeploy previous tip. No schema.
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack
- Parent wave: PR #1684 W8 NS-EXP (merged `41da8d832`).
- Bugbot finding on #1684: “Band filter wrong canvas copy” (resolved after fix).

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC + Change Ledger complete
- [x] **Gate 1:** Copy-only; no twin surface
- [ ] **Gate 2:** CI green on the PR
- [x] **Gate 3:** Vitest verified locally
- [x] **Gate 4:** No migration
- [ ] **Gate 5:** DONE = tip LIVE after merge — not claimed here
