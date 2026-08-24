# Change Ledger (CL-FR-WFFORCE-CAL-01 + CL-FR-WF-CG-01)

> Base: `origin/main` @ `5cd4a43fb` (#1707 FR-HONESTY-SWEEP-01 vapourware sweep).
> Deletion / freeze / redirect only. No new hub, no generic WF engine, no
> alembic revision, no OpenAPI change.

## 1) Summary

- **Feature / Change name:** FR-WFFORCE-CAL-01 — kill the duplicate Workforce
  calendar page; FR-WF-CG-01 — fold Competence gaps into the Knowledge Exchange
  → Actions thread and remove the orphan board.
- **User goal (1–2 lines):** Two entries in the Workforce hub led to surfaces
  that either restated data the product already shows better elsewhere, or had
  no owning journey at all. Removing them makes the hub describe what the
  product actually does.
- **Problem — item 1 (duplicate calendar):** `/workforce/calendar` was a second,
  narrower calendar implementation. `/calendar` (`CalendarView`) reads the
  unified feed `GET /api/v1/calendar/feed`, and
  `calendar_feed_service` **already** loads `AssessmentRun` and `InductionRun`
  rows and emits them as `type: "training"` events, with hrefs straight to
  `/workforce/assessments/{id}/execute` and `/workforce/training/{id}/execute`.
  The workforce grid fetched the same two collections directly and rendered its
  own month/week/list views over them — strictly less coverage (no audits,
  deadlines, reviews or meetings) for 614 lines of parallel calendar code.
- **Problem — item 2 (orphan competence gaps):** `/workforce/competence-gaps`
  was a standalone board whose only inbound journey was a nav entry and one
  deep link. Gaps are not authored there — they are raised by the Knowledge
  Exchange evidence hook (`competence_gap_service.from_evidence_link`, called
  from `governed_knowledge.py`) — and a gap only becomes tracked work when it
  becomes a CAPA. That CAPA already lives in the Actions register with
  `source_type = "competence_gap"`, which the unified Actions API accepts
  (`CAPA_ONLY_API_SOURCE_TYPES`). The board was a second inbox in front of work
  Actions already owns.
- **In scope:**
  - Delete `pages/workforce/Calendar.tsx`; retire `/workforce/calendar` to
    `/calendar?types=training`
  - Delete `pages/CompetenceGaps.tsx` and its now-unreferenced
    `api/competenceGapClient.ts`; retire `/workforce/competence-gaps` to
    `/actions?sourceType=competence_gap`
  - Remove both Workforce hub nav entries (the only Layout edit)
  - Add `competence_gap` to the Actions source filter so the redirect target
    does not misreport itself (see §3)
  - Remove the engineer-profile deep link that pointed at the deleted board
  - Drop the dead `competence_gap_href` from the Knowledge Exchange confirm
    payload
  - Registry + locale cleanup, and tests that fail if either surface returns
- **Out of scope / deliberately not done:**
  - **No backend competence-gap work.** `competence_gap_service`,
    `src/api/routes/workforce_competence_gaps.py`, `models/competence_gap.py`
    and `CAPASource.COMPETENCE_GAP` are untouched. Gaps are still recorded by
    both Knowledge Exchange hooks.
  - **No new hub, no generic workflow engine, no approvals surface.**
  - **No `/calendar` feature work.** `CalendarView` is not modified; the
    redirect only pre-selects a filter it already supported.
  - Audit Builder, `NotificationSettings`, `RecentCasesPanel`,
    `notification_service` and alembic — all untouched (no overlap with #1704 /
    #1706 / #1707).
  - No Assets regroup and no Admin visibility change; the Layout diff is nav
    removals only.
  - `docs/ux/page-stories-inventory.md` and the historical
    `scripts/governance/pr_body_*.md` files still describe both pages. They are
    point-in-time records of past PRs, not live registries, so they are left
    alone; `PAGE_REGISTRY.yml` (the registry the gates read) is updated.
- **Feature flag / kill switch:** None. Both changes are deletions; rollback is
  revert.

## 2) Impact Map (what changed)

- **Frontend — `frontend/src/components/Layout.tsx` (7 lines deleted, nothing
  added):** the `/workforce/calendar` item and the `/workforce/competence-gaps`
  item are gone from the Workforce hub, plus the `ShieldAlert` icon import that
  only the CG item used. No other nav edit — no hub added, reordered or
  renamed, and the `Calendar` icon import stays because the surviving
  `/calendar` entry under Insights uses it.
- **Frontend — `frontend/src/App.tsx`:** both routes now render
  `<Navigate … replace />`, matching the retirement idiom already in the file
  (`workflows`, `my-work`, `capa`, `evidence`, `knowledge-bank`). Both lazy
  imports removed. Each redirect carries a comment recording why the surface
  went.
- **Frontend — deletions:**
  - `pages/workforce/Calendar.tsx` (614 lines)
  - `pages/CompetenceGaps.tsx` (478 lines)
  - `api/competenceGapClient.ts` (151 lines) — after the page went, nothing
    imported it (verified repo-wide), so leaving it would be dead code that
    still looked like a live client.
- **Frontend — `frontend/src/pages/Actions.tsx` (+4 lines):** `competence_gap`
  added to the `SourceTypeFilter` union and one `SelectItem` added. This is the
  only non-test addition in the PR and it exists to keep the redirect honest —
  see §3. It follows the `compliance_record` precedent already in that
  `SelectContent`.
- **Frontend — `frontend/src/pages/workforce/EngineerProfile.tsx` (11 lines
  deleted):** `competenceGapsEngineerHref` and the "View competence gaps"
  header link removed. The link carried an `engineer_id` filter that no
  surviving surface honours, so it is deleted rather than silently widened to
  every engineer's gaps (retiring AC-04 of the earlier `pr_body_wf_profile`).
  The alternative — repointing the same link at
  `/actions?sourceType=competence_gap` — was rejected on evidence, not taste:
  `list_actions` offers no engineer filter at all, and the only person-shaped
  filter it has (`assigned_to`) resolves to the CAPA **owner**, which
  `competence_gap_service.create_capa` sets from `owner_id` / `owner_email` /
  `created_by_id` — never the engineer the gap is about. A link labelled with
  one engineer that lands on every engineer's gap work is the same class of
  lie this PR is removing, so the affordance goes rather than degrades. The
  engineer's own competency picture stays on the profile (competency records,
  state KPIs, requirements coverage), all untouched.
- **Frontend — locales:** 46 lines removed from **each** of `en.json` and
  `cy.json` (parity preserved): the 44 `competenceGaps.*` strings,
  `nav.competence_gaps`, and `workforce.engineers.view_competence_gaps`.
  `nav.calendar` is **kept** — the surviving `/calendar` nav entry uses it.
- **Backend — `src/api/routes/governed_knowledge.py` (2 insertions, 3
  deletions):** the evidence-confirm response no longer builds or returns
  `competence_gap_href`, which pointed at the deleted board.
  `competence_gap_id` is still returned. Gap creation itself is unchanged.
- **APIs:** No endpoint added, removed or changed shape by declaration.
  `competence_gap_href` was an undeclared key on an untyped `dict` response
  (the route has no `response_model`), it appears nowhere in
  `docs/contracts/openapi.json` or `openapi-baseline.json`, and no client in
  this repo read it — so both contract files are untouched.
- **Database:** None. No alembic revision, no column, no backfill.
- **Docs / registry:** `docs/ops/PAGE_REGISTRY.yml` — both entries converted to
  the existing `component: Navigate` alias convention used by `/capa`,
  `/my-work` and friends, with `expected_empty_state: null` and a description
  naming the redirect target. `workforce-competence-gaps` moves P1 → P2 to match
  that convention, so the `summary` block moves `p1_routes` 61 → 60 and
  `p2_routes` 44 → 45 (`total_routes` unchanged at 117 — no entry was added or
  removed). This was caught by
  `test_page_registry_summary_matches_measured_counts`, not by inspection.
  `last_updated` is bumped `2026-08-01` → `2026-08-10`, which is what
  `validate_registries.py` asks for when a registry's content is reviewed and
  changed. `docs/evidence/registry-validation-report.json` is a shared
  generated artifact whose only diff on this branch was its own regeneration
  timestamps, so it is deliberately **not** committed.
- **Tests:** see §5. Net: 3 test files deleted (they tested deleted code), 3
  updated, 1 backend governance list updated.
- **Dependencies:** None added, removed or updated.

## 3) Compatibility & Data Safety

- **Compatibility strategy:** redirects, not 404s. Both paths stay mounted and
  resolve with `replace`, so Back does not bounce.
- **`/workforce/calendar` → `/calendar?types=training` is a real destination,
  not a landing page.** `CalendarView` reads `types` from the query string,
  splits on comma and validates against `ALL_TYPES` (which contains
  `training`), and opens the filter panel when a type is pre-selected — so the
  user can see the filter that has been applied. The events behind
  `training` are the same assessment and induction runs the deleted grid drew.
- **The one honesty fix required by the CG redirect.** Actions builds its source
  dropdown from explicit `SelectItem`s, and `sourceTypeFilter` is populated by
  raw cast from the URL. Redirecting to `?sourceType=competence_gap` without
  adding the option would have left the trigger rendering its **"All Sources"**
  placeholder while the register was in fact filtered to one source — a control
  actively lying about the list beneath it. The option is added for that reason
  and for no other; the filter value itself already worked end to end, because
  the unified Actions API accepts `competence_gap`.
- **Stated plainly — a capability is lost, not relocated.** The deleted board
  was the **only** frontend caller of `/api/v1/workforce/competence-gaps/*`.
  `competence_gap_service.create_capa` is invoked from exactly one place in the
  codebase (`workforce_competence_gaps.py:155`, the REST route), so after this
  PR **there is no UI that escalates a gap to a CAPA, links a gap to an
  engineer/requirement, resolves or dismisses a gap, or renders a gap's golden
  thread.** The endpoints all still exist and still work for an API caller;
  nothing is deleted server-side. The consequence is that
  `/actions?sourceType=competence_gap` will list gap-sourced CAPAs raised before
  this change (or via API) and will not gain new ones through the UI. This is
  inherent in "remove the orphan surface" and is recorded here rather than left
  to be discovered: if the gap → CAPA step is wanted back, it needs a home in a
  journey someone actually walks, which is a separate FR.
- **Gaps are still captured.** Both `from_evidence_link` call sites in
  `governed_knowledge.py` and `from_signal` in the REST route are untouched, so
  the Knowledge Exchange hook keeps writing `competence_gap_actions` rows. No
  signal is dropped; only the standalone inbox in front of them is.
- **No data is destroyed by deploying this.** No migration, no delete
  statement. Existing `competence_gap_actions` rows and gap-sourced CAPAs are
  untouched and still readable over the API.
- **Role-gating change, deliberate and non-escalating.** Both routes previously
  sat behind `RequireRole allowed={['admin','supervisor']}`; the redirects are
  ungated, matching the `/workflows` idiom. This grants nothing: the targets
  `/calendar` and `/actions` are already reachable by any authenticated staff
  user by typing them, and each enforces its own authz plus backend
  permissions. A non-supervisor who follows an old bookmark now lands on a page
  they could always open, instead of a role wall.
- **Breaking changes:** none for any API consumer. For users: two nav entries
  and two pages disappear, and the engineer profile loses one header link.
- **Migration plan:** N/A.
- **Rollback strategy (DB):** no DB change. Revert the merge commit.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Calendar surfaces | Two implementations — `/calendar` (unified feed) and `/workforce/calendar` (assessments + inductions only) | One. The unified feed, which already carried both as `training` events |
| `/workforce/calendar` deep link | Loaded the duplicate grid | Redirects to `/calendar?types=training`, filter visibly applied |
| Calendar code | 614 lines of parallel month/week/list rendering | Deleted; no calendar logic added anywhere |
| Competence gap board | Standalone inbox with no owning journey | Removed; gap work is the CAPA in Actions |
| `/workforce/competence-gaps` deep link | Loaded the orphan board | Redirects to `/actions?sourceType=competence_gap` |
| Actions source filter honesty | `?sourceType=competence_gap` would filter the list while the control read "All Sources" | Option present, so the control states the filter it is applying |
| Gap capture (Knowledge Exchange) | Evidence-confirm hook raises a gap | Unchanged — still raises, still returns `competence_gap_id` |
| Gap → CAPA escalation in UI | "Create CAPA" button on the board | **None — API-only.** Declared in §3, not papered over |
| `competence_gap_href` in confirm payload | Emitted a link to the board; no client read it | Removed rather than left pointing at a deleted page |
| Engineer profile gap link | Deep link with an `engineer_id` filter | Removed rather than widened to all engineers' gaps |
| Workforce nav budget | 6 children | 4 children; two slots returned, none added |
| PAGE_REGISTRY | Both routes registered as real pages (CG as P1) | Both registered as `Navigate` aliases naming their target; summary counts corrected |
| Locale parity | — | 46 keys removed from en **and** cy; `i18n:check` clean |
| Backend competence-gap stack | Service, routes, model, migrations | Untouched, byte-identical |

## 4) Acceptance Criteria (AC)

- [x] AC-01: The Workforce hub, fully expanded, contains no Workforce calendar
  link and no Competence gaps link.
- [x] AC-02: `/workforce/calendar` resolves to `/calendar?types=training` and
  renders the unified calendar, not a 404 and not a second grid.
- [x] AC-03: `/workforce/competence-gaps` resolves to
  `/actions?sourceType=competence_gap` and renders the Actions register.
- [x] AC-04: The Actions source control names the `competence_gap` filter it is
  applying rather than showing its "All Sources" placeholder.
- [x] AC-05: `pages/workforce/Calendar.tsx`, `pages/CompetenceGaps.tsx` and
  `api/competenceGapClient.ts` are gone, and nothing in the repo still imports
  them.
- [x] AC-06: The surviving `/calendar` entry under Insights and the rest of the
  Workforce hub are unchanged; the `Layout.tsx` diff is nav removals only, with
  no Assets or Admin edit.
- [x] AC-07: No backend competence-gap service, route, model or migration is
  modified; the only backend edit removes a dead href from one response.
- [x] AC-08: No alembic revision, no `openapi.json` / `openapi-baseline.json`
  change.
- [x] AC-09: No test was skipped, loosened or deleted to go green. The three
  deleted test files tested deleted code; the surviving `dateUtils` helpers keep
  full coverage in `dateUtils.test.ts`.
- [x] AC-10: Change Ledger body present for the ledger gate / gate checklist.

## 5) Testing Evidence

Run locally in the worktree `.worktrees/p2-calendar-cg-cut` on `5cd4a43fb`:

- [x] **Full frontend suite** `npx vitest run` → **406 files, 2820 tests
  passed**, 0 failed, 0 skipped.
- [x] `npx tsc --noEmit` → clean (this is what proves no surviving module
  imports the three deleted files).
- [x] `npm run lint` (`eslint src/ --max-warnings 0`) → clean.
- [x] `npm run i18n:check` → "All i18n keys validated (4182 keys, 598 files
  scanned)"; cy parity unchanged at 92.0%.
- [x] Backend `pytest tests/unit/test_page_registry_nav_routes.py` → **15
  passed**. This suite **caught a real defect mid-change**: the registry
  `summary` counts still claimed 61 P1 routes after CG moved to P2. Fixed by
  correcting the counts, not by touching the assertion.
- [x] Backend `pytest tests/integration/test_competence_gap_cuj.py` → **2
  passed** — the gap loop still works server-side with the board gone.
- [x] Backend `pytest tests/unit/test_assessor_followup_hooks.py
  tests/unit/test_governed_knowledge_service.py` → **33 passed**, covering the
  evidence-confirm hook whose payload changed.
- [x] `python scripts/validate_registries.py` → all 3 registries pass. (The
  evidence JSON it rewrites was reverted — it is a shared generated artifact and
  its only diff was a regeneration timestamp unrelated to this PR.)
- [x] `mypy src/api/routes/governed_knowledge.py` → "Success: no issues found in
  1 source file".
- [x] **Every new/changed test proven to bite (negative controls, each reverted
  afterwards):**
  - Restoring `Layout.tsx` from `origin/main` → exactly the new nav-absence test
    fails (1 failed / 19 passed).
  - Repointing the calendar redirect at `/dashboard` and the CG redirect at
    `/actions?view=mine` → exactly the two new redirect tests fail (2 failed /
    11 passed). The CG case failing on a still-`/actions` target confirms the
    search-param assertion does real work.
  - Re-adding a `engineer-competence-gaps-link` anchor → exactly the rewritten
    EngineerProfile test fails (1 failed / 12 passed).
- **Test file changes:**
  - `frontend/src/__tests__/App.test.tsx` — 2 new redirect tests; stale
    `vi.mock('../pages/workforce/Calendar')` removed (it would fail resolution
    against the deleted file).
  - `frontend/src/components/__tests__/Layout.test.tsx` — new absence test that
    also asserts `/calendar` still appears under Insights (positively, by
    expanding that hub, so it cannot pass vacuously); Workforce hub expectation
    trimmed.
  - `frontend/src/pages/workforce/__tests__/EngineerProfile.test.tsx` — the
    "links to competence gaps" test becomes an absence test that first waits for
    `engineer-identity`, so it cannot pass against an unrendered tree; the
    `competenceGapsEngineerHref` unit test and import are removed with the
    function.
  - **Deleted:** `pages/workforce/__tests__/Calendar.test.tsx` (287),
    `pages/__tests__/CompetenceGaps.test.tsx` (328),
    `frontend/tests/e2e/workforce-calendar.spec.ts` (148). The first duplicated
    `dateUtils` coverage that `dateUtils.test.ts` already holds in full; no
    config or CI job references the deleted e2e spec (checked).
  - `tests/unit/test_page_registry_nav_routes.py` — `/workforce/competence-gaps`
    moves from `LAYOUT_NAV_ROUTES` (Layout no longer links it) to
    `NAVIGATE_ALIAS_ROUTES`, and `/workforce/calendar` joins it. That list
    asserts P2 + `component: Navigate`, so it now enforces the redirect
    convention on both routes rather than merely tolerating them.
- [ ] Full CI — on PR.
- [ ] Staging / Prod tip verify — after merge per conveyor (DONE ≠ merge).

**Not verified:** `ruff` is not installed in this local toolchain, so the two
changed Python files were checked with `mypy` only; CI's lint job is the first
`ruff` run on them. The Python diff is three deleted lines plus a comment in one
route function and a two-entry move between two module-level tuples in one test.

No real browser was driven. Redirect evidence is
`window.location` after render in jsdom, not a browser navigation. The Playwright
UX-coverage specs (`link-audit`, `page-audit`, `a11y-audit`) are registry-driven
and run against a deployed app; they were not executed locally, so the claim
that both routes behave like the existing `Navigate` aliases in those audits
rests on the registry entries matching that convention exactly, not on a run.
No load or performance testing was done (none is relevant to a deletion).

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: A supervisor expands Workforce and sees Competency, Assessments,
  Training and Engineers — no calendar, no gaps board.
- [x] CUJ-02: A user follows an old `/workforce/calendar` bookmark and lands on
  the unified calendar with the training filter applied, where the same
  assessment and induction events are listed.
- [x] CUJ-03: A user follows an old `/workforce/competence-gaps` bookmark and
  lands on the Actions register filtered to competence-gap CAPAs, with the
  source control naming that filter.
- [x] CUJ-04: An assessor confirms an evidence link; the gap is still raised and
  `competence_gap_id` still comes back, with no link to a dead page.
- [x] CUJ-05: An engineer profile still opens and shows identity, tickets and
  requirements, with no dead gaps link in the header.
- [ ] CUJ-06: The same journeys against real tenant data on staging — to verify
  on tip after deploy.

## 7) Observability & Ops

- **Removed test hooks:** `competence-gap-row-*`, `competence-gap-status-filter`,
  `competence-gap-engineer-*`, `competence-gap-requirement-*` and
  `engineer-competence-gaps-link` disappear with the deleted page and link. No
  spec outside the deleted test files referenced them (checked repo-wide).
- **Retained hooks:** `actions-source-filter` now also selects
  `competence_gap`; `engineer-identity` is unchanged and is now load-bearing for
  the EngineerProfile absence test.
- **Logs / Metrics / Alerts:** none new, none removed. No backend telemetry
  changes — the only backend edit drops one string from one response body.
- **Ops note:** `/api/v1/workforce/competence-gaps/*` stays mounted and still
  answers, so any external caller or monitor pointed at it is unaffected. Only
  the human-facing surface is gone.
- **Runbook updates:** none required — no operational procedure referenced
  either page.

## 8) Release Plan

1. Open PR on tip `5cd4a43fb` (#1707 merged). **Do not merge** — raised for
   review only, per the request.
2. Merge only after the ledger / compliance gates and `CI - Default` are green.
3. Tip-chase: `Build, Push and Deploy to Azure` success for the tip SHA, then
   verify the ACA image tag contains the tip SHA on the prod FQDN.
4. Only then mark FR-WFFORCE-CAL-01 / FR-WF-CG-01 conveyor **PROD → DONE**.
   Merge alone is not done.

## 9) Rollback Plan

- **Trigger:** a journey depended on the workforce grid's specific layout, or
  the loss of the UI gap → CAPA step (§3) proves urgent rather than deferrable.
- **Rollback steps:** revert the merge commit on `main` and let the pipeline
  deploy the reverted tip. Frontend-plus-one-response-field, no schema, no flag,
  no data migration, so the revert is complete on its own — no data repair and
  no `Emergency Rollback - Production` image restore needed.
- **Partial option:** because the backend stack is untouched, the gap → CAPA
  step can be restored by reinstating the client and a call site alone, without
  reverting the calendar half.
- **Owner:** Platform Engineering (Governance UX lane) — David Harris.

## 10) Evidence Pack (links)

- Branch: `feat/p2-calendar-cg-cut`
- Base: `5cd4a43fb` (#1707)
- Files: 18 changed excluding this ledger — 6 source, 2 locale, 1 registry,
  4 frontend test files, 1 backend governance test, 3 pages/clients deleted,
  1 e2e spec deleted
- Net excluding the ledger: **89 insertions, 2,155 deletions** across 18 files;
  the only non-test production addition is 4 lines in `Actions.tsx`
- Local evidence: 2,820 frontend tests green; 50 backend tests green across 4
  files; all new tests proven to fail without their change; `tsc` / eslint /
  i18n / registry validation clean (see §5)
- CI / STG / PROD: pending after PR open

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Contracts — no API declared shape change, no schema, no
  OpenAPI baseline, no alembic; the one backend edit removes an undeclared key
  from an untyped response that no client read
- [ ] **Gate 2:** CI green — on PR
- [ ] **Gate 3:** Staging tip verify
- [x] **Gate 4:** Canary — N/A (no flag; deletion + redirect)
- [ ] **Gate 5:** Production tip LIVE before DONE

## Anti-conflict checklist

- [x] `Layout.tsx` edit is **nav removals only** — two hub items and one icon
  import, 7 deleted lines, 0 added. Sole Layout owner for this PR.
- [x] No Assets regroup, no Admin visibility change, no hub added, reordered or
  renamed
- [x] No Audit Builder / `AuditTemplateBuilder` / `audit-builder` edits
- [x] No `NotificationSettings.tsx` edits (no overlap with #1707)
- [x] No `RecentCasesPanel.tsx` / dashboard edits (no overlap with #1706)
- [x] No `notification_service` / dispatcher edits (no overlap with #1704)
- [x] No alembic revision, no OpenAPI contract change
- [x] No new hub and no generic WF engine; FR-APPROVALS-01 untouched
- [x] Backend competence-gap service / routes / model left byte-identical
- [x] Retirement uses the `<Navigate replace>` idiom already in `App.tsx`
      rather than introducing a new pattern
- [x] Shared generated artifact `docs/evidence/registry-validation-report.json`
      deliberately reverted, not committed
