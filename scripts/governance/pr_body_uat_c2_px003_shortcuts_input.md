# Change Ledger (CL-UAT-C2-PX003)

## 1) Summary
- **Feature / Change name:** PX-003 — Ignore global shortcuts overlay in editable fields
- **User goal (1–2 lines):** Typing `?` (Shift+/) in form fields must not open the keyboard-shortcuts dialog or swallow keystrokes.
- **In scope:** `useKeyboardShortcuts` editable-target guard; vitest proofs; this Change Ledger
- **Out of scope:** New shortcuts, Layout/search palette changes, backend, E2E harness
- **Feature flag / kill switch:** N/A — FE keyboard handler only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):**
  - `frontend/src/hooks/useKeyboardShortcuts.ts` — treat input/textarea/select/contenteditable and ARIA combobox/listbox/searchbox as editable; skip bare-key and shift-only shortcuts there; retain ctrl/meta/alt combos (e.g. save)
  - `frontend/src/hooks/__tests__/useKeyboardShortcuts.test.ts` — Shift+? + searchbox regression tests
  - `frontend/src/components/__tests__/KeyboardShortcutHelp.test.tsx` — input focus regression for shortcuts dialog
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Narrower shortcut interception; no API or persistence change
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None — Shift+? outside editable fields still opens help
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Typing `?` in `<input>` does not open shortcuts overlay or call `preventDefault`
- [x] AC-02: Typing `?` in `<textarea>` / `<select>` / `contenteditable` is not intercepted
- [x] AC-03: Elements with `role=combobox|listbox|searchbox` (including ancestors) skip bare-key shortcuts
- [x] AC-04: Shift+? on non-editable focus still opens keyboard shortcuts help
- [x] AC-05: Ctrl/Meta/Alt shortcuts (e.g. Ctrl+S save) still work inside text fields
- [x] AC-06: Unit tests cover hook + `KeyboardShortcutHelp` mount paths

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `frontend` vitest `useKeyboardShortcuts.test.ts`, `KeyboardShortcutHelp.test.tsx` (local)
- [ ] Integration tests — N/A
- [ ] Contract tests — N/A
- [ ] E2E Smoke — N/A (keyboard handler lane)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Incident/record edit form — user types `?` in title/description without shortcuts modal
- [x] CUJ-02: Global search / filter inputs — punctuation and shift-modified keys reach the field
- [x] CUJ-03: Staff user presses Shift+? on page chrome — shortcuts help still opens

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open any form field, type `?`; confirm no overlay; Shift+? on sidebar still opens help
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check one text field + Shift+? help

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Legitimate global shortcuts fail to fire outside forms
- **Rollback steps:** Revert PR
- **Owner:** Platform / UAT Wave C2 track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A at draft open
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** FE-only; editable-target guard aligned to PX-003 repro
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Rollback plan verified
- [ ] **Gate 5:** Evidence pack linked / LIVE honesty noted

## Exclusive allowlist (this PR)
- `frontend/src/hooks/useKeyboardShortcuts.ts`
- `frontend/src/hooks/__tests__/useKeyboardShortcuts.test.ts`
- `frontend/src/components/__tests__/KeyboardShortcutHelp.test.tsx`
- `scripts/governance/pr_body_uat_c2_px003_shortcuts_input.md`
