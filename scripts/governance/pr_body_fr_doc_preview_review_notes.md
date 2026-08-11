# Change Ledger (CL-FR-DOC-PREVIEW-REVIEW-NOTES)

> Base: `origin/main` @ `c977c5e8` (#1726 nav tip).
> Library Document Detail: Preview as its own top-layer view + next-review notes pad.

## 1) Summary

- **Feature / Change name:** FR-DOC-PREVIEW-REVIEW-NOTES — Preview tab + next-review notes
- **User goal:** Preview is a first-class Document View layer (not buried under Control). Operators capture notes for the next review beside the file.
- **Problem:** Preview lived only at the bottom of Control; no working pad for review context on published docs.
- **In scope:**
  - Document Detail spine adds `preview` layer (`?tab=preview`)
  - Inline reader + open/download on that layer; Control keeps a handoff link
  - `review_notes` on DocumentResponse + LibraryDocumentPatch; PATCH may save notes on published rows without a version bump
  - Tests for layer resolver + DocumentDetail layers
- **Out of scope:** Safety hub rename; Certificate-in-Schedule; Assist FIND-02; domain filters
- **Feature flag:** None

## 2) Impact Map

- **Backend:** `src/api/routes/documents.py` — response + patch for `review_notes`
- **Frontend:** `documentEvidenceTab.ts`, `DocumentDetail.tsx`, layer tests
- **DB:** None (column already exists)

## 3) Compatibility & Data Safety

- **Compatibility:** Additive optional `review_notes` on DocumentResponse; new tab id.
- **Breaking:** None. Control no longer embeds the full preview reader (handoff to Preview tab).
- **Rollback:** Revert merge; redeploy. Notes data retained in DB.

## Compliance Delta

| Control | Before | After |
| --- | --- | --- |
| Document Preview | Control footer only | Dedicated Preview layer |
| Next-review context | Reject-path / unused field | Editable notes pad on Preview (incl. published) |

## 4) Acceptance Criteria

- [x] **AC-01:** Tabs include Preview after Assurance; `?tab=preview` opens that layer
- [x] **AC-02:** Preview layer shows file actions + inline reader
- [x] **AC-03:** Next-review notes textarea + save via PATCH without version bump
- [x] **AC-04:** Published documents can save `review_notes` (content fields still draft-gated)
- [x] **AC-05:** Layer unit/UI tests cover seven layers + preview panel
- [x] **AC-06:** No test skipped/loosened

## 5) Testing Evidence

- [x] `vitest` documentEvidenceTab + DocumentDetailLayers — **21 passed**
- [ ] Full CI / tip LIVE — after merge

## 6) Critical Journeys

- [x] **CUJ-01:** Open document → Preview tab → inline reader
- [x] **CUJ-02:** Save next-review notes on a published document
- [x] **CUJ-03:** Control handoff “Open Preview” deep-links `?tab=preview`

## 7) Observability & Ops

- No new metrics. Existing document PATCH audit path applies.

## 8) Release Plan

1. Merge after CI green (admin-merge authorised).
2. Main CI → STG → PROD with `release_sha` = tip.
3. Spot-check Library Document Detail Preview tab + notes save.

## 9) Rollback Plan

- **Trigger:** Preview tab missing/broken; notes save refuses on published.
- **Steps:** Revert merge; redeploy prior tip.
- **Owner:** Platform Engineering — David Harris

## 10) Evidence Pack

- Vitest 21 passed
- Change Ledger: this body

---

# Gate Checklist

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Additive API field (existing column)
- [x] **Gate 2:** Touched FE tests green
- [x] **Gate 3:** Rollback = revert deploy
- [ ] **Gate 4:** CI green on PR
- [ ] **Gate 5:** Tip LIVE verified
