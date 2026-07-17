# Change Ledger (CL-AUD-W-01)

**Path claim:** `path11/aud-w01-work-lanes`

## File allowlist (exclusive)

- `frontend/src/pages/auditsBoardModel.ts`
- `frontend/src/pages/Audits.tsx`
- `frontend/src/pages/__tests__/auditsBoardModel.test.ts`
- `frontend/src/pages/__tests__/Audits.test.tsx`
- `scripts/governance/pr_body_aud_w01_work_lanes.md`

**Zero overlap** with parallel lanes: documents, reference_number, incidents, complaints, governed_knowledge, AuditTemplateBuilder, AssessmentCreate, builderMapAssistHonesty, PlanetMark, CalendarView, calendarPersonalHonesty, Layout, App, client, Alembic. No `en.json`/`cy.json` edits (defaults via `t(..., default)`).

## 1) Summary

- **Feature / Change name:** Path11 AUD-W-01 — Audits board Round 3 verify (already done on main)
- **Verdict:** **Already done** on `main` via AUD-W-W1 PR #1059 (3 work lanes + program chips). This PR is a **verify / lock-in** slice — not a net-new board redesign.
- **User goal:** Keep the operator board as Do now / Needs review / Closed + program chips; prevent regression to equal 4-col status board.
- **In scope:** Extract Round 3 board model module; vitest contract + UI verify; clear-program `data-testid`; Change Ledger
- **Out of scope:** URL sync for chips, backend summary API, locale files, other modules
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Board UX (product) | Already Round 3 on main (#1059) | Unchanged behaviour |
| Board model | Inline constants in `Audits.tsx` | Shared `auditsBoardModel.ts` for AUD-W-01 contract tests |
| Program clear control | No test id | `audits-program-clear` for Playwright/vitest |
| Tests | AUD-W-W1 lane + basic chip coverage | + AUD-W-01 model contract + 3-lane/not-4 + all program chips + clear restore |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** FE-only refactor + tests; same grouping/filter semantics as #1059
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Board remains 3 work lanes (Do now / Needs review / Closed) — verified on main + locked in tests
- [x] AC-02: Do now aggregates `scheduled` + `in_progress` (not separate equal columns)
- [x] AC-03: Program chips (Internal / UVDB / Planet Mark / Customer) filter board; clear restores
- [x] AC-04: No regression to 4 equal status columns (`scheduled` / `in_progress` lane test ids absent)
- [x] AC-05: Vitest AUD-W-01 model + UI verify suites green locally

## 5) Testing Evidence

- [x] `cd frontend && npx vitest run src/pages/__tests__/Audits.test.tsx src/pages/__tests__/auditsBoardModel.test.ts` — 28/28 passed locally
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Mixed statuses land in Round 3 lanes (scheduled+in_progress share Do now)
- [x] CUJ-02: All four program chips appear when data supports them; clear restores board
- [x] CUJ-03: Model contract rejects draft/cancelled as board-visible statuses

## 7) Observability & Ops

- **Playwright hooks:** existing `audits-board-lane-*`, `audits-program-filters`, `audits-program-chip-*` + new `audits-program-clear`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (**do not merge from this lane**)
3. Staging smoke `/audits` — 3 lanes + program chips

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- Prior ship: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/1059
- CI run(s): linked after PR creation

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [x] `cd frontend && npx vitest run src/pages/__tests__/Audits.test.tsx src/pages/__tests__/auditsBoardModel.test.ts`
- [ ] Manual: `/audits` — confirm 3 lanes + program chips (no 4 equal status columns)
- [ ] Manual: program chip filter + Clear program filter restores all cards
