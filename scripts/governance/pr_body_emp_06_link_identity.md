# Change Ledger (CL-EMP-06)

## File allowlist (exclusive)

- `frontend/src/pages/workforce/EngineerProfile.tsx`
- `frontend/src/pages/workforce/Engineers.tsx`
- `frontend/src/pages/workforce/__tests__/EngineerProfile.test.tsx`
- `frontend/src/pages/workforce/__tests__/Engineers.test.tsx`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_emp_06_link_identity.md`

**Zero overlap** with parallel lanes: CA-W1a i18n/IMS (#1066), `PlanetMark*` (#1065), Layout/App/client spines, `api/__init__.py`, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 EMP-06 — Employee ↔ QGP user link UI honesty
- **User goal:** Workforce admins see whether an employee row is linked to a portal user (`user_id`) or is a valid PAMS-only row — no silent assumption that every engineer has a login.
- **In scope:** Engineer profile identity panel + roster badge; i18n; vitest
- **Out of scope:** Backend schema relax, user picker/search, edit-in-place link flow, PAMS sync upsert changes
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Engineer profile | `user_id` hidden | **QGP user link** row — linked `#id` or honest unlinked copy |
| Engineers roster cards | Active/inactive only | + **User #id** or **No user link** badge |
| Create dialog | Optional user ID field (unchanged) | Unchanged — honesty on read surfaces |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Read-only UI — no API contract changes
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Profile shows linked state when `engineer.user_id` is set
- [x] AC-02: Profile shows unlinked honesty copy when `user_id` is null/undefined
- [x] AC-03: Roster card badge distinguishes linked vs unlinked rows
- [x] AC-04: i18n keys added for en + cy
- [x] AC-05: Vitest covers linked + unlinked profile states

## 5) Testing Evidence

- [x] Vitest — `EngineerProfile.test.tsx`, `Engineers.test.tsx`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Admin opens linked employee — sees “Linked to user #N”
- [x] CUJ-02: Admin opens PAMS-only employee — sees unlinked message (not blank / not fake user)

## 7) Observability & Ops

- **Playwright hooks:** `engineer-user-link`, `engineer-user-link-linked`, `engineer-user-link-unlinked`, `engineer-user-linked-{id}`, `engineer-user-unlinked-{id}`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke `/workforce/engineers` + profile detail

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected (no spines)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [ ] `cd frontend && npx vitest run src/pages/workforce/__tests__/EngineerProfile.test.tsx src/pages/workforce/__tests__/Engineers.test.tsx`
- [ ] Manual: employee with `user_id` — profile + roster badge show link
- [ ] Manual: PAMS employee without `user_id` — honest unlinked copy
