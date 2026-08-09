# Change Ledger (CL-LIB-WD1-WIZARD-SCAFFOLD)

## 1) Summary
- **Feature / Change name:** Library SECOND belt WD-1 prep — Filing wizard FE scaffold on existing upload modal (L-18/18b/18c spine)
- **User goal (1–2 lines):** An HSEQ filer uploading a library document walks File → Function confirm → Related → Bring-under-control chrome inside the existing Documents upload dialog — not a second Register or twin wizard app.
- **In scope:** Multi-step chrome on `Documents.tsx` upload modal; Function step calling `GET /document-categories/functions` and optional `function_code` on existing upload; Related honesty placeholder when `document_graph` is off (live `DocumentCreateRelationshipsStep` when on); Bring-under-control stub waiting for WC-1; i18n en/cy; Vitest
- **Out of scope:** Alembic; DocumentDetail body edits; WC-1 control/holds files; requiring Function at file (API remains optional until full WD-1 after WC-1 LIVE); heuristic Related propose; enabling `document_graph`; Register “Bring under control” entry on uncontrolled rows
- **Feature flag / kill switch:** None new. Related live step still gated by existing `document_graph` (default off). Function/`function_code` is additive optional Form field (WA-2 already LIVE).

## 2) Impact Map (what changed)
- **Frontend:** `Documents.tsx` upload modal → filing wizard phases; `documentFilingWizard.ts`; `DocumentFilingFunctionStep`; `DocumentFilingRelatedPlaceholder`; `DocumentFilingControlStub`; `DocumentFilingWizardChrome`; i18n `en.json` / `cy.json`; tests
- **Backend:** None
- **APIs:** Consumes existing `GET /api/v1/document-categories/functions` and optional `function_code` on `POST /api/v1/documents/upload` (WA-2) — no OpenAPI change
- **Database:** None — no Alembic
- **Config/env/flags:** None
- **Dependencies:** None
- **Tests:** Vitest helpers + step components + Documents upload spine paths
- **Docs:** this Change Ledger
- **Contract baseline:** Unchanged

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Enhance existing upload modal only. Upload no longer fires on file-pick alone — Function confirm (or explicit skip) precedes POST. Flag-off Related no longer auto-closes the modal; shows honesty then Control stub.
- **Tolerant reader / strict writer applied?** Yes — omit `function_code` still uploads; Doc Graph APIs never called when flag off
- **Breaking changes:** Upload UX timing changed (extra steps before/after POST). Callers of the upload API are unchanged.
- **Migration plan:** N/A (FE-only)
- **Rollback strategy (DB):** No DB change — revert merge / redeploy prior tip

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Function confirm at filing (L-18 / ADR-0023) | Upload had no Function picker; `function_code` unused by FE | Filers can confirm Function before upload; optional `function_code` sent when chosen |
| Related at create (L-18b) | Flag-on only; flag-off closed modal with no honesty | Flag-on keeps live step; flag-off shows honest “not recorded” placeholder |
| Bring under control (L-18c) | Ops-only / absent in-app | Honest WC-1-waiting stub in filing spine — no twin control API |
| Twin Register / wizard app | Risk of inventing second create surface | Single upload modal enhanced |
| WC-1 conflict surface | Parallel lane on lifecycle/holds | This PR touches FE upload modal only — no alembic, Detail, or WC-1 files |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Upload modal exposes File → Function → Related → Control chrome (one composition, existing dialog)
- [x] AC-02: Function step loads WA-2 vocabulary and can send `function_code` on upload; skip path omits the field
- [x] AC-03: With `document_graph` off, Related shows honesty placeholder and issues no Doc Graph requests
- [x] AC-04: With `document_graph` on, existing `DocumentCreateRelationshipsStep` mounts after upload, then Control stub
- [x] AC-05: Control stub is honest that Bring under control waits for WC-1 LIVE — no invented control API
- [x] AC-06: No Alembic, no DocumentDetail body edits, no WC-1 backend files in the diff
- [x] AC-07: Targeted Vitest passes locally (helpers + steps + Documents upload paths)

## 5) Testing Evidence (link to runs)
- [x] `vitest` `documentFilingWizard.test.ts` + `DocumentFilingWizardSteps.test.tsx` + `Documents.test.tsx` — 22 passed (local)
- [ ] Full CI — on PR
- [ ] Staging / Prod tip verify — after merge per conveyor (DONE ≠ merge; WD-1 full slice still blocked on WC-1 LIVE)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator opens Upload → picks file → Function step → upload without function → Related honesty (flag off) → Control stub → Done
- [x] CUJ-02: Operator confirms Function `IT` → upload FormData includes `function_code=IT`
- [x] CUJ-03: With `document_graph` on, post-upload Related live step → Skip → Control stub → Done

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** None new. Existing upload + Doc Graph create-edge paths unchanged.
- **Runbook updates:** None. Full L-18 required-at-file + L-18c Register entry wait for WC-1 LIVE + WD-1 product slice.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging / Prod:** FE-only; WA-2 functions endpoint must remain available (already LIVE).
- **Canary plan:** N/A — revert is the kill switch.
- **DONE bar:** Conveyor marks full WD-1 PROD only after WC-1 LIVE and the product slice (required Function + Register Bring under control) — this PR is prep scaffold only.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Upload modal stuck mid-wizard; Function vocabulary fetch blocking all uploads; Related honesty confusing operators.
- **Rollback steps:** Revert the merge and redeploy the prior tip. No DB rollback.
- **Owner:** Platform Engineering (Library spine) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: After merge tip chase
- Canary evidence (if applicable): N/A
- Acceptance notes: Prep parallel to WC-1 per `library-spine-conveyor` / Round 3 cascade lock. Full WD-1 remains blocked on WC-1 PROD.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX — enhance existing upload modal; WA-2 functions + optional function_code; Related honesty; Control stub
- [ ] **Gate 2:** CI green (lint/type/build/tests as applicable)
- [x] **Gate 3:** Staging verification plan — tip SHA after merge; upload wizard smoke with flags off
- [x] **Gate 4:** Canary healthy (if used) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — tip SHA LIVE before DONE; full WD-1 product still waits on WC-1
