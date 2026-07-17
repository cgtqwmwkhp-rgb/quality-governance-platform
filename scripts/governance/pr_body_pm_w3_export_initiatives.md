# Change Ledger (CL-PM-W3-EXPORT-INITIATIVES)

**Path claim:** `path11/pm-w3-export-initiatives`

## File allowlist (exclusive)

- `frontend/src/pages/PlanetMark.tsx`
- `frontend/src/pages/planetMarkHelpers.ts`
- `frontend/src/pages/__tests__/PlanetMark.test.tsx`
- `frontend/src/pages/__tests__/planetMarkHelpers.test.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_pm_w3_export_initiatives.md`

**Zero overlap** with parallel lanes: EMP-07 workforce*, MAP-W1 IMS*, Documents*, Layout/App/client.ts spines, `api/__init__.py`, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 PM-W3 — Export pack JSON + AI hotspot initiatives → Improve actions
- **User goal:** Operators can download a real JSON export pack (not a dead unauthenticated `/export` URL) and turn ranked Scope 3 hotspot initiatives into Improve actions.
- **In scope:** Client JSON pack; hotspot initiative ranking; createAction wire; honesty that PDF/XLSX are follow-on; vitest; i18n
- **Out of scope:** Backend `/export` route; branded PDF/XLSX; monthly ingest; client.ts spine
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map

| Surface | Before | After |
|---------|--------|-------|
| Export button | `window.open(/api/.../export)` (dead / no auth) | Downloads authoritative **JSON pack** from live year + Scope 3 + actions + initiatives |
| Improve tab | Actions list / empty only | **Hotspot initiatives** ranked by footprint % + Add as Improve action |
| Copy | Implied full report ready | Explicit PDF/XLSX not wired |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Client-side pack + existing createAction API — no contract/Alembic changes
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Export downloads JSON pack (not dead window.open)
- [x] AC-02: Pack includes honesty notes for PDF/XLSX follow-on
- [x] AC-03: Initiatives ranked from measured Scope 3 footprint share
- [x] AC-04: Add as Improve action calls createAction and refreshes list
- [x] AC-05: Vitest covers helpers + export/initiative UI
- [x] AC-06: en + cy flat keys (≥95% cy coverage for new keys)

## 5) Testing Evidence

- [x] Vitest — planetMarkHelpers + PlanetMark
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Export section → JSON download
- [x] CUJ-02: Improve → initiative → Improve action

## 7) Observability & Ops

- **Playwright hooks:** `planet-mark-section-export`, `planet-mark-export-json`, `planet-mark-export-honesty`, `planet-mark-initiatives`, `planet-mark-initiative-*`

## 8) Checklist id

**PM-W3** (living tracker)
