# Change Ledger (CL-PM-W1-SHELL)

## File allowlist (exclusive)

- `frontend/src/pages/PlanetMark.tsx`
- `frontend/src/pages/planetMarkHelpers.ts`
- `frontend/src/pages/__tests__/PlanetMark.test.tsx`
- `frontend/src/pages/__tests__/planetMarkHelpers.test.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_pm_w1_planet_mark_shell.md`

**Zero overlap** with parallel lanes: Actions, ComplianceAutomation, KnowledgeExceptions, Analytics, Audits.tsx, Layout, App, client.ts, api/__init__.py, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 PM-W1 — Planet Mark UI shell (Audits IA alignment)
- **User goal:** Operators on `/planet-mark` get a light-token shell with year switcher and five sections — **Years · Trends · Monthly · Improve · Export** — matching Audits section-toggle IA; honest empty states when ingest APIs are missing (no fake carbon numbers, no dark Scope 3 islands).
- **In scope:** PlanetMark page shell refactor; `planetMarkHelpers`; vitest; minimal `planet_mark.shell.*` i18n
- **Out of scope:** Layout/App routing; client.ts / backend routes; monthly ingest API; full legacy tab parity (scope3/certification/imported sub-pages)
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Page IA | 7 tabs (dashboard, emissions, scope3, actions, quality, certification, imported) | 5 Audits-style sections: years, trends, monthly, improve, export |
| Year selection | Gradient banner `<select>` | Header year switcher + URL `?year=` sync |
| Section nav | Primary-colored tab row | Audits-style `bg-surface` pill toggle + URL `?section=` sync |
| Styling | Mixed light cards + dark slate Scope 3 / emissions tables | Light design tokens throughout (`bg-card`, `border-border`, `bg-surface`) |
| Monthly | N/A | Honest empty — ingest not wired |
| Trends | Embedded in dashboard banner | Dedicated section; live rows when `historical_years` present, else empty |
| Improve | Full actions toolbar | Shell lists live actions when API returns rows; honest empty otherwise |
| Export | Header button only | Dedicated export section with download CTA |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** FE-only shell; existing Planet Mark APIs unchanged
- **Breaking changes:** None (route unchanged); legacy in-page tabs removed in favour of new IA (follow-on slices can re-home deep features)
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Year switcher present when reporting years exist
- [x] AC-02: Five sections — years, trends, monthly, improve, export — with Audits-style toggle
- [x] AC-03: Light tokens only (no `bg-slate-800` / dark Scope 3 islands)
- [x] AC-04: Monthly section shows honest empty (no fabricated monthly data)
- [x] AC-05: Trends shows live `historical_years` when available; honest empty otherwise
- [x] AC-06: Improve shows live actions when API returns rows; honest empty otherwise
- [x] AC-07: Export section exposes download for selected year without inventing totals
- [x] AC-08: Vitest covers shell tabs, empty states, setup flow, helpers

## 5) Testing Evidence

- [x] Vitest — `PlanetMark.test.tsx`, `planetMarkHelpers.test.ts` (14 tests)
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Tenant with reporting year — Years section shows live totals from API
- [x] CUJ-02: Monthly tab — honest placeholder, no fake numbers
- [x] CUJ-03: Setup-required tenant — create reporting year form still works

## 7) Observability & Ops

- **Playwright hooks:** `planet-mark-section-years`, `planet-mark-section-trends`, `planet-mark-section-monthly`, `planet-mark-section-improve`, `planet-mark-section-export`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging tip smoke `/planet-mark`

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation

---

# Follow-ons (PM-W1b+ — out of scope for this PR)

| Slice | Scope | Rationale |
|-------|-------|-----------|
| **PM-W1b** | Monthly ingest API + chart wiring | Requires backend route |
| **PM-W1c** | Re-home scope3 / certification / imported assessments under Years or Improve | Legacy feature parity |
| **PM-W1d** | URL deep-link polish + breadcrumb from Audits import flow | Cross-module routing |

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [x] `cd frontend && npx vitest run src/pages/__tests__/PlanetMark.test.tsx src/pages/__tests__/planetMarkHelpers.test.ts`
- [ ] Manual: `/planet-mark` — verify five sections, year switcher, light styling, monthly empty honesty
