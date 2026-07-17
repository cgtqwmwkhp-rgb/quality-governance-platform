# Change Ledger (CL-TPL-02-PDF-EXPORT)

**Path claim:** `path11/tpl-02-pdf-export`

## File allowlist (exclusive)

- `frontend/src/pages/InvestigationDetail.tsx`
- `frontend/src/pages/investigation/investigationReportHelpers.ts`
- `frontend/src/pages/investigation/__tests__/investigationReportHelpers.test.ts`
- `frontend/src/pages/__tests__/InvestigationDetail.test.tsx`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_tpl_02_pdf_export.md`

**Zero overlap** with parallel lanes: `Documents*`, `ComplianceAutomation*`, `PlanetMark*` (#1068), Layout/App/client.ts spines, `api/__init__.py`, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 TPL-02 — Investigation Report tab download honesty + JSON export stub
- **User goal:** Operators on the Report tab can download something real when a pack exists; generate triggers immediate JSON export; copy is honest that branded PDF is a follow-on.
- **In scope:** Wire history Download button; generate → JSON download; manifest stub when only metadata available; helpers + vitest; minimal i18n
- **Out of scope:** Branded PDF renderer; backend GET pack-by-id; `client.ts` spine; template builder changes
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Report history Download | Inert button (no handler) | Downloads **JSON manifest stub** with checksum metadata + PDF honesty note |
| Generate Internal/External | Creates pack, no download | Creates pack + **immediate full JSON export** of server payload |
| Copy | Implied PDF ready | Explicit: JSON today, branded PDF follow-on |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Client-side download only — no API contract changes
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Report history Download button triggers manifest stub download when pack row exists
- [x] AC-02: Generate report downloads full JSON payload from `generatePack` response
- [x] AC-03: Tooltip/copy states branded PDF is not wired yet
- [x] AC-04: Vitest covers helper payloads + download click on Report tab
- [x] AC-05: No `client.ts` / backend spine edits

## 5) Testing Evidence

- [x] Vitest — `investigationReportHelpers.test.ts`, `InvestigationDetail.test.tsx`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Investigation with generated pack → Report tab → Download → JSON manifest saves
- [x] CUJ-02: Generate Internal Report → JSON export downloads + pack appears in history

## 7) Observability & Ops

- **Playwright hooks:** `investigation-pack-download-{id}`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke: investigation Report tab generate + download

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation
- Builds on: TPL-01 INC043 template scaffold (#1063)

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [ ] `cd frontend && npx vitest run src/pages/investigation/__tests__/investigationReportHelpers.test.ts src/pages/__tests__/InvestigationDetail.test.tsx`
- [ ] Manual: open investigation Report tab → download existing pack manifest
- [ ] Manual: generate report → JSON file downloads
