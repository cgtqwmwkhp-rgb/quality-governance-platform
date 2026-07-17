# Change Ledger (CL-MAP-W1-STANDARDS)

**Path claim:** `path11/map-w1-standards`

## File allowlist (exclusive)

- `frontend/src/pages/IMSDashboard.tsx`
- `frontend/src/pages/imsMapHonesty.ts`
- `frontend/src/pages/__tests__/imsMapHonesty.test.ts`
- `frontend/src/pages/__tests__/IMSDashboard.test.tsx`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_map_w1_standards.md`

**Zero overlap** with parallel lanes: PlanetMark*, workforce EMP-07*, Documents* (#1070), Layout/App/client.ts spines, `api/__init__.py`, Alembic. EVD-02 skipped (prefer MAP-W1 Standards/IMS map).

## 1) Summary

- **Feature / Change name:** Path11 MAP-W1 — IMS Standards map multi-scheme honesty
- **User goal:** On IMS Cross-Standard Mapping, operators see ISO / Planet Mark / UVDB scheme chips with live-vs-awaiting honesty; faux Planet Mark/UVDB “Complete” management-review rows are demoted to Not live placeholders; Audit Builder AI accept chips explicitly follow-on.
- **In scope:** IMS mapping tab honesty; scheme detection helper; review demo-source honesty; vitest; i18n
- **Out of scope:** Audit Builder AI suggest chips (MAP-W2); Alembic; Documents*; evidence spine (EVD-02)
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map

| Surface | Before | After |
|---------|--------|-------|
| IMS Mapping tab | Generic “live from DB” copy | Multi-scheme chips + propose-only / builder follow-on honesty |
| Management review Carbon/UVDB | Status Complete (faux) | **Not live** + static placeholder hint |
| Scheme coverage | Invisible | ISO / Planet Mark / UVDB live-vs-awaiting |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** FE-only honesty; no API/Alembic
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Mapping tab shows scheme chips + honesty copy
- [x] AC-02: Demo Planet Mark/UVDB review rows not shown as Complete
- [x] AC-03: Helper detects schemes from mapping labels
- [x] AC-04: Vitest coverage
- [x] AC-05: en + cy flat keys
- [x] AC-06: No Documents* / Alembic touches

## 5) Testing Evidence

- [x] Vitest — imsMapHonesty + IMSDashboard MAP-W1
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: IMS → Cross-Standard Mapping → scheme honesty visible

## 7) Observability & Ops

- **Playwright hooks:** `ims-map-w1-panel`, `ims-map-w1-honesty`, `ims-map-w1-scheme-chips`, `ims-map-w1-demo-review-row`

## 8) Checklist id

**MAP-W1** (living tracker) — EVD-02 skipped (Documents*/evidence spine collision risk after #1070; MAP-W1 clearer and disjoint)
