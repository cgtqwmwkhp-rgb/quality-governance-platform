# Change Ledger (CL-FR-DASH-RECENT-01)

> Base: `origin/main` @ `d894e6ae9` (#1705 FR-AUDIT-SAVE-01 audit save timeout UX).
> Frontend only — no alembic, no API surface change, no new flag.

## 1) Summary

- **Feature / Change name:** FR-DASH-RECENT-01 — Dashboard "Recent cases" rows
  are real links into the case they name
- **User goal (1–2 lines):** A manager who spots a case on the dashboard opens it
  from there — click the row, middle-click the reference into a new tab, copy the
  link into a message, or tab to the row and press Enter — instead of reading the
  reference, going to the register, and finding it again by hand.
- **Problem:** The reference cell was painted `text-primary`, so the one thing on
  the panel that looked like a route into a case was plain text
  (`<td className="… text-primary">{formatReference(row.reference)}</td>`). The
  row had no click target and no `tabIndex` either. The only navigation the panel
  offered was "View All", which lands on the register — the user still has to
  find the record. Registers already fixed exactly this (PX-173 / PX-200) with a
  real `<Link>` in the reference cell plus a row-level open; the dashboard never
  got that treatment, so the two surfaces disagreed about whether a reference is
  clickable.
- **In scope:**
  - Reference cell renders the shared `CaseRegisterReferenceLink` pointing at the
    row's own detail route
  - Whole row is activatable — mouse click, Enter and Space
  - Correct detail route per tab: `/incidents/:id`, `/near-misses/:id`,
    `/complaints/:id`, `/rtas/:id`
  - Accessible row name that says which kind of case it opens
  - Honest no-link path when a feed hands back a row with no usable id
  - Tests for hrefs, row/keyboard navigation, and the inert-row case
- **Out of scope / deferred:**
  - Migrating the panel onto `CaseRegisterTable` — the dashboard table is a
    compact 5-column summary inside a `Card` with its own tab strip, not a
    register; folding it in is a layout change, not a link change
  - i18n for the panel's strings (the file has no `useTranslation` today; adding
    it for one new label would leave the tab labels, empty states and card title
    still hardcoded)
  - Any change to what the panel fetches or how rows are ordered
- **Feature flag / kill switch:** None — additive navigation on an existing
  panel; rollback is revert.

## 2) Impact Map (what changed)

- **Frontend:**
  - `frontend/src/pages/dashboard/RecentCasesPanel.tsx`
    - NEW `detailPath(href, id)` — returns `${href}/${id}`, or `null` when the id
      is not a positive integer.
    - `TABS` gains `noun` (`incident` / `near miss` / `complaint` /
      `road traffic accident`) for the row's accessible name, wording matched to
      each register's own `rowLabel`. `href` is documented as the register route
      that the detail route hangs off.
    - Reference cell renders `CaseRegisterReferenceLink` (imported from
      `components/register/`) instead of a `text-primary` `<td>`.
    - Row gets `onClick`, `onKeyDown` (Enter / Space), `tabIndex={0}`,
      `aria-label`, `cursor-pointer` and `data-testid="recent-cases-row"`.
- **Backend:** None.
- **APIs:** None. No route, payload, or status-code change.
- **Database:** None (no alembic).
- **Tests:** `frontend/src/pages/dashboard/__tests__/RecentCasesPanel.test.tsx`
  — new `RecentCasesPanel case links (FR-DASH-RECENT-01)` describe block (11
  tests) plus a `LocationProbe` helper following the `RiskRegister.test.tsx`
  convention. The existing PX-122 date-column block is untouched.
- **Docs:** This Change Ledger.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Purely additive to one presentational component.
  No exported type changed: `RecentCaseRow`, `RecentCaseKind` and
  `RecentCasesData` are byte-identical, so `useDashboardData` and `Dashboard.tsx`
  are untouched.
- **Route correctness:** All four detail routes are `${register}/:id` and were
  read off `App.tsx` (`incidents/:id`, `near-misses/:id`, `rtas/:id`,
  `complaints/:id`), not inferred from the tab id — note `near_misses` (tab) vs
  `near-misses` (route), which is exactly the kind of mismatch a guessed path
  would have shipped.
- **No invented data:** The link is built from `row.id`, which already came from
  the API list response. Nothing new is fetched, derived or displayed.
- **Fail-honest on a missing id:** `detailPath` returns `null` for a
  non-positive or non-integer id, and the row then renders the reference as
  muted plain text with no `tabIndex`, no `aria-label` and no click handler.
  `/incidents/0` or `/incidents/undefined` would have loaded a detail page that
  cannot resolve, which reads to the user as a broken case rather than a missing
  id.
- **Double-navigation:** `CaseRegisterReferenceLink` already calls
  `stopPropagation()` on click, so a click on the anchor does not also fire the
  row handler — React Router navigates once.
- **Stray keystrokes:** the row's `onKeyDown` returns unless
  `event.target === event.currentTarget`, so a key pressed inside a cell never
  navigates the dashboard away. Same guard as `CaseRegisterTable`; verified to
  fail the suite when removed (see §5).
- **ARIA:** the row stays a plain `<tr>` with no `role="button"` — the mistake
  PX-173 removed from the registers is not reintroduced here.
- **Breaking changes:** None.
- **Migration plan:** N/A.
- **Rollback strategy:** Revert the merge commit; no schema, no flag, no data.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Reference affordance honesty | Styled `text-primary` as if it were a link; was plain text | Real `<a href>` to the case, via the shared `CaseRegisterReferenceLink` |
| Open in new tab / copy link | Impossible — no anchor, no href | Native browser behaviour on the reference anchor |
| Keyboard access to a case | None — row had no `tabIndex` and no handler | Row is focusable; Enter and Space open the case |
| Mouse target | Nothing on the row was clickable | Whole row opens the case; reference anchor takes precedence |
| Screen-reader naming | Row announced as an unlabelled table row | `View incident: INC-2026-0057` etc., naming the kind of case |
| Dashboard ↔ register consistency | Registers had real reference links (PX-173 / PX-200), the dashboard did not | Same component, same interaction contract on both surfaces |
| Row with no usable id | N/A (nothing was clickable) | No link, no focus, no click — never a guessed `/incidents/0` |
| Route derivation | N/A | Read from `App.tsx`; `near_misses` tab correctly maps to `/near-misses/:id` |

## 4) Acceptance Criteria (AC)

- [x] AC-01: The reference in an incident row is an anchor whose `href` is that
  incident's detail route — `/incidents/57` for id 57, not `/incidents`.
- [x] AC-02: Each tab links to its own detail route — near misses to
  `/near-misses/3`, complaints to `/complaints/4`, RTAs to `/rtas/5`.
- [x] AC-03: Clicking a row away from the reference cell (on the title) routes to
  the case detail path.
- [x] AC-04: A focused row opens on Enter and on Space, and carries
  `tabindex="0"`.
- [x] AC-05: The row's accessible name names the kind of case it opens
  (`View near miss: NM-2026-0003`).
- [x] AC-06: A key pressed inside a cell rather than on the row does **not**
  navigate.
- [x] AC-07: A row whose feed gave no usable id renders no link, is not
  focusable, and does not navigate on click.
- [x] AC-08: "View All" still points at the register for the active tab
  (`/incidents`, then `/rtas`) — the panel-level link is not turned into a
  detail link.
- [x] AC-09: Change Ledger body present for the ledger gate / gate checklist.

## 5) Testing Evidence

Run locally in the worktree `.worktrees/dash-recent-cases-links`:

- [x] `npx vitest run src/pages/dashboard/__tests__/RecentCasesPanel.test.tsx`
  → **15 tests passed** (4 pre-existing PX-122 + 11 new)
- [x] Widened regression sweep `npx vitest run src/pages/dashboard
  src/pages/__tests__/Dashboard.test.tsx src/components/register`
  → **11 files, 103 tests passed**
- [x] `npx tsc --noEmit` → clean
- [x] `npx eslint src/pages/dashboard/RecentCasesPanel.tsx
  src/pages/dashboard/__tests__/RecentCasesPanel.test.tsx --max-warnings 0`
  → clean
- [x] **New tests fail without the fix.** Reverting only
  `RecentCasesPanel.tsx` to its `origin/main` state and re-running the file
  gives **9 failed / 6 passed** — the href, row-click, Enter/Space,
  accessible-name and inert-row assertions all fail on the old component, so
  none of them is vacuous.
- [x] **The cell-keystroke guard is load-bearing.** Disabling the
  `event.target !== event.currentTarget` check makes exactly the AC-06 test fail
  (1 failed / 14 passed); the guard was restored afterwards.
- [ ] Full CI — on PR
- [ ] Staging / Prod tip verify — after merge per conveyor (DONE ≠ merge)

Not verified: real-browser middle-click and "copy link address" against a live
backend. Those are native anchor behaviours and the evidence here is the rendered
`href` attribute in jsdom, not a browser interaction. No Playwright spec
references this panel, so none was updated.

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Manager sees a high-severity incident on the dashboard and clicks
  the row — lands on `/incidents/57`.
- [x] CUJ-02: Manager switches to Near misses / Complaints / RTAs and opens a
  row from each — lands on that record's own detail route, with the tab-to-route
  mapping (`near_misses` → `/near-misses`) correct.
- [x] CUJ-03: Keyboard-only user tabs to a recent-cases row and presses Enter —
  the case opens; a keystroke inside a cell does not navigate.
- [x] CUJ-04: Manager wants the case in a new tab — the reference is a real
  anchor with the detail `href`, so the browser's own middle-click and
  copy-link work.
- [ ] CUJ-05: Same four journeys against real tenant data on staging — to
  verify on tip after deploy.

## 7) Observability & Ops

- **Playwright / test hooks:** `recent-cases-row` (new), alongside the existing
  `recent-cases-panel`, `recent-cases-tabs`, `recent-cases-tab-*`,
  `recent-cases-view-all` and `recent-cases-date-header`.
- **Accessibility:** row carries an `aria-label` naming the case kind and
  reference; the row remains a plain `<tr>` with no invalid `role="button"`
  (PX-173). Reference anchor keeps `hover:underline` /
  `focus-visible:underline` from the shared component.
- **Logs / Metrics:** none new. Navigation is client-side routing to routes that
  already exist.
- **Ops note:** if a detail route ever stops being `${register}/:id`, the single
  place to change is `detailPath` plus the tab's `href`.

## 8) Release Plan

1. Open PR on tip `d894e6ae9` (#1705 merged).
2. Merge only after ledger/compliance gates and `CI - Default` are green.
3. Tip-chase: `Build, Push and Deploy to Azure` success for the tip SHA, then
   verify the ACA image tag contains the tip SHA on the prod FQDN.
4. Only then mark FR-DASH-RECENT-01 conveyor **PROD → DONE**. Merge alone is not
   done.

## 9) Rollback Plan

- **Trigger:** Dashboard rows navigate to the wrong record, a row swallows a
  keystroke needed elsewhere on the dashboard, or the reference anchor breaks
  the panel's layout.
- **Rollback steps:** Revert the merge commit on `main` and let the pipeline
  deploy the reverted tip. Frontend-only, no schema and no flag, so the revert
  is complete on its own — no data repair and no `Emergency Rollback -
  Production` image restore needed.
- **Owner:** Platform Engineering (Dashboard lane) — David Harris.

## 10) Evidence Pack (links)

- Branch: `feat/dash-recent-cases-links`
- Base: `d894e6ae9` (#1705)
- Files: 3 changed — 1 component, 1 test file, this ledger
- Local evidence: 103 vitest tests green, new tests proven to fail on
  `origin/main`, `tsc --noEmit` clean, eslint clean (see §5)
- CI / STG / PROD: pending after PR open

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts — frontend only; no API/schema/alembic; no exported
  type or prop signature changed; detail routes verified against `App.tsx`
- [ ] **Gate 2:** CI green — on PR
- [ ] **Gate 3:** Staging tip verify
- [x] **Gate 4:** Canary — N/A (no flag, additive frontend navigation)
- [ ] **Gate 5:** Production tip LIVE before DONE

## Anti-conflict checklist

- [x] No `Layout.tsx` / navigation shell edits
- [x] No notification service or dispatcher edits (no overlap with #1704
  `notif-kill1-governance-dispatcher`)
- [x] No `AuditTemplateBuilder` / `audit-builder` edits (no overlap with #1705
  `audit-save-timeout-ux`)
- [x] No alembic revision, no backend source, no API contract
- [x] No changes to `useDashboardData.ts`, `Dashboard.tsx`, or the register pages
  — `CaseRegisterReferenceLink` is imported, not modified
- [x] Enhance-never-replicate: reuses the registers' existing reference-link
  component and their PX-173 row-activation contract rather than writing a
  second implementation; the PX-122 date-column behaviour and its tests are
  left exactly as they were
