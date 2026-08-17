# Change Ledger (CL-NAV-LIBRARY-DOCUMENT-CONTROL)

> **Start gate:** Parked behind #1785 A4 (`STACK_MAX=1`). Do not merge until A4 is LIVE.
> David request: add Document Control to the Library category in the vertical menu.

## 1) Summary
- **Feature / Change name:** Library hub owns Document Control
- **User goal:** Find Document Control under Library, next to Documents, instead of under Compliance & Sustainability.
- **In scope:** Sidebar IA only — Library becomes an expandable hub with Documents + Document Control. Document Control is removed from Compliance.
- **Out of scope:** LibraryShell tabs (Policies / campaigns stay in-page). Routes, APIs, Entra, Exceptions paging, A4 board lanes.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| NAV-01 | Library | Single `/documents` link | Expandable Library hub |
| NAV-02 | Document Control | Child of Compliance & Sustainability | Child of Library |
| NAV-03 | Policies / campaigns | Not sidebar items | Unchanged — LibraryShell tabs only |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Routes unchanged (`/documents`, `/document-control`, `/policies`). Deep links keep working.
- **Breaking changes:** None for APIs/data. Sidebar: Document Control moves; Compliance no longer lists it.
- **Migration plan:** None.
- **Rollback strategy:** Revert merge; redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Nav honesty | Document Control lived under Compliance while the page already links to Library | Document Control sits with the document library |
| Duplicate IA | Library was a lone link; controlled docs were a different hub | One Library hub; no second Document Control entry |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Vertical menu Library hub expands to Documents (`/documents`) and Document Control (`/document-control`).
- [x] AC-02: Document Control is not listed under Compliance & Sustainability.
- [x] AC-03: Policies and Document campaigns remain LibraryShell tabs, not extra sidebar items.
- [x] AC-04: `/document-control` auto-expands Library and marks Document Control active; `/documents` and `/policies` still mark Library/Documents active.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit (local): `Layout.test.tsx` — 29 passed
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Expand Library → Documents and Document Control; Compliance does not show Document Control.
- [x] CUJ-02: Open `/document-control` → Library is expanded and Document Control is the active child.

## 7) Observability & Ops
- Test ids: `nav-hub-library`, `nav-hub-btn-library` (same hub pattern as other first-level categories).

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge only after #1785 A4 is LIVE (`STACK_MAX=1`; admin-squash authorised when required CI is green).
2. Staging: sidebar Library expands to Documents + Document Control; `/document-control` still renders.
3. Promote PROD; verify `/api/v1/health` version = main tip; Production **Build and Deploy SUCCESS (not skipped)**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Document Control missing from the sidebar, duplicated under Compliance, or `/document-control` no longer reachable from nav.
- **Rollback steps:** Revert merge commit; redeploy prior tip via governed Staging → Production path.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `feat/nav-library-document-control`
- Ledger: `scripts/governance/pr_body_nav_library_document_control.md`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
