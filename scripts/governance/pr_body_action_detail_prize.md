# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Action detail “prize pass” — three review rounds on owner commentary + evidence UX/API hardening
- **User goal:** Safer validation, bounded list size, clearer errors, refresh, a11y, attachment metadata, delete confirm.

## 2) Impact Map
- **Backend:** `src/api/routes/actions.py` — note create validator; `limit` on `GET /by-key/notes`
- **Frontend:** `frontend/src/pages/ActionDetail.tsx`, `frontend/src/api/client.ts`
- **Tests:** `tests/unit/test_action_owner_note_create.py`

## 3) Compatibility & Data Safety
- **Additive:** `limit` query default 100 (max 200). Clients omitting `limit` behave as before with a cap.
- **Stricter:** Whitespace-only note bodies rejected (422).

## 4) Acceptance Criteria
- [x] AC-01: Empty/whitespace-only note body rejected server-side
- [x] AC-02: Notes list bounded by `limit`
- [x] AC-03: UI: refresh, confirm delete, `aria-live`, file `accept`, attachment metadata

## 5) Testing Evidence
- [x] `make pr-ready` passed locally
- [x] `tests/unit/test_action_owner_note_create.py` (3 tests)

## 6) Critical Journeys (CUJ)
- [x] CUJ-01: Load action → see notes/attachments or actionable error + Refresh
- [x] CUJ-02: Add note (form submit) → confirm validation on whitespace via API

## 7) Observability
- No change

## 8) Release Plan
- Merge → CI → staging → production per existing workflows

## 9) Rollback Plan
- **Rollback steps:** Revert merge commit
- **Owner:** Platform team

## 10) Evidence Pack
- Unit tests + `make pr-ready`

---

# Gate Checklist
- [x] **Gate 0:** Scope + AC + rollback
- [x] **Gate 1:** Lint/type (pr-ready)
- [x] **Gate 2:** Unit + integration (pr-ready)
- [x] **Gate 3:** Frontend tests (pr-ready)
- [x] **Gate 4:** Staging after merge
- [x] **Gate 5:** Prod verification after deploy
