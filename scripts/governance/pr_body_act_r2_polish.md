# Change Ledger (CL-ACT-R2-POLISH)

## File allowlist (exclusive)

- `frontend/src/pages/Actions.tsx`
- `frontend/src/pages/__tests__/Actions.test.tsx`
- `frontend/src/i18n/locales/en.json` (3 `actions.detail.*` keys for expand polish)
- `scripts/governance/pr_body_act_r2_polish.md`

**Zero overlap** with parallel lanes: Layout/App/client spines; Harden #1048–#1050.

## 1) Summary

- **Feature / Change name:** Path11 — Actions Round 2 polish (ACT-R2)
- **User goal:** Shareable hero/view/source filters; keyboard-safe create dialog; honest KPI counts on load failure; richer expandable row details.
- **In scope:** `Actions.tsx` URL sync, a11y, honesty, detail expand; vitest proofs; minimal i18n; Change Ledger
- **Out of scope:** Layout/App/client.ts spines; Harden already shipped (#1048–#1050)
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Hero KPI URL | Only `view`/`sourceType` partially synced; `status` not shareable | Full bidirectional sync for `status`, `view`, `sourceType` (+ existing `sourceId`) |
| View-mode toggles | No `aria-pressed` | Toggle group exposes pressed state |
| Create dialog | Escape closed but focus not restored | Escape closes; focus returns to New Action trigger; first field focused on open |
| Hero metrics | Fell back to client `actions.length` zeros | Summary-only counts; em dash while unavailable; error page instead of fake zeros on list failure |
| Detail expand | Basic description only | `aria-controls` + region panel; type + created metadata |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive URL params (`status`); existing deep links unchanged
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: `?status=open` (and hero clicks) sync to URL and hydrate on load/back
- [x] AC-02: `view` + `sourceType` remain shareable with bidirectional hydration
- [x] AC-03: Hero + view-mode buttons expose `aria-pressed`; Esc closes create dialog with focus restore
- [x] AC-04: List load failure shows retry — no hero zero theatre; summary failure keeps unavailable banner
- [x] AC-05: Expanded row links via `aria-controls`; shows type/created metadata
- [x] AC-06: Vitest covers URL sync, honesty, a11y, expand polish

## 5) Testing Evidence

- [x] Vitest `Actions.test.tsx` — `Actions Round 2 polish — URL sync` + `honesty & a11y` describe blocks
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Share `/actions?status=open&sourceType=incident` — filters hydrate
- [x] CUJ-02: Hero Overdue → `view=overdue`; hero Open → `status=open`
- [x] CUJ-03: New Action → Escape → focus on trigger
- [x] CUJ-04: API 500 on list load → Try Again, no KPI zeros

## 7) Observability & Ops

- **Test hooks:** `actions-hero-*`, `actions-view-*`, `actions-summary-unavailable`, `actions-detail-*`, `search-params` (test probe)

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke `/actions` with shared filter URLs

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
