# Change Ledger (CL-LIB-WA1-REGISTER)

## 1) Summary
- **Feature / Change name:** Library SECOND belt WA-1 — Master Document Register (ALL docs + PEL lead + Hyperlink)
- **User goal (1–2 lines):** The existing Documents list is the Master Document Register: every library document remains visible (optional filters only), PEL leads when present, and every filed row has a working Hyperlink to Detail via `href_registry` — never blank.
- **In scope:** List projection `href` on `DocumentResponse` via `document_href`; Register list/grid PEL + Hyperlink columns on `Documents.tsx`; register helpers + unit tests; list search includes `pel_doc_ref`; Change Ledger
- **Out of scope:** Function seed / PEL allocator migration (WA-2); Owner column (no library `owner` field yet — Author not invented on Register); Document Control merge; IMS052 export; second Register page; Function/Category dual-axis UI
- **Feature flag / kill switch:** None — additive list projection + Register UX on existing `/documents`

## 2) Impact Map (what changed)
- **Frontend:** `Documents.tsx` (list default; PEL + Hyperlink columns); `documentsRegisterHelpers.ts`; i18n en/cy; Documents + helper tests
- **Backend:** `src/api/routes/documents.py` — `_document_to_response` projects `href` from `href_registry.document_href`; list search matches `pel_doc_ref`
- **APIs:** `DocumentResponse.href` (required string Detail path); additive
- **Database:** None
- **Config/env/flags:** None
- **Dependencies:** None
- **Tests:** `tests/unit/test_documents_list_response.py`; `frontend/src/pages/__tests__/documentsRegisterHelpers.test.ts`; `Documents.test.tsx` Register assertions
- **Docs:** This Change Ledger

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive `href` on existing Document responses; FE prefers API `href`, fallback mirrors registry path for partial fixtures
- **Breaking changes:** None (clients ignoring `href` unchanged)
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR / redeploy prior tip

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Master Document Register home | Documents list = all active docs (paginated) but PEL/Hyperlink not explicit Register columns | Same single list SoT; PEL lead + Hyperlink column; list default |
| Document open path | Row click used ad-hoc `/documents/{id}` | List projection `href` from `href_registry`; Hyperlink uses projected path |
| Twin Register / dual SSOT | Risk of inventing second Register page | Enhance existing Documents only (D1) |
| Owner vs Author (D3) | Uploaded By on list; no library Owner field | No Author column invented; Owner deferred until control-layer field is easy |

## 4) Acceptance Criteria (AC)
- [x] AC-01 (L-01): Register remains the existing Documents list — all active tenant library docs (ACL-visible); no second Register page; no default hard filter hiding the estate
- [x] AC-02 (L-05): PEL shown as Register lead when `pel_doc_ref` present; DOC remains secondary
- [x] AC-03 (L-05b): Every filed row has a non-blank Hyperlink to Detail via list `href` from `href_registry.document_href`
- [x] AC-04: Hyperlink opens Detail (artefact open remains signed-url elsewhere) — not binary edit
- [x] AC-05: No Function/PEL allocator / `functions.json` migration in this PR (WA-2)
- [x] AC-06: Unit tests cover list `href`/`pel_doc_ref` projection and Register href/PEL helpers

## 5) Testing Evidence (link to runs)
- [x] `pytest tests/unit/test_documents_list_response.py` — local
- [x] `vitest` Documents + documentsRegisterHelpers — local
- [ ] Full CI — on PR
- [ ] Staging / Prod tip verify — after merge per conveyor (DONE ≠ merge)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator opens `/documents` → Register list shows docs with Hyperlink Open → Detail
- [x] CUJ-02: Doc with `pel_doc_ref` shows PEL in Register column / lead chip
- [x] CUJ-03: Doc without PEL still has Hyperlink (never blank) and DOC lead
- [x] CUJ-04: Search can match `pel_doc_ref` on list API

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** None new
- **Runbook updates:** None — WA-2 owns Function allocator cutover

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging / Prod:** Ship with tip; no flag flip
- **Canary plan:** N/A
- **DONE bar:** Conveyor marks WA-1 PROD/DONE only after tip SHA is LIVE on ACA + health verified

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Register Hyperlink/PEL columns confuse operators or `href` field breaks a consumer
- **Rollback steps:** Revert merge; redeploy prior tip; `href` is additive so FE-only revert also restores prior columns if needed
- **Owner:** Platform Engineering (Library spine) — David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR checks complete
- Staging deploy evidence: After merge tip chase
- Canary evidence (if applicable): N/A
- Acceptance notes: Pre-WA-1 list already enumerated all active ACL-visible docs; this slice makes PEL + Hyperlink explicit Register columns and registry-backed `href`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX — additive `href` via href_registry; enhance Documents list only
- [ ] **Gate 2:** CI green (lint/type/build/tests as applicable)
- [x] **Gate 3:** Staging verification plan — tip SHA after merge
- [x] **Gate 4:** Canary healthy (if used) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — tip SHA LIVE before DONE
